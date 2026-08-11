"""Stage 1 — Collect: discover devices, fetch sources, mirror llm-wiki/raw."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich.console import Console

from terminal_insight_v2.category.loader import load_category_schema
from terminal_insight_v2.config import settings
from terminal_insight_v2.fetch import FetchResult, fetch_url
from terminal_insight_v2.identity import source_id as make_source_id
from terminal_insight_v2.models.stage import StageContext, StageResult
from terminal_insight_v2.providers.llm import LLMProvider
from terminal_insight_v2.providers.search import resolve_search_provider
from terminal_insight_v2.render.sources_html import write_collect_sources_html
from terminal_insight_v2.sourcing.discover import discover_devices
from terminal_insight_v2.sourcing.plan_urls import PlannedUrl, plan_urls_for_device
from terminal_insight_v2.store.db import transaction, utc_now
from terminal_insight_v2.store.repositories import persist_fetch, upsert_device
from terminal_insight_v2.store.wiki import write_raw_snapshot
from terminal_insight_v2.stages.base import Stage

console = Console()


def _fetch_and_persist(
    did: str,
    plan: PlannedUrl,
    *,
    run_id: str,
) -> Tuple[PlannedUrl, FetchResult, str, str]:
    fr = fetch_url(plan.url, settings)
    snap_id = ""
    wiki_rel = ""
    with transaction() as conn:
        sid = persist_fetch(
            conn,
            device_id=did,
            url=plan.url,
            link_role=plan.link_role,
            batch_id=run_id,
            tier=plan.tier,
            source_kind=plan.source_kind,
            fetch_method=fr.fetch_method,
            http_status=fr.http_status,
            final_url=fr.final_url,
            raw_status=fr.raw_status,
            raw_html=fr.raw_html,
            content_md=fr.content_md,
            error=fr.error,
        )
    if sid:
        snap_id = sid
        src_id = make_source_id(plan.url) or "unknown"
        if fr.content_md or fr.raw_html:
            wiki_dir = write_raw_snapshot(
                device_id=did,
                source_id=src_id,
                snapshot_id=snap_id,
                url=plan.url,
                content_md=fr.content_md,
                raw_html=fr.raw_html,
                meta={
                    "run_id": run_id,
                    "link_role": plan.link_role,
                    "raw_status": fr.raw_status,
                    "fetch_method": fr.fetch_method,
                },
            )
            wiki_rel = str(wiki_dir.relative_to(settings.memory_root()))
    return plan, fr, snap_id, wiki_rel


class CollectStage(Stage):
    name = "collect"

    def prereq(self, ctx: StageContext) -> None:
        if not (settings.doubao_api_key or "").strip() and not (settings.tavily_api_key or "").strip():
            raise RuntimeError("DOUBAO_API_KEY or TAVILY_API_KEY is required for collect")
        if not (settings.openai_api_key or "").strip():
            raise RuntimeError("OPENAI_API_KEY is required for collect (discovery)")

    def run(self, ctx: StageContext) -> StageResult:
        schema = load_category_schema(ctx.category, persist=False)
        schema_id = ctx.schema_fingerprint or schema.fingerprint
        search = resolve_search_provider(settings)
        llm = LLMProvider(settings)

        devices, pool_hits = discover_devices(
            schema,
            settings,
            date_start=ctx.date_start,
            date_end=ctx.date_end,
            search=search,
            llm=llm,
        )
        if not devices:
            return StageResult(
                stage=self.name,
                status="partial",
                output_revision=f"collect:{ctx.run_id}:0devices",
                errors=["discovery returned 0 devices"],
            )

        manifest_devices: List[Dict[str, Any]] = []
        errors: List[str] = []
        fetched_ok = 0
        fetched_fail = 0
        fetch_workers = max(1, settings.collect_fetch_workers)

        for dev in devices:
            with transaction() as conn:
                did = upsert_device(
                    conn,
                    dev,
                    category=ctx.category,
                    schema_id=schema_id,
                )
            planned = plan_urls_for_device(
                dev,
                schema,
                settings,
                search=search,
                extra_hits=pool_hits,
            )
            console.log(
                f"[collect] {dev.brand} {dev.model}: {len(planned)} urls"
            )
            source_rows: List[Dict[str, Any]] = []

            with ThreadPoolExecutor(max_workers=fetch_workers) as pool:
                futs = {
                    pool.submit(_fetch_and_persist, did, p, run_id=ctx.run_id): p
                    for p in planned
                }
                for fut in as_completed(futs):
                    plan = futs[fut]
                    try:
                        p, fr, snap_id, wiki_rel = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{dev.brand} {dev.model} {plan.url}: {exc}")
                        fetched_fail += 1
                        source_rows.append(
                            {
                                "url": plan.url,
                                "raw_status": "failed",
                                "error": str(exc),
                                "link_role": plan.link_role,
                                "tier": plan.tier,
                            }
                        )
                        continue
                    if fr.raw_status in ("ok", "markdown_only"):
                        fetched_ok += 1
                    else:
                        fetched_fail += 1
                    source_rows.append(
                        {
                            "url": p.url,
                            "title": p.title,
                            "site": p.site,
                            "link_role": p.link_role,
                            "tier": p.tier,
                            "source_kind": p.source_kind,
                            "raw_status": fr.raw_status,
                            "fetch_method": fr.fetch_method,
                            "http_status": fr.http_status,
                            "snapshot_id": snap_id,
                            "wiki_path": wiki_rel,
                            "error": fr.error,
                        }
                    )

            manifest_devices.append(
                {
                    "device_id": did,
                    "brand": dev.brand,
                    "model": dev.model,
                    "release_date": dev.release_date,
                    "sources": source_rows,
                }
            )

        manifest: Dict[str, Any] = {
            "schema_version": 1,
            "run_id": ctx.run_id,
            "category": ctx.category,
            "schema_fingerprint": schema_id,
            "date_start": ctx.date_start,
            "date_end": ctx.date_end,
            "generated_at": utc_now(),
            "input_revision": ctx.input_revision or f"run:{ctx.run_id}",
            "devices": manifest_devices,
            "metrics": {
                "devices": len(manifest_devices),
                "sources_ok": fetched_ok,
                "sources_failed": fetched_fail,
                "search_calls": search.call_count,
                "llm_calls": llm.call_count,
            },
        }

        run_dir = Path(ctx.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = run_dir / "collection_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        html_path = run_dir / "sources.html"
        write_collect_sources_html(manifest, html_path)
        n_devices = len(manifest_devices)
        html_name = f"sources_{n_devices}{ctx.category}.html"
        write_collect_sources_html(manifest, run_dir / html_name)

        status = "ok" if fetched_ok else "partial"
        if fetched_fail and fetched_ok:
            status = "partial"

        return StageResult(
            stage=self.name,
            status=status,
            output_revision=f"collect:{ctx.run_id}:d{len(devices)}",
            metrics=manifest["metrics"],
            artifacts={
                "collection_manifest.json": str(manifest_path),
                "sources.html": str(html_path),
                html_name: str(run_dir / html_name),
                "llm_wiki_raw": str(settings.memory_root() / "llm-wiki" / "raw"),
            },
            errors=errors[:20],
        )

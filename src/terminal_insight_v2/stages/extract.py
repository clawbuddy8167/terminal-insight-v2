"""Stage 2 — Extract: one LLM call per snapshot → field_assertions."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from rich.console import Console

from terminal_insight_v2.category.loader import load_category_schema
from terminal_insight_v2.category.schema import CategorySchema
from terminal_insight_v2.config import settings
from terminal_insight_v2.identity import blob_matches_model
from terminal_insight_v2.models.extraction import ExtractSnapshotPayload
from terminal_insight_v2.models.stage import StageContext, StageResult
from terminal_insight_v2.prompts import extract_snapshot_system, extract_snapshot_user
from terminal_insight_v2.providers.llm import LLMProvider
from terminal_insight_v2.store.db import transaction, utc_now
from terminal_insight_v2.store.repositories import (
    clear_assertions_for_run,
    insert_field_assertion,
    new_assertion_id,
    update_snapshot_match,
)
from terminal_insight_v2.store.snapshots import SnapshotRow, load_snapshot_body, load_snapshots_for_run
from terminal_insight_v2.stages.base import Stage
from terminal_insight_v2.verify.resolution import load_assertions_for_run

console = Console()


def _field_lines(schema: CategorySchema) -> str:
    lines: List[str] = []
    for f in schema.spec_fields():
        kw = "、".join(f.search_keywords[:4]) if f.search_keywords else ""
        extra = f"（关键词：{kw}）" if kw else ""
        lines.append(f"- {f.name}：{f.description}{extra}")
    return "\n".join(lines)


def _allowed_field_names(schema: CategorySchema) -> Set[str]:
    return set(schema.field_names())


def _extract_one_snapshot(
    row: SnapshotRow,
    *,
    schema: CategorySchema,
    llm: LLMProvider,
    run_id: str,
    field_names: Set[str],
    system: str,
    only_fields: Optional[Set[str]] = None,
) -> tuple[SnapshotRow, List[Dict[str, Any]], str | None]:
    body = load_snapshot_body(row)
    if not body:
        return row, [], "empty_body"
    verdict = blob_matches_model(f"{row.url}\n{body[:4000]}", row.brand, row.model)
    identity_status = "match" if verdict.ok else "mismatch"
    with transaction() as conn:
        update_snapshot_match(conn, row.snapshot_id, 1 if verdict.ok else 0, identity_status)
    if not verdict.ok:
        return row, [], f"identity:{verdict.reason}"

    try:
        payload = llm.chat_json(
            system,
            extract_snapshot_user(row.brand, row.model, row.url, body),
            ExtractSnapshotPayload,
            temperature=0.1,
            max_tokens=4096,
        )
    except Exception as exc:  # noqa: BLE001
        return row, [], f"llm:{exc}"

    allowed = field_names if not only_fields else (field_names & only_fields)
    records: List[Dict[str, Any]] = []
    with transaction() as conn:
        for item in payload.fields:
            name = (item.name or "").strip()
            value = (item.value or "").strip()
            snippet = (item.snippet or "").strip()
            if name not in allowed or not value or not snippet:
                continue
            aid = new_assertion_id(run_id, row.snapshot_id, name, value)
            insert_field_assertion(
                conn,
                assertion_id=aid,
                device_id=row.device_id,
                field_name=name,
                value_text=value,
                snapshot_id=row.snapshot_id,
                source_id=row.source_id,
                snippet=snippet,
                run_id=run_id,
            )
            records.append(
                {
                    "assertion_id": aid,
                    "device_id": row.device_id,
                    "brand": row.brand,
                    "model": row.model,
                    "field_name": name,
                    "value_text": value,
                    "snippet": snippet,
                    "snapshot_id": row.snapshot_id,
                    "source_id": row.source_id,
                    "source_url": row.url,
                    "source_tier": row.tier,
                    "link_role": row.link_role,
                    "extract_method": "llm_snapshot",
                }
            )
    return row, records, None


def write_assertions_jsonl(
    *,
    run_id: str,
    run_dir: Path,
    category: str,
    schema_fingerprint: str,
) -> Path:
    """Rewrite assertions.jsonl from DB (full dump for the run)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = run_dir / "assertions.jsonl"
    rows = load_assertions_for_run(run_id)
    header = {
        "schema_version": 1,
        "run_id": run_id,
        "category": category,
        "schema_fingerprint": schema_fingerprint,
        "generated_at": utc_now(),
        "input_revision": f"run:{run_id}",
    }
    with jsonl_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({**header, "_type": "manifest"}, ensure_ascii=False) + "\n")
        for a in rows:
            rec = {
                **header,
                "assertion_id": a["assertion_id"],
                "device_id": a["device_id"],
                "brand": a["brand"],
                "model": a["model"],
                "field_name": a["field_name"],
                "value_text": a["value_text"],
                "snippet": a["snippet"],
                "snapshot_id": a["snapshot_id"],
                "source_id": a["source_id"],
                "source_url": a.get("url"),
                "source_tier": a.get("tier"),
                "link_role": a.get("link_role"),
                "extract_method": a.get("extract_method") or "llm_snapshot",
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return jsonl_path


def extract_snapshots(
    *,
    run_id: str,
    run_dir: Path,
    category: str,
    schema: CategorySchema,
    rows: Sequence[SnapshotRow],
    clear_existing: bool = True,
    only_fields: Optional[Set[str]] = None,
    llm: Optional[LLMProvider] = None,
) -> Dict[str, Any]:
    """Run LLM extract on given snapshots. Returns metrics + new records."""
    field_names = _allowed_field_names(schema)
    system = extract_snapshot_system(schema.label_zh, _field_lines(schema))
    provider = llm or LLMProvider(settings)

    if not rows:
        return {
            "snapshots": 0,
            "assertions": 0,
            "new_assertions": 0,
            "skipped_identity": 0,
            "llm_calls": 0,
            "records": [],
            "errors": ["no snapshots to extract"],
        }

    if clear_existing:
        with transaction() as conn:
            clear_assertions_for_run(conn, run_id)

    all_records: List[Dict[str, Any]] = []
    errors: List[str] = []
    skipped_identity = 0
    workers = max(1, settings.extract_max_workers)
    console.log(f"[extract] {len(rows)} snapshots, workers={workers}, clear={clear_existing}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                _extract_one_snapshot,
                row,
                schema=schema,
                llm=provider,
                run_id=run_id,
                field_names=field_names,
                system=system,
                only_fields=only_fields,
            ): row
            for row in rows
        }
        done = 0
        for fut in as_completed(futs):
            row = futs[fut]
            done += 1
            try:
                _, recs, err = fut.result()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{row.snapshot_id}: {exc}")
                continue
            if err:
                if err.startswith("identity:"):
                    skipped_identity += 1
                else:
                    errors.append(f"{row.brand} {row.model} {row.url}: {err}")
            all_records.extend(recs)
            if done % 5 == 0 or done == len(futs):
                console.log(f"[extract] progress {done}/{len(futs)}")

    jsonl_path = write_assertions_jsonl(
        run_id=run_id,
        run_dir=run_dir,
        category=category,
        schema_fingerprint=schema.fingerprint,
    )
    return {
        "snapshots": len(rows),
        "assertions": len(load_assertions_for_run(run_id)),
        "new_assertions": len(all_records),
        "devices_with_assertions": len({r["device_id"] for r in all_records}),
        "skipped_identity": skipped_identity,
        "llm_calls": provider.call_count,
        "records": all_records,
        "errors": errors,
        "assertions_path": str(jsonl_path),
    }


class ExtractStage(Stage):
    name = "extract"

    def prereq(self, ctx: StageContext) -> None:
        if not (settings.openai_api_key or "").strip():
            raise RuntimeError("OPENAI_API_KEY is required for extract")
        manifest = Path(ctx.run_dir) / "collection_manifest.json"
        snaps = load_snapshots_for_run(ctx.run_id, ctx.run_dir)
        if not manifest.exists() and not snaps:
            raise FileNotFoundError(
                f"缺少 collection_manifest.json 或 run={ctx.run_id} 的可抽取快照；请先跑 collect"
            )

    def run(self, ctx: StageContext) -> StageResult:
        schema = load_category_schema(ctx.category, persist=False)
        rows = load_snapshots_for_run(ctx.run_id, ctx.run_dir)
        out = extract_snapshots(
            run_id=ctx.run_id,
            run_dir=Path(ctx.run_dir),
            category=ctx.category,
            schema=schema,
            rows=rows,
            clear_existing=True,
        )
        status = "ok" if out["new_assertions"] or out["assertions"] else "partial"
        return StageResult(
            stage=self.name,
            status=status,
            output_revision=f"extract:{ctx.run_id}:n{out['assertions']}",
            metrics={
                "snapshots": out["snapshots"],
                "assertions": out["assertions"],
                "devices_with_assertions": out.get("devices_with_assertions", 0),
                "skipped_identity": out["skipped_identity"],
                "llm_calls": out["llm_calls"],
            },
            artifacts={"assertions.jsonl": out.get("assertions_path") or ""},
            errors=(out.get("errors") or [])[:30],
        )

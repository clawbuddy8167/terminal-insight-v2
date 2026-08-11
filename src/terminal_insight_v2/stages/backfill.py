"""Stage 3 — Backfill: directed search for missing fields (max N rounds)."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from rich.console import Console

from terminal_insight_v2.category.loader import load_category_schema
from terminal_insight_v2.category.schema import CategorySchema
from terminal_insight_v2.config import settings
from terminal_insight_v2.fetch import fetch_url
from terminal_insight_v2.identity import source_id as make_source_id
from terminal_insight_v2.models.stage import StageContext, StageResult
from terminal_insight_v2.providers.doubao import truncate_query
from terminal_insight_v2.providers.search import resolve_search_provider
from terminal_insight_v2.sourcing.plan_urls import PlannedUrl, tier_for_url
from terminal_insight_v2.stages.base import Stage
from terminal_insight_v2.stages.extract import extract_snapshots
from terminal_insight_v2.store.db import connection, transaction, utc_now
from terminal_insight_v2.store.ledger import set_backfill_round
from terminal_insight_v2.store.repositories import persist_fetch
from terminal_insight_v2.store.snapshots import load_snapshots_by_ids
from terminal_insight_v2.store.wiki import write_raw_snapshot
from terminal_insight_v2.verify.resolution import load_assertions_for_run, load_devices_for_run

console = Console()

# Short keywords to keep Doubao query ≤ 100 chars
FIELD_QUERY_HINTS: Dict[str, str] = {
    "发布时间": "发布日期 上市时间",
    "起售价": "起售价 价格",
    "表壳尺寸与材质": "表壳 尺寸 材质 mm",
    "屏幕显示": "屏幕 显示",
    "续航与充电": "续航 充电",
    "防水等级": "防水 ATM",
    "传感器与健康": "心率 血氧 传感器",
    "系统与连接": "系统 蓝牙 GPS",
    "表带与适配": "表带",
    "核心宣发亮点与差异化功能": "卖点 亮点",
    "防水和防护": "IP防水 防护",
    "核心算力与存储": "处理器 内存 存储 SoC",
    "前沿通信能力": "5G WiFi 蓝牙 NFC",
    "屏幕显示技术": "屏幕 刷新率 分辨率",
    "功耗与续航管理": "电池 mAh 充电",
    "声学与音频": "扬声器 音频",
    "智能传感与交互": "指纹 传感器",
    "AI底层能力": "AI 大模型 端侧",
}


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").replace("www.", "")
    except Exception:
        return ""


def _url_key(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def load_missing_jobs(run_dir: Path, run_id: str) -> List[Dict[str, Any]]:
    """Load (device, missing_fields) from coverage_report or compute from assertions."""
    path = run_dir / "coverage_report.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.get("items") or data.get("coverage") or []
            jobs = []
            for it in items:
                missing = list(it.get("missing_fields") or [])
                if not missing:
                    continue
                jobs.append(
                    {
                        "device_id": it.get("device_id") or "",
                        "brand": it.get("brand") or "",
                        "model": it.get("model") or "",
                        "missing_fields": missing,
                    }
                )
            if jobs:
                return jobs
        except Exception as exc:  # noqa: BLE001
            console.log(f"[backfill] coverage_report unreadable: {exc}")

    # Fallback: all schema fields minus asserted fields
    from terminal_insight_v2.category.loader import load_category_schema as _load

    # category unknown here — caller should have coverage; return empty
    _ = run_id
    return []


def compute_missing_from_db(
    run_id: str,
    schema: CategorySchema,
) -> List[Dict[str, Any]]:
    """Recompute missing fields from DB assertions (proxy before re-verify)."""
    devices = load_devices_for_run(run_id)
    assertions = load_assertions_for_run(run_id)
    have: Dict[str, Set[str]] = {}
    for a in assertions:
        have.setdefault(a["device_id"], set()).add(a["field_name"])
    field_names = [f.name for f in schema.spec_fields()]
    jobs: List[Dict[str, Any]] = []
    for d in devices:
        present = have.get(d["device_id"], set())
        missing = [n for n in field_names if n not in present]
        if missing:
            jobs.append(
                {
                    "device_id": d["device_id"],
                    "brand": d["brand"],
                    "model": d["model"],
                    "missing_fields": missing,
                }
            )
    return jobs


def known_urls_for_device(device_id: str, batch_id: str) -> Set[str]:
    sql = """
      SELECT s.url FROM sources s
      JOIN device_sources ds ON ds.source_id = s.source_id
      WHERE ds.device_id = ? AND ds.batch_id = ?
    """
    with connection(readonly=True) as conn:
        rows = conn.execute(sql, (device_id, batch_id)).fetchall()
    return {_url_key(r["url"]) for r in rows if r["url"]}


def build_backfill_queries(
    brand: str,
    model: str,
    missing_fields: List[str],
    *,
    product: str,
    max_queries: int,
) -> List[Tuple[str, List[str]]]:
    """Return list of (query, fields_targeted)."""
    if not missing_fields:
        return []
    max_q = max(1, max_queries)
    # Prefer fewer broader queries when many fields missing
    if len(missing_fields) <= 2:
        chunks = [[f] for f in missing_fields]
    elif len(missing_fields) <= 5:
        mid = (len(missing_fields) + 1) // 2
        chunks = [missing_fields[:mid], missing_fields[mid:]]
    else:
        # 3 buckets
        n = len(missing_fields)
        a, b = n // 3, (2 * n) // 3
        chunks = [missing_fields[:a], missing_fields[a:b], missing_fields[b:]]

    out: List[Tuple[str, List[str]]] = []
    for chunk in chunks[:max_q]:
        hints = [FIELD_QUERY_HINTS.get(f, f) for f in chunk[:3]]
        hint_str = " ".join(hints)
        parts = [brand, model, product, hint_str, "官方 参数"]
        q = truncate_query(" ".join(p for p in parts if p).strip())
        out.append((q, list(chunk)))
    return out


def _search_urls_for_job(
    job: Dict[str, Any],
    *,
    schema: CategorySchema,
    search,
    known: Set[str],
    max_urls: int,
    max_queries: int,
) -> List[PlannedUrl]:
    product = schema.discovery.product or schema.label_zh or ""
    queries = build_backfill_queries(
        job["brand"],
        job["model"],
        job["missing_fields"],
        product=product,
        max_queries=max_queries,
    )
    seen = set(known)
    planned: List[PlannedUrl] = []
    for q, _fields in queries:
        try:
            body = search.search(q, count=min(8, settings.doubao_max_results))
            hits = search.hits(body)
        except Exception as exc:  # noqa: BLE001
            console.log(f"[backfill] search fail {job['brand']} {job['model']}: {exc}")
            continue
        for hit in hits:
            u = (hit.url or "").strip()
            key = _url_key(u)
            if not u.startswith("http") or key in seen:
                continue
            seen.add(key)
            tier, kind, role = tier_for_url(u, schema)
            # Search clues until body is fetched; keep kind for named sources.
            source_kind = kind if kind != "web" else "search_clue"
            planned.append(
                PlannedUrl(
                    url=u,
                    title=hit.title or "",
                    site=hit.site_name or _host(u),
                    link_role="backfill" if role == "third_party" else role,
                    tier=tier,
                    source_kind=source_kind,
                    discovered_by="backfill",
                )
            )
            if len(planned) >= max_urls:
                return planned
    return planned


def _fetch_one(
    device_id: str,
    plan: PlannedUrl,
    *,
    run_id: str,
) -> Tuple[PlannedUrl, Optional[str], str]:
    fr = fetch_url(plan.url, settings)
    snap_id: Optional[str] = None
    # After successful body fetch, promote search_clue → web
    kind = plan.source_kind
    if fr.content_md and kind == "search_clue":
        kind = "web"
    with transaction() as conn:
        snap_id = persist_fetch(
            conn,
            device_id=device_id,
            url=plan.url,
            link_role=plan.link_role,
            batch_id=run_id,
            tier=plan.tier,
            source_kind=kind,
            fetch_method=fr.fetch_method,
            http_status=fr.http_status,
            final_url=fr.final_url,
            raw_status=fr.raw_status,
            raw_html=fr.raw_html,
            content_md=fr.content_md,
            error=fr.error,
            discovered_by="backfill",
        )
    if snap_id and (fr.content_md or fr.raw_html):
        src_id = make_source_id(plan.url) or "unknown"
        write_raw_snapshot(
            device_id=device_id,
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
                "discovered_by": "backfill",
            },
        )
    status = "ok" if fr.content_md else (fr.raw_status or "failed")
    return plan, snap_id, status


class BackfillStage(Stage):
    name = "backfill"

    def prereq(self, ctx: StageContext) -> None:
        if not (settings.doubao_api_key or "").strip() and not (settings.tavily_api_key or "").strip():
            raise RuntimeError("DOUBAO_API_KEY or TAVILY_API_KEY is required for backfill")
        if not (settings.openai_api_key or "").strip():
            raise RuntimeError("OPENAI_API_KEY is required for backfill (extract)")
        devices = load_devices_for_run(ctx.run_id)
        if not devices:
            raise FileNotFoundError(f"run={ctx.run_id} 无设备；请先跑 collect")

    def run(self, ctx: StageContext) -> StageResult:
        schema = load_category_schema(ctx.category, persist=False)
        run_dir = Path(ctx.run_dir)
        max_rounds = max(0, int(settings.backfill_max_rounds))
        max_urls = max(1, int(settings.backfill_urls_per_device))
        max_queries = max(1, int(settings.backfill_queries_per_device))
        search = resolve_search_provider(settings)

        jobs = load_missing_jobs(run_dir, ctx.run_id)
        if not jobs:
            jobs = compute_missing_from_db(ctx.run_id, schema)

        prev_missing = sum(len(j["missing_fields"]) for j in jobs)
        console.log(f"[backfill] start missing_fields={prev_missing} devices={len(jobs)}")

        if prev_missing == 0 or max_rounds == 0:
            return StageResult(
                stage=self.name,
                status="ok",
                output_revision=f"backfill:{ctx.run_id}:r0",
                metrics={"rounds": 0, "missing_before": 0, "missing_after": 0, "stop_reason": "no_missing"},
            )

        round_logs: List[Dict[str, Any]] = []
        stop_reason = "max_rounds"
        rounds_done = 0
        total_fetched = 0
        total_new_assertions = 0
        errors: List[str] = []

        for round_no in range(1, max_rounds + 1):
            if not jobs:
                stop_reason = "no_missing"
                break

            console.log(
                f"[backfill] round {round_no}/{max_rounds} "
                f"devices={len(jobs)} missing={sum(len(j['missing_fields']) for j in jobs)}"
            )

            # 1) Search → plan new URLs
            device_plans: List[Tuple[Dict[str, Any], List[PlannedUrl]]] = []
            for job in jobs:
                known = known_urls_for_device(job["device_id"], ctx.run_id)
                plans = _search_urls_for_job(
                    job,
                    schema=schema,
                    search=search,
                    known=known,
                    max_urls=max_urls,
                    max_queries=max_queries,
                )
                if plans:
                    device_plans.append((job, plans))

            if not device_plans:
                stop_reason = "no_candidate_urls"
                console.log("[backfill] no new candidate URLs")
                break

            # 2) Fetch new URLs
            new_snap_ids: List[str] = []
            fetch_workers = max(1, settings.collect_fetch_workers)
            fetch_jobs: List[Tuple[str, PlannedUrl]] = [
                (job["device_id"], plan) for job, plans in device_plans for plan in plans
            ]
            with ThreadPoolExecutor(max_workers=fetch_workers) as pool:
                futs = {
                    pool.submit(_fetch_one, did, plan, run_id=ctx.run_id): (did, plan)
                    for did, plan in fetch_jobs
                }
                for fut in as_completed(futs):
                    try:
                        _plan, snap_id, status = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        errors.append(str(exc))
                        continue
                    total_fetched += 1
                    if snap_id and status in ("ok", "markdown_only"):
                        new_snap_ids.append(snap_id)

            console.log(f"[backfill] fetched usable snapshots={len(new_snap_ids)}")

            if not new_snap_ids:
                stop_reason = "no_progress"
                round_logs.append(
                    {
                        "round": round_no,
                        "fetched": total_fetched,
                        "new_snapshots": 0,
                        "new_assertions": 0,
                        "missing_before": prev_missing,
                        "missing_after": prev_missing,
                    }
                )
                break

            # 3) Extract only new snapshots (append)
            rows = load_snapshots_by_ids(new_snap_ids)
            # Focus extract on fields that are still missing across jobs
            only_fields: Set[str] = set()
            for j in jobs:
                only_fields.update(j["missing_fields"])
            out = extract_snapshots(
                run_id=ctx.run_id,
                run_dir=run_dir,
                category=ctx.category,
                schema=schema,
                rows=rows,
                clear_existing=False,
                only_fields=only_fields or None,
            )
            new_n = int(out.get("new_assertions") or 0)
            total_new_assertions += new_n
            errors.extend((out.get("errors") or [])[:10])

            # 4) coverage delta (assertion presence proxy)
            jobs = compute_missing_from_db(ctx.run_id, schema)
            new_missing = sum(len(j["missing_fields"]) for j in jobs)
            delta = prev_missing - new_missing
            console.log(
                f"[backfill] round {round_no}: missing {prev_missing} → {new_missing} "
                f"(delta={delta}, new_assertions={new_n})"
            )
            round_logs.append(
                {
                    "round": round_no,
                    "new_snapshots": len(new_snap_ids),
                    "new_assertions": new_n,
                    "skipped_identity": out.get("skipped_identity", 0),
                    "missing_before": prev_missing,
                    "missing_after": new_missing,
                    "coverage_delta": delta,
                }
            )
            rounds_done = round_no
            set_backfill_round(ctx.run_id, round_no)

            if new_missing == 0:
                stop_reason = "complete"
                prev_missing = 0
                break
            if delta <= 0 and new_n == 0:
                stop_reason = "no_progress"
                prev_missing = new_missing
                break
            if delta <= 0:
                # got assertions but they didn't cover missing (wrong fields / dup)
                stop_reason = "no_progress"
                prev_missing = new_missing
                break
            prev_missing = new_missing
        else:
            if stop_reason == "max_rounds" and rounds_done == max_rounds:
                stop_reason = "max_rounds"

        report = {
            "run_id": ctx.run_id,
            "generated_at": utc_now(),
            "rounds_done": rounds_done,
            "stop_reason": stop_reason,
            "missing_after": prev_missing,
            "total_new_assertions": total_new_assertions,
            "rounds": round_logs,
        }
        report_path = run_dir / "backfill_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        status = "ok" if rounds_done > 0 or stop_reason in ("no_missing", "complete") else "partial"
        return StageResult(
            stage=self.name,
            status=status,
            output_revision=f"backfill:{ctx.run_id}:r{rounds_done}",
            metrics={
                "rounds": rounds_done,
                "stop_reason": stop_reason,
                "missing_after": prev_missing,
                "new_assertions": total_new_assertions,
                "fetched": total_fetched,
            },
            artifacts={"backfill_report.json": str(report_path)},
            errors=errors[:30],
        )

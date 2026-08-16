"""Pipeline orchestrator — stage scheduling + ledger."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from rich.console import Console

from terminal_insight_v2.config import STAGES, settings
from terminal_insight_v2.models import StageContext
from terminal_insight_v2.stages import get_stage
from terminal_insight_v2.store import (
    begin_run,
    ensure_memory_dirs,
    finish_run,
    finish_stage,
    start_stage,
)
from terminal_insight_v2.store.ledger import get_run

console = Console()


def normalize_stages(stages: Sequence[str] | None) -> List[str]:
    if not stages or "all" in stages:
        return list(STAGES)
    wanted = {s.strip() for s in stages if s.strip()}
    unknown = wanted - set(STAGES)
    if unknown:
        raise ValueError(f"未知 stage: {sorted(unknown)}; 可选: {list(STAGES)}")
    return [s for s in STAGES if s in wanted]


def run_pipeline(
    *,
    category: str,
    stages: Sequence[str] | None = None,
    date_start: str = "",
    date_end: str = "",
    schema_fingerprint: str = "pending",
    resume_run_id: Optional[str] = None,
    root: Optional[Path] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, object]:
    """Execute requested stages, recording ledger entries."""
    ensure_memory_dirs(root=root)
    requested = normalize_stages(stages)
    ds = date_start or settings.date_start
    de = date_end or settings.date_end
    cat = category or settings.category

    if resume_run_id:
        meta = get_run(resume_run_id, root=root)
        if not meta:
            raise FileNotFoundError(f"run 不存在: {resume_run_id}")
        run_meta = dict(meta)
        run_id = resume_run_id
    else:
        run_meta = begin_run(
            category=cat,
            schema_fingerprint=schema_fingerprint,
            date_start=ds,
            date_end=de,
            root=root,
        )
        run_id = str(run_meta["run_id"])

    run_dir = settings.data_path() / (run_meta.get("rel_path") or f"runs/{run_id}")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx_extras = dict(extras or {})
    targets = ctx_extras.get("targets")
    if targets:
        from terminal_insight_v2.targets import coerce_targets, write_targets_file

        rows = coerce_targets(targets)
        ctx_extras["targets"] = [t.model_dump() for t in rows]
        write_targets_file(
            run_dir,
            rows,
            category=cat,
            date_start=ds,
            date_end=de,
            mode="targets",
        )
    elif resume_run_id:
        from terminal_insight_v2.targets import load_targets_file

        saved = load_targets_file(run_dir)
        if saved:
            ctx_extras["targets"] = [t.model_dump() for t in saved]
    steps_path = run_dir / "steps.json"
    steps: List[dict] = []
    if steps_path.exists():
        try:
            steps = json.loads(steps_path.read_text(encoding="utf-8"))
            if not isinstance(steps, list):
                steps = []
        except Exception:
            steps = []

    results = []
    failed = False
    for stage_name in requested:
        console.rule(f"[bold cyan]Stage: {stage_name}[/]")
        ctx = StageContext(
            run_id=run_id,
            category=cat,
            schema_fingerprint=str(run_meta.get("schema_fingerprint") or schema_fingerprint),
            backfill_round=int(run_meta.get("backfill_round") or 0),
            date_start=ds,
            date_end=de,
            input_revision=str(run_meta.get("input_revision") or ""),
            run_dir=str(run_dir),
            extras=ctx_extras,
        )
        stage = get_stage(stage_name)
        ledger = start_stage(
            run_id,
            stage_name,
            input_revision=ctx.input_revision or f"run:{run_id}",
            root=root,
        )
        try:
            stage.prereq(ctx)
            result = stage.run(ctx)
            finish_stage(
                ledger["stage_run_id"],
                status=result.status,
                output_revision=result.output_revision,
                error="; ".join(result.errors),
                root=root,
            )
        except Exception as exc:
            finish_stage(
                ledger["stage_run_id"],
                status="failed",
                error=str(exc),
                root=root,
            )
            failed = True
            console.log(f"[red]{stage_name} failed: {exc}[/]")
            break

        entry = {
            "stage": stage_name,
            "status": result.status,
            "attempt": ledger["attempt"],
            "output_revision": result.output_revision,
            "metrics": result.metrics,
            "artifacts": result.artifacts,
            "errors": result.errors,
        }
        steps.append(entry)
        results.append(entry)
        steps_path.write_text(
            json.dumps(steps, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.log(f"[green]{stage_name}[/] → {result.status}")
        if stage_name == "backfill":
            rounds = int((result.metrics or {}).get("rounds") or 0)
            if rounds:
                run_meta["backfill_round"] = rounds

    bf_round = int(run_meta.get("backfill_round") or 0) or None
    finish_run(
        run_id,
        status="failed" if failed else "ok",
        backfill_round=bf_round,
        root=root,
    )
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "failed" if failed else "ok",
        "stages": results,
    }


__all__ = ["normalize_stages", "run_pipeline"]

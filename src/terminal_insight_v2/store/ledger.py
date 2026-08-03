"""Pipeline run / stage run ledger."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from terminal_insight_v2.config import settings

from .db import connection, ensure_memory_dirs, transaction, utc_now


def _ts_run_id(category: str, date_start: str, date_end: str) -> str:
    start = (date_start or "00000000").replace("-", "")
    end = (date_end or "00000000").replace("-", "")
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{category}_{start}-{end}_{stamp}"


def begin_run(
    *,
    category: str,
    schema_fingerprint: str,
    date_start: str = "",
    date_end: str = "",
    input_revision: str = "",
    run_id: Optional[str] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a pipeline_runs row and batch directory. Returns run metadata."""
    ensure_memory_dirs(root=root)
    rid = run_id or _ts_run_id(category, date_start, date_end)
    rel = f"runs/{rid}"
    run_dir = settings.data_path() / rel
    run_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    rev = input_revision or f"run:{rid}"
    meta = {
        "schema_version": 1,
        "run_id": rid,
        "category": category,
        "schema_fingerprint": schema_fingerprint,
        "date_start": date_start,
        "date_end": date_end,
        "status": "running",
        "backfill_round": 0,
        "input_revision": rev,
        "rel_path": rel,
        "created_at": now,
    }
    with transaction(root=root) as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs(
              run_id, category, schema_fingerprint, date_start, date_end,
              status, backfill_round, input_revision, rel_path, created_at
            ) VALUES (?, ?, ?, ?, ?, 'running', 0, ?, ?, ?)
            """,
            (
                rid,
                category,
                schema_fingerprint,
                date_start or None,
                date_end or None,
                rev,
                rel,
                now,
            ),
        )
    (run_dir / "run.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return meta


def start_stage(
    run_id: str,
    stage: str,
    *,
    input_revision: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    with transaction(root=root) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(attempt), 0) AS n FROM stage_runs
            WHERE run_id=? AND stage=?
            """,
            (run_id, stage),
        ).fetchone()
        attempt = int(row["n"]) + 1
        sid = str(uuid.uuid4())
        now = utc_now()
        conn.execute(
            """
            INSERT INTO stage_runs(
              stage_run_id, run_id, stage, status, attempt,
              input_revision, started_at
            ) VALUES (?, ?, ?, 'running', ?, ?, ?)
            """,
            (sid, run_id, stage, attempt, input_revision, now),
        )
    return {
        "stage_run_id": sid,
        "run_id": run_id,
        "stage": stage,
        "attempt": attempt,
        "status": "running",
        "input_revision": input_revision,
        "started_at": now,
    }


def finish_stage(
    stage_run_id: str,
    *,
    status: str,
    output_revision: str = "",
    error: str = "",
    root: Optional[Path] = None,
) -> None:
    with transaction(root=root) as conn:
        conn.execute(
            """
            UPDATE stage_runs
            SET status=?, output_revision=?, error=?, finished_at=?
            WHERE stage_run_id=?
            """,
            (
                status,
                output_revision or None,
                error or None,
                utc_now(),
                stage_run_id,
            ),
        )


def finish_run(
    run_id: str,
    *,
    status: str = "ok",
    backfill_round: Optional[int] = None,
    root: Optional[Path] = None,
) -> None:
    with transaction(root=root) as conn:
        if backfill_round is None:
            conn.execute(
                """
                UPDATE pipeline_runs
                SET status=?, finished_at=?
                WHERE run_id=?
                """,
                (status, utc_now(), run_id),
            )
        else:
            conn.execute(
                """
                UPDATE pipeline_runs
                SET status=?, backfill_round=?, finished_at=?
                WHERE run_id=?
                """,
                (status, int(backfill_round), utc_now(), run_id),
            )
        row = conn.execute(
            "SELECT rel_path FROM pipeline_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    if row and row["rel_path"]:
        run_json = settings.data_path() / row["rel_path"] / "run.json"
        if run_json.exists():
            meta = json.loads(run_json.read_text(encoding="utf-8"))
            meta["status"] = status
            meta["finished_at"] = utc_now()
            if backfill_round is not None:
                meta["backfill_round"] = int(backfill_round)
            run_json.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def get_run(run_id: str, *, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with connection(readonly=True, root=root) as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)


def list_stage_runs(run_id: str, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    with connection(readonly=True, root=root) as conn:
        rows = conn.execute(
            """
            SELECT * FROM stage_runs WHERE run_id=?
            ORDER BY started_at, attempt
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_backfill_round(
    run_id: str,
    round_n: int,
    *,
    root: Optional[Path] = None,
) -> None:
    with transaction(root=root) as conn:
        conn.execute(
            "UPDATE pipeline_runs SET backfill_round=? WHERE run_id=?",
            (int(round_n), run_id),
        )


__all__ = [
    "begin_run",
    "finish_run",
    "finish_stage",
    "get_run",
    "list_stage_runs",
    "set_backfill_round",
    "start_stage",
]

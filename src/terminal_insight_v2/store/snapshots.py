"""Load snapshots and blob bodies for Extract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from terminal_insight_v2.store.blobs import read_blob
from terminal_insight_v2.store.db import connection


@dataclass
class SnapshotRow:
    snapshot_id: str
    source_id: str
    device_id: str
    brand: str
    model: str
    url: str
    tier: str
    link_role: str
    review_status: str
    content_md_blob: str
    raw_status: str
    match_ok: int


def _row_from_sql(r) -> SnapshotRow:
    return SnapshotRow(
        snapshot_id=r["snapshot_id"],
        source_id=r["source_id"],
        device_id=r["device_id"],
        brand=r["brand"],
        model=r["model"],
        url=r["url"],
        tier=r["tier"] or "P3",
        link_role=r["link_role"],
        review_status=r["review_status"],
        content_md_blob=r["content_md_blob"],
        raw_status=r["raw_status"],
        match_ok=int(r["match_ok"] or 0),
    )


_SNAPSHOT_SELECT = """
    SELECT
      s.snapshot_id, s.source_id, s.device_id,
      d.brand, d.model,
      src.url, src.tier,
      ds.link_role, ds.review_status,
      s.content_md_blob, s.raw_status, s.match_ok
    FROM snapshots s
    JOIN devices d ON d.device_id = s.device_id
    JOIN sources src ON src.source_id = s.source_id
    JOIN device_sources ds ON ds.device_id = s.device_id
      AND ds.source_id = s.source_id
"""


def load_snapshots_for_run(run_id: str) -> List[SnapshotRow]:
    """Snapshots collected in this run with usable markdown content."""
    sql = (
        _SNAPSHOT_SELECT
        + """
        WHERE ds.batch_id = ?
          AND ds.review_status NOT IN ('rejected')
          AND src.global_status = 'active'
          AND s.raw_status IN ('ok', 'markdown_only')
          AND s.content_md_blob IS NOT NULL
          AND TRIM(s.content_md_blob) != ''
        ORDER BY s.device_id, s.fetched_at
        """
    )
    with connection(readonly=True) as conn:
        return [_row_from_sql(r) for r in conn.execute(sql, (run_id,)).fetchall()]


def load_snapshots_by_ids(snapshot_ids: List[str]) -> List[SnapshotRow]:
    """Load specific snapshots that have usable markdown content."""
    ids = [s for s in snapshot_ids if s]
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    sql = (
        _SNAPSHOT_SELECT
        + f"""
        WHERE s.snapshot_id IN ({placeholders})
          AND ds.review_status NOT IN ('rejected')
          AND src.global_status = 'active'
          AND s.raw_status IN ('ok', 'markdown_only')
          AND s.content_md_blob IS NOT NULL
          AND TRIM(s.content_md_blob) != ''
        ORDER BY s.device_id, s.fetched_at
        """
    )
    with connection(readonly=True) as conn:
        rows = [_row_from_sql(r) for r in conn.execute(sql, ids).fetchall()]
    # device_sources may have multiple link_roles per source — dedupe by snapshot
    seen: set[str] = set()
    out: List[SnapshotRow] = []
    for row in rows:
        if row.snapshot_id in seen:
            continue
        seen.add(row.snapshot_id)
        out.append(row)
    return out


def load_snapshot_body(row: SnapshotRow, *, max_chars: int = 16000) -> Optional[str]:
    blob_id = (row.content_md_blob or "").strip()
    if not blob_id:
        return None
    with connection(readonly=True) as conn:
        rec = conn.execute(
            "SELECT sha256, rel_path FROM blobs WHERE blob_id=?", (blob_id,)
        ).fetchone()
    if not rec:
        return None
    text = read_blob(rec["sha256"], content_type="text/markdown")
    if not isinstance(text, str) or not text.strip():
        text = read_blob(rec["sha256"], content_type="text/html")
    if not isinstance(text, str):
        return None
    text = text.strip()
    if len(text) > max_chars:
        return text[:max_chars]
    return text

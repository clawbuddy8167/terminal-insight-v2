"""Load snapshots and blob bodies for Extract."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from terminal_insight_v2.store.blobs import read_blob
from terminal_insight_v2.store.db import connection

RunDir = Union[str, Path]


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


def read_collection_manifest(run_dir: Optional[RunDir]) -> Optional[Dict[str, Any]]:
    """Return parsed collection_manifest.json, or None if missing / unusable."""
    if not run_dir:
        return None
    path = Path(run_dir) / "collection_manifest.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def snapshot_ids_from_manifest(run_dir: Optional[RunDir]) -> Optional[List[str]]:
    """Snapshot ids listed for this run.

    ``None`` means the manifest has no membership list (fall back to batch_id).
    An empty list means the run collected devices but no usable snapshot ids.
    """
    man = read_collection_manifest(run_dir)
    if man is None or "devices" not in man or not isinstance(man.get("devices"), list):
        return None
    ids: List[str] = []
    for device in man["devices"]:
        if not isinstance(device, dict):
            continue
        for src in device.get("sources") or []:
            if not isinstance(src, dict):
                continue
            sid = str(src.get("snapshot_id") or "").strip()
            if sid:
                ids.append(sid)
    return ids


def devices_from_manifest(run_dir: Optional[RunDir]) -> Optional[List[Dict[str, Any]]]:
    """Devices listed in this run's collection manifest, or None to fall back."""
    man = read_collection_manifest(run_dir)
    if man is None or "devices" not in man or not isinstance(man.get("devices"), list):
        return None
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for device in man["devices"]:
        if not isinstance(device, dict):
            continue
        did = str(device.get("device_id") or "").strip()
        if not did or did in seen:
            continue
        seen.add(did)
        out.append(
            {
                "device_id": did,
                "brand": device.get("brand") or "",
                "model": device.get("model") or "",
                "release_date": device.get("release_date") or "",
                "status": device.get("status") or "active",
            }
        )
    return out


def urls_from_manifest(run_dir: Optional[RunDir], device_id: str) -> List[str]:
    man = read_collection_manifest(run_dir)
    if man is None or not isinstance(man.get("devices"), list):
        return []
    urls: List[str] = []
    for device in man["devices"]:
        if not isinstance(device, dict) or device.get("device_id") != device_id:
            continue
        for src in device.get("sources") or []:
            if not isinstance(src, dict):
                continue
            url = str(src.get("url") or "").strip()
            if url:
                urls.append(url)
    return urls


def load_snapshots_for_run(
    run_id: str,
    run_dir: Optional[RunDir] = None,
) -> List[SnapshotRow]:
    """Snapshots collected in this run with usable markdown content.

    Prefer ``collection_manifest.json`` snapshot ids so a re-collect of the
    same URL is still visible even when ``device_sources.batch_id`` stayed on
    an older run. Fall back to ``batch_id`` when the manifest has no device list.
    """
    ids = snapshot_ids_from_manifest(run_dir)
    if ids is not None:
        return load_snapshots_by_ids(ids)
    return _load_snapshots_by_batch(run_id)


def _load_snapshots_by_batch(run_id: str) -> List[SnapshotRow]:
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
        rows = [_row_from_sql(r) for r in conn.execute(sql, (run_id,)).fetchall()]
    seen: set[str] = set()
    out: List[SnapshotRow] = []
    for row in rows:
        if row.snapshot_id in seen:
            continue
        seen.add(row.snapshot_id)
        out.append(row)
    return out


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

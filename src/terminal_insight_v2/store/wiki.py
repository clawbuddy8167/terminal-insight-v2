"""llm-wiki path helpers and raw-layer mirror writes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from terminal_insight_v2.store.db import memory_root, utc_now


def slug_id(value: str) -> str:
    return (value or "").replace(":", "_").replace("/", "_")


def wiki_root(*, root: Optional[Path] = None) -> Path:
    return memory_root(root=root) / "llm-wiki"


def raw_snapshot_dir(
    device_id: str,
    source_id: str,
    snapshot_id: str,
    *,
    root: Optional[Path] = None,
) -> Path:
    return (
        wiki_root(root=root)
        / "raw"
        / slug_id(device_id)
        / slug_id(source_id)
        / slug_id(snapshot_id)
    )


def write_raw_snapshot(
    *,
    device_id: str,
    source_id: str,
    snapshot_id: str,
    url: str,
    content_md: str = "",
    raw_html: str = "",
    meta: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
) -> Path:
    """Mirror one collect snapshot under llm-wiki/raw/…"""
    d = raw_snapshot_dir(device_id, source_id, snapshot_id, root=root)
    d.mkdir(parents=True, exist_ok=True)
    if raw_html:
        (d / "raw.html").write_text(raw_html, encoding="utf-8")
    if content_md:
        (d / "content.md").write_text(content_md, encoding="utf-8")
    payload = {
        "schema_version": 1,
        "device_id": device_id,
        "source_id": source_id,
        "snapshot_id": snapshot_id,
        "url": url,
        "written_at": utc_now(),
        **(meta or {}),
    }
    (d / "snapshot.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return d


__all__ = [
    "raw_snapshot_dir",
    "slug_id",
    "wiki_root",
    "write_raw_snapshot",
]

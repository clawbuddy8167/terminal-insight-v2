"""Content-addressed blob store (HTML / JSON / Markdown)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from terminal_insight_v2.identity import blob_id_from_sha, content_sha256

from .db import blobs_dir, connection, memory_root, transaction, utc_now

_EXT = {
    "text/html": "html",
    "application/json": "json",
    "text/markdown": "md",
    "text/plain": "txt",
}


def blob_rel_path(sha256: str, *, content_type: str = "text/markdown") -> str:
    ext = _EXT.get(content_type, "bin")
    return f"blobs/{sha256[:2]}/{sha256}.{ext}"


def blob_abs_path(
    sha256: str,
    *,
    content_type: str = "text/markdown",
    root: Optional[Path] = None,
) -> Path:
    base = memory_root(root=root)
    # Prefer exact typed path; fall back to any extension under prefix.
    typed = base / blob_rel_path(sha256, content_type=content_type)
    if typed.exists():
        return typed
    prefix = base / "blobs" / sha256[:2]
    if prefix.is_dir():
        for p in prefix.glob(f"{sha256}.*"):
            return p
    return typed


def write_blob(
    body: str | bytes,
    *,
    content_type: str = "text/markdown",
    root: Optional[Path] = None,
    persist_db: bool = True,
) -> Tuple[str, str, int, str]:
    """Write content-addressed blob. Returns (blob_id, sha256, byte_size, rel_path)."""
    if isinstance(body, str):
        data = body.encode("utf-8")
        text_for_db = body
    else:
        data = body
        text_for_db = None
    sha = content_sha256(data)
    bid = blob_id_from_sha(sha)
    rel = blob_rel_path(sha, content_type=content_type)
    abs_path = memory_root(root=root) / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    if not abs_path.exists():
        tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, abs_path)
    size = len(data)
    if persist_db:
        with transaction(root=root) as conn:
            conn.execute(
                """
                INSERT INTO blobs(blob_id, sha256, content_type, byte_size, rel_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(blob_id) DO NOTHING
                """,
                (bid, sha, content_type, size, rel, utc_now()),
            )
    return bid, sha, size, rel


def read_blob(
    sha256: str,
    *,
    content_type: str = "text/markdown",
    root: Optional[Path] = None,
    as_bytes: bool = False,
) -> Optional[str | bytes]:
    path = blob_abs_path(sha256, content_type=content_type, root=root)
    if not path.exists():
        with connection(readonly=True, root=root) as conn:
            row = conn.execute(
                "SELECT rel_path FROM blobs WHERE sha256=?", (sha256,)
            ).fetchone()
        if row:
            path = memory_root(root=root) / row["rel_path"]
        if not path.exists():
            return None
    data = path.read_bytes()
    if as_bytes:
        return data
    return data.decode("utf-8", errors="replace")


def ensure_blob_row(
    conn,
    *,
    body: str | bytes,
    content_type: str = "text/markdown",
    root: Optional[Path] = None,
) -> str:
    """Write blob to disk and ensure DB row using an open connection."""
    if isinstance(body, str):
        data = body.encode("utf-8")
    else:
        data = body
    sha = content_sha256(data)
    bid = blob_id_from_sha(sha)
    rel = blob_rel_path(sha, content_type=content_type)
    abs_path = memory_root(root=root) / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    if not abs_path.exists():
        tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, abs_path)
    conn.execute(
        """
        INSERT INTO blobs(blob_id, sha256, content_type, byte_size, rel_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(blob_id) DO NOTHING
        """,
        (bid, sha, content_type, len(data), rel, utc_now()),
    )
    return bid


__all__ = [
    "blob_abs_path",
    "blob_rel_path",
    "blobs_dir",
    "ensure_blob_row",
    "read_blob",
    "write_blob",
]

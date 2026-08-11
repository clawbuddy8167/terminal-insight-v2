"""SQLite persistence for collect stage."""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional
from urllib.parse import urlparse

from terminal_insight_v2.identity import (
    brand_norm,
    canonical_brand,
    device_id,
    model_norm,
    normalize_url,
    source_id as make_source_id,
)
from terminal_insight_v2.models.discovery import DiscoveredDevice
from terminal_insight_v2.store.db import transaction, utc_now
from terminal_insight_v2.store.blobs import ensure_blob_row


def new_snapshot_id(source_id: str) -> str:
    seed = f"{source_id}:{utc_now()}:{uuid.uuid4().hex[:8]}"
    return "snap:" + hashlib.sha256(seed.encode()).hexdigest()[:24]


def upsert_device(
    conn,
    dev: DiscoveredDevice,
    *,
    category: str,
    schema_id: str,
    region: str = "CN",
) -> str:
    did = device_id(category, dev.brand, dev.model, region=region)
    now = utc_now()
    conn.execute(
        """
        INSERT INTO devices(
          device_id, category, brand, brand_norm, model, model_norm,
          region, release_date, status, schema_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
          release_date=excluded.release_date,
          schema_id=excluded.schema_id,
          updated_at=excluded.updated_at
        """,
        (
            did,
            category,
            canonical_brand(dev.brand),
            brand_norm(dev.brand),
            dev.model.strip(),
            model_norm(dev.model),
            region,
            (dev.release_date or "").strip() or None,
            schema_id,
            now,
            now,
        ),
    )
    return did


def upsert_source(conn, url: str, *, tier: str = "web", source_kind: str = "web") -> Optional[str]:
    norm = normalize_url(url)
    sid = make_source_id(norm)
    if not sid:
        return None
    host = urlparse(norm).hostname or ""
    now = utc_now()
    conn.execute(
        """
        INSERT INTO sources(source_id, url, url_norm, host, tier, source_kind, first_seen, last_fetch)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET last_fetch=excluded.last_fetch
        """,
        (sid, url.strip(), norm, host, tier, source_kind, now, now),
    )
    return sid


def link_device_source(
    conn,
    *,
    device_id: str,
    source_id: str,
    link_role: str,
    batch_id: str,
    discovered_by: str = "collect",
) -> None:
    conn.execute(
        """
        INSERT INTO device_sources(
          device_id, source_id, link_role, identity_status, review_status,
          discovered_by, not_available, batch_id
        ) VALUES (?, ?, ?, 'unknown', 'auto', ?, 0, ?)
        ON CONFLICT(device_id, source_id, link_role) DO NOTHING
        """,
        (device_id, source_id, link_role, discovered_by, batch_id),
    )


def insert_snapshot(
    conn,
    *,
    snapshot_id: str,
    source_id: str,
    device_id: str,
    fetch_method: str,
    http_status: int,
    final_url: str,
    raw_status: str,
    raw_html_blob: Optional[str],
    content_md_blob: str,
    content_sha256: str,
    error: str = "",
    match_ok: int = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO snapshots(
          snapshot_id, source_id, device_id, fetched_at, fetch_method,
          http_status, final_url, raw_status, raw_html_blob, content_md_blob,
          content_json_blob, content_sha256, converter_version, error, match_ok
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'collect-mvp/1', ?, ?)
        """,
        (
            snapshot_id,
            source_id,
            device_id,
            utc_now(),
            fetch_method,
            http_status,
            final_url,
            raw_status,
            raw_html_blob,
            content_md_blob,
            content_sha256,
            error or None,
            match_ok,
        ),
    )


def persist_fetch(
    conn,
    *,
    device_id: str,
    url: str,
    link_role: str,
    batch_id: str,
    tier: str,
    source_kind: str,
    fetch_method: str,
    http_status: int,
    final_url: str,
    raw_status: str,
    raw_html: str,
    content_md: str,
    error: str = "",
    discovered_by: str = "collect",
    root=None,
) -> Optional[str]:
    sid = upsert_source(conn, url, tier=tier, source_kind=source_kind)
    if not sid:
        return None
    link_device_source(
        conn,
        device_id=device_id,
        source_id=sid,
        link_role=link_role,
        batch_id=batch_id,
        discovered_by=discovered_by,
    )
    if not content_md and not raw_html:
        snap_id = new_snapshot_id(sid)
        insert_snapshot(
            conn,
            snapshot_id=snap_id,
            source_id=sid,
            device_id=device_id,
            fetch_method=fetch_method,
            http_status=http_status,
            final_url=final_url,
            raw_status="failed",
            raw_html_blob=None,
            content_md_blob="",
            content_sha256="",
            error=error or "fetch failed",
        )
        return snap_id

    html_blob = None
    md_blob = None
    sha = ""
    if raw_html:
        html_blob = ensure_blob_row(conn, body=raw_html, content_type="text/html", root=root)
    if content_md:
        md_blob = ensure_blob_row(conn, body=content_md, content_type="text/markdown", root=root)
        from terminal_insight_v2.identity import content_sha256

        sha = content_sha256(content_md)
    snap_id = new_snapshot_id(sid)
    insert_snapshot(
        conn,
        snapshot_id=snap_id,
        source_id=sid,
        device_id=device_id,
        fetch_method=fetch_method,
        http_status=http_status,
        final_url=final_url,
        raw_status=raw_status,
        raw_html_blob=html_blob,
        content_md_blob=md_blob or "",
        content_sha256=sha,
        error=error,
        match_ok=1 if content_md else 0,
    )
    return snap_id


def clear_assertions_for_run(conn, run_id: str) -> None:
    conn.execute("DELETE FROM field_assertions WHERE run_id=?", (run_id,))


def insert_field_assertion(
    conn,
    *,
    assertion_id: str,
    device_id: str,
    field_name: str,
    value_text: str,
    snapshot_id: str,
    source_id: str,
    snippet: str,
    run_id: str,
    extract_method: str = "llm_snapshot",
    confidence: float | None = None,
) -> None:
    from terminal_insight_v2.identity import content_sha256

    value_norm = (value_text or "").strip()
    if not value_norm or not (snippet or "").strip():
        return
    conn.execute(
        """
        INSERT INTO field_assertions(
          assertion_id, device_id, field_name, value_text, value_norm,
          snapshot_id, source_id, snippet, extract_method, confidence,
          run_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(assertion_id) DO UPDATE SET
          value_text=excluded.value_text,
          snippet=excluded.snippet,
          created_at=excluded.created_at
        """,
        (
            assertion_id,
            device_id,
            field_name,
            value_norm,
            content_sha256(value_norm)[:32],
            snapshot_id,
            source_id,
            snippet.strip()[:2000],
            extract_method,
            confidence,
            run_id,
            utc_now(),
        ),
    )


def update_snapshot_match(conn, snapshot_id: str, match_ok: int, identity_status: str) -> None:
    conn.execute(
        "UPDATE snapshots SET match_ok=? WHERE snapshot_id=?",
        (match_ok, snapshot_id),
    )
    conn.execute(
        """
        UPDATE device_sources SET identity_status=?
        WHERE (device_id, source_id) IN (
          SELECT device_id, source_id FROM snapshots WHERE snapshot_id=?
        )
        """,
        (identity_status, snapshot_id),
    )


def new_assertion_id(run_id: str, snapshot_id: str, field_name: str, value: str) -> str:
    seed = f"{run_id}|{snapshot_id}|{field_name}|{value.strip()}"
    return "asrt:" + hashlib.sha256(seed.encode()).hexdigest()[:24]

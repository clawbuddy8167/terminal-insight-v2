"""Verify helpers: load assertions, write verifications/resolutions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from terminal_insight_v2.store.db import connection, transaction, utc_now
from terminal_insight_v2.store.snapshots import devices_from_manifest


def load_assertions_for_run(run_id: str) -> List[Dict[str, Any]]:
    sql = """
      SELECT
        a.assertion_id, a.device_id, a.field_name, a.value_text, a.snippet,
        a.snapshot_id, a.source_id, a.extract_method, a.confidence,
        d.brand, d.model,
        s.url, s.tier, s.host,
        sn.match_ok, sn.raw_status,
        ds.identity_status, ds.review_status, ds.link_role
      FROM field_assertions a
      JOIN devices d ON d.device_id = a.device_id
      JOIN sources s ON s.source_id = a.source_id
      JOIN snapshots sn ON sn.snapshot_id = a.snapshot_id
      LEFT JOIN device_sources ds
        ON ds.device_id = a.device_id AND ds.source_id = a.source_id
      WHERE a.run_id = ?
        AND COALESCE(ds.review_status, 'auto') NOT IN ('rejected')
        AND s.global_status = 'active'
      ORDER BY a.device_id, a.field_name, a.created_at
    """
    with connection(readonly=True) as conn:
        return [dict(r) for r in conn.execute(sql, (run_id,)).fetchall()]


def load_devices_for_run(
    run_id: str,
    run_dir: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Devices belonging to this run.

    Prefer ``collection_manifest.json`` so a re-collect of the same URLs is
    not dropped when ``device_sources.batch_id`` still points at an older run.
    """
    listed = devices_from_manifest(run_dir)
    if listed is not None:
        return listed
    sql = """
      SELECT DISTINCT d.device_id, d.brand, d.model, d.release_date, d.status
      FROM devices d
      JOIN device_sources ds ON ds.device_id = d.device_id
      WHERE ds.batch_id = ?
      ORDER BY d.brand, d.model
    """
    with connection(readonly=True) as conn:
        return [dict(r) for r in conn.execute(sql, (run_id,)).fetchall()]


def clear_verify_for_run(conn, run_id: str) -> None:
    conn.execute(
        """
        DELETE FROM verifications WHERE assertion_id IN (
          SELECT assertion_id FROM field_assertions WHERE run_id=?
        )
        """,
        (run_id,),
    )
    conn.execute("DELETE FROM resolutions WHERE run_id=?", (run_id,))


def insert_verification(
    conn,
    *,
    assertion_id: str,
    identity_ok: bool,
    evidence_ok: bool,
    accuracy_status: str,
    notes: str = "",
    checker: str = "verify-mvp",
) -> str:
    vid = "ver:" + hashlib.sha256(f"{assertion_id}:{accuracy_status}:{notes}".encode()).hexdigest()[:24]
    conn.execute(
        """
        INSERT INTO verifications(
          verification_id, assertion_id, identity_ok, evidence_ok,
          accuracy_status, notes, checked_at, checker
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(verification_id) DO UPDATE SET
          identity_ok=excluded.identity_ok,
          evidence_ok=excluded.evidence_ok,
          accuracy_status=excluded.accuracy_status,
          notes=excluded.notes,
          checked_at=excluded.checked_at
        """,
        (
            vid,
            assertion_id,
            1 if identity_ok else 0,
            1 if evidence_ok else 0,
            accuracy_status,
            notes or None,
            utc_now(),
            checker,
        ),
    )
    return vid


def upsert_resolution(
    conn,
    *,
    device_id: str,
    field_name: str,
    display_text: str,
    policy: str,
    assertion_ids: List[str],
    conflict: bool,
    run_id: str,
    locked: bool = False,
    locked_value: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO resolutions(
          device_id, field_name, display_text, policy, selected_assertion_ids,
          conflict, locked, locked_value, resolved_at, run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id, field_name, run_id) DO UPDATE SET
          display_text=excluded.display_text,
          policy=excluded.policy,
          selected_assertion_ids=excluded.selected_assertion_ids,
          conflict=excluded.conflict,
          locked=excluded.locked,
          locked_value=excluded.locked_value,
          resolved_at=excluded.resolved_at
        """,
        (
            device_id,
            field_name,
            display_text,
            policy,
            json.dumps(assertion_ids, ensure_ascii=False),
            1 if conflict else 0,
            1 if locked else 0,
            locked_value,
            utc_now(),
            run_id,
        ),
    )


def load_locked_fields(device_id: str) -> Dict[str, str]:
    """Latest lock-field decisions for a device."""
    sql = """
      SELECT field_name, value_text FROM review_decisions
      WHERE device_id=? AND action='lock-field' AND field_name IS NOT NULL
      ORDER BY created_at DESC
    """
    out: Dict[str, str] = {}
    with connection(readonly=True) as conn:
        for r in conn.execute(sql, (device_id,)).fetchall():
            fn = r["field_name"]
            if fn and fn not in out:
                out[fn] = (r["value_text"] or "").strip()
    return out


TIER_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "official": 0, "named": 1, "web": 3}


def resolve_field(
    accepted: List[Dict[str, Any]],
    *,
    conflict_policy: str = "multi_claim",
) -> Tuple[str, str, List[str], bool]:
    """Return display_text, policy, assertion_ids, conflict."""
    if not accepted:
        return "", "missing", [], False
    # Dedup by value_text
    by_value: Dict[str, List[Dict[str, Any]]] = {}
    for a in accepted:
        by_value.setdefault(a["value_text"].strip(), []).append(a)

    if len(by_value) == 1:
        value = next(iter(by_value))
        ids = [a["assertion_id"] for a in accepted]
        return value, "unanimous", ids, False

    if conflict_policy == "prefer_official":
        ranked = sorted(
            accepted,
            key=lambda a: TIER_RANK.get((a.get("tier") or "P3"), 9),
        )
        best = ranked[0]
        return best["value_text"].strip(), "prefer_official", [best["assertion_id"]], True

    # multi_claim default
    parts: List[str] = []
    ids: List[str] = []
    seen_val: set[str] = set()
    for a in accepted:
        val = a["value_text"].strip()
        if val in seen_val:
            continue
        seen_val.add(val)
        label = a.get("host") or a.get("link_role") or a.get("tier") or "信源"
        parts.append(f"{label}：{val}")
        ids.append(a["assertion_id"])
    return "；".join(parts), "multi_claim", ids, True

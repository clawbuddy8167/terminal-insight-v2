"""Re-collecting the same URL must still belong to the new run."""
from __future__ import annotations

import json
from pathlib import Path

from terminal_insight_v2.identity import device_id
from terminal_insight_v2.models.discovery import DiscoveredDevice
from terminal_insight_v2.store import ensure_memory_dirs
from terminal_insight_v2.store.blobs import ensure_blob_row
from terminal_insight_v2.store.db import transaction
from terminal_insight_v2.store.repositories import (
    insert_snapshot,
    link_device_source,
    new_snapshot_id,
    upsert_device,
    upsert_source,
)
from terminal_insight_v2.store.snapshots import load_snapshots_for_run
from terminal_insight_v2.verify.resolution import load_devices_for_run


def _patch_db(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("DATA_ROOT", str(data))
    import terminal_insight_v2.store.db as db_mod
    from terminal_insight_v2.config import Settings

    s = Settings(_env_file=None, data_root=str(data))
    monkeypatch.setattr(db_mod, "settings", s)
    root = ensure_memory_dirs(root=s.memory_root())
    return data, root


def _write_snap(conn, *, did: str, sid: str, url: str, body: str, root) -> str:
    blob_id = ensure_blob_row(conn, body=body, content_type="text/markdown", root=root)
    snap_id = new_snapshot_id(sid)
    insert_snapshot(
        conn,
        snapshot_id=snap_id,
        source_id=sid,
        device_id=did,
        fetch_method="test",
        http_status=200,
        final_url=url,
        raw_status="ok",
        raw_html_blob=None,
        content_md_blob=blob_id,
        content_sha256="x",
        match_ok=1,
    )
    return snap_id


def test_manifest_keeps_recollected_device(tmp_path: Path, monkeypatch):
    data, root = _patch_db(tmp_path, monkeypatch)
    run_a = "phone_old"
    run_b = "phone_new"
    url = "https://www.oppo.com/cn/smartphones/series-a/a7-pro-max/specs/"
    did = device_id("phone", "OPPO", "A7 Pro Max")

    with transaction(root=root) as conn:
        upsert_device(
            conn,
            DiscoveredDevice(brand="OPPO", model="A7 Pro Max"),
            category="phone",
            schema_id="fp",
        )
        sid = upsert_source(conn, url, tier="P1")
        assert sid
        link_device_source(
            conn, device_id=did, source_id=sid, link_role="official", batch_id=run_a
        )
        snap_a = _write_snap(conn, did=did, sid=sid, url=url, body="old " * 40, root=root)
        snap_b = _write_snap(conn, did=did, sid=sid, url=url, body="new " * 40, root=root)

    dir_b = data / "runs" / run_b
    dir_b.mkdir(parents=True)
    (dir_b / "collection_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_b,
                "devices": [
                    {
                        "device_id": did,
                        "brand": "OPPO",
                        "model": "A7 Pro Max",
                        "sources": [{"url": url, "snapshot_id": snap_b}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # batch_id still points at run_a — old query would hide this device from run_b
    assert load_devices_for_run(run_b) == []
    assert [r.snapshot_id for r in load_snapshots_for_run(run_b)] == []

    devices = load_devices_for_run(run_b, run_dir=dir_b)
    assert [d["device_id"] for d in devices] == [did]
    snaps = load_snapshots_for_run(run_b, dir_b)
    assert [r.snapshot_id for r in snaps] == [snap_b]
    assert snap_a not in {r.snapshot_id for r in snaps}


def test_empty_manifest_falls_back_to_batch_id(tmp_path: Path, monkeypatch):
    data, root = _patch_db(tmp_path, monkeypatch)
    run_id = "run-fallback"
    url = "https://example.com/spec"
    did = device_id("phone", "Redmi", "Note 17 Pro")

    with transaction(root=root) as conn:
        upsert_device(
            conn,
            DiscoveredDevice(brand="Redmi", model="Note 17 Pro"),
            category="phone",
            schema_id="fp",
        )
        sid = upsert_source(conn, url, tier="P3")
        assert sid
        link_device_source(
            conn, device_id=did, source_id=sid, link_role="third_party", batch_id=run_id
        )
        snap = _write_snap(conn, did=did, sid=sid, url=url, body="body " * 40, root=root)

    run_dir = data / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "collection_manifest.json").write_text("{}", encoding="utf-8")

    assert [d["device_id"] for d in load_devices_for_run(run_id, run_dir=run_dir)] == [did]
    assert [r.snapshot_id for r in load_snapshots_for_run(run_id, run_dir)] == [snap]

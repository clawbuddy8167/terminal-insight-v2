"""Verify + Excel stage tests."""
from __future__ import annotations

import json
from pathlib import Path

from terminal_insight_v2.identity import device_id
from terminal_insight_v2.models.discovery import DiscoveredDevice
from terminal_insight_v2.models.stage import StageContext
from terminal_insight_v2.store import ensure_memory_dirs
from terminal_insight_v2.store.db import transaction
from terminal_insight_v2.store.repositories import (
    insert_field_assertion,
    insert_snapshot,
    link_device_source,
    new_assertion_id,
    new_snapshot_id,
    upsert_device,
    upsert_source,
)
from terminal_insight_v2.stages.excel_stage import ExcelStage
from terminal_insight_v2.stages.verify import VerifyStage
from terminal_insight_v2.verify.validators import snippet_supports_value


def test_snippet_supports_value():
    ok, _ = snippet_supports_value("续航约 14 天", "14天")
    assert ok


def test_verify_and_excel(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("DATA_ROOT", str(data))
    monkeypatch.setenv(
        "TEMPLATE_DIR",
        str(Path(__file__).resolve().parents[1] / "category_templates"),
    )

    import terminal_insight_v2.stages.verify as verify_mod
    import terminal_insight_v2.exporters.excel as excel_mod
    import terminal_insight_v2.store.db as db_mod
    from terminal_insight_v2.config import Settings

    s = Settings(_env_file=None, data_root=str(data), openai_api_key="x")
    monkeypatch.setattr(verify_mod, "settings", s) if hasattr(verify_mod, "settings") else None
    monkeypatch.setattr(excel_mod, "settings", s)
    monkeypatch.setattr(db_mod, "settings", s)
    root = ensure_memory_dirs(root=s.memory_root())

    run_id = "run-verify-1"
    did = device_id("watch", "Garmin", "Forerunner 70")
    with transaction(root=root) as conn:
        upsert_device(
            conn,
            DiscoveredDevice(brand="Garmin", model="Forerunner 70", release_date="2026-03-01"),
            category="watch",
            schema_id="fp",
        )
        sid = upsert_source(conn, "https://example.com/fr70", tier="P2")
        assert sid
        link_device_source(
            conn, device_id=did, source_id=sid, link_role="named", batch_id=run_id
        )
        snap = new_snapshot_id(sid)
        insert_snapshot(
            conn,
            snapshot_id=snap,
            source_id=sid,
            device_id=did,
            fetch_method="test",
            http_status=200,
            final_url="https://example.com/fr70",
            raw_status="markdown_only",
            raw_html_blob=None,
            content_md_blob="blob:x",
            content_sha256="x",
            match_ok=1,
        )
        aid = new_assertion_id(run_id, snap, "续航与充电", "最长14天")
        insert_field_assertion(
            conn,
            assertion_id=aid,
            device_id=did,
            field_name="续航与充电",
            value_text="最长14天",
            snapshot_id=snap,
            source_id=sid,
            snippet="续航最长14天，日常使用",
            run_id=run_id,
        )

    run_dir = data / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "assertions.jsonl").write_text("{}\n", encoding="utf-8")

    ctx = StageContext(
        run_id=run_id,
        category="watch",
        schema_fingerprint="fp",
        date_start="2026-01-01",
        date_end="2026-07-31",
        run_dir=str(run_dir),
    )
    v = VerifyStage().run(ctx)
    assert v.status == "ok"
    assert (run_dir / "resolved.json").exists()
    assert (run_dir / "coverage_report.json").exists()

    e = ExcelStage().run(ctx)
    assert e.status == "ok"
    xlsx = Path(e.artifacts["excel"])
    assert xlsx.exists()
    cov = json.loads((run_dir / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["items"][0]["brand"] == "Garmin"

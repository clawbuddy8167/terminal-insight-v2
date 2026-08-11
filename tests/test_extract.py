"""Extract stage tests."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from terminal_insight_v2.identity import device_id
from terminal_insight_v2.models.extraction import ExtractSnapshotPayload, ExtractedField
from terminal_insight_v2.models.stage import StageContext
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
from terminal_insight_v2.models.discovery import DiscoveredDevice
from terminal_insight_v2.stages.extract import ExtractStage


def test_extract_stage_mocked(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("DATA_ROOT", str(data))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("TEMPLATE_DIR", str(Path(__file__).resolve().parents[1] / "category_templates"))

    import terminal_insight_v2.stages.extract as extract_mod
    import terminal_insight_v2.store.db as db_mod

    s = extract_mod.settings.__class__(
        _env_file=None,
        data_root=str(data),
        openai_api_key="test-key",
        extract_max_workers=1,
    )
    monkeypatch.setattr(extract_mod, "settings", s)
    monkeypatch.setattr(db_mod, "settings", s)
    root = ensure_memory_dirs(root=s.memory_root())

    run_id = "run-extract-1"
    did = device_id("glasses", "雷鸟", "V4")
    with transaction(root=root) as conn:
        upsert_device(
            conn,
            DiscoveredDevice(brand="雷鸟", model="V4"),
            category="glasses",
            schema_id="fp",
        )
        sid = upsert_source(conn, "https://example.com/spec", tier="P3")
        assert sid
        link_device_source(conn, device_id=did, source_id=sid, link_role="third_party", batch_id=run_id)
        body = "雷鸟 V4 智能眼镜 起售价 4299元 重量 38g " * 20
        blob_id = ensure_blob_row(conn, body=body, content_type="text/markdown", root=root)
        snap_id = new_snapshot_id(sid)
        insert_snapshot(
            conn,
            snapshot_id=snap_id,
            source_id=sid,
            device_id=did,
            fetch_method="test",
            http_status=200,
            final_url="https://example.com/spec",
            raw_status="markdown_only",
            raw_html_blob=None,
            content_md_blob=blob_id,
            content_sha256="abc",
            match_ok=1,
        )

    run_dir = data / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "collection_manifest.json").write_text("{}", encoding="utf-8")

    ctx = StageContext(
        run_id=run_id,
        category="glasses",
        schema_fingerprint="fp",
        date_start="2026-01-01",
        date_end="2026-07-31",
        run_dir=str(run_dir),
    )

    payload = ExtractSnapshotPayload(
        fields=[
            ExtractedField(name="起售价", value="4299元", snippet="起售价 4299元"),
            ExtractedField(name="重量", value="38g", snippet="重量 38g"),
        ]
    )

    mock_schema = MagicMock()
    mock_schema.fingerprint = "fp"
    mock_schema.label_zh = "智能眼镜"
    mock_schema.field_names.return_value = ["品牌", "机型", "起售价", "重量"]
    mock_schema.spec_fields.return_value = []

    with (
        patch("terminal_insight_v2.stages.extract.load_category_schema", return_value=mock_schema),
        patch("terminal_insight_v2.providers.llm.LLMProvider.chat_json", return_value=payload),
    ):
        result = ExtractStage().run(ctx)

    assert result.status == "ok"
    assert result.metrics["assertions"] >= 2
    lines = (run_dir / "assertions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 3  # manifest + assertions
    rec = json.loads(lines[1])
    assert rec["field_name"] == "起售价"

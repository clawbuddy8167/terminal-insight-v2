"""Collect stage tests (mocked network)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from terminal_insight_v2.fetch.simple import FetchResult
from terminal_insight_v2.models.discovery import DiscoveredDevice
from terminal_insight_v2.models.stage import StageContext
from terminal_insight_v2.sourcing.plan_urls import PlannedUrl, plan_urls_for_device
from terminal_insight_v2.stages.collect import CollectStage


@pytest.fixture
def memory_root(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("DOUBAO_API_KEY", "test-doubao")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    from terminal_insight_v2.config import Settings

    return Settings().memory_root()


def test_plan_urls_dedup(monkeypatch):
    monkeypatch.setenv("DOUBAO_API_KEY", "k")
    from terminal_insight_v2.config import Settings
    from terminal_insight_v2.category.schema import CategorySchema, DiscoveryConfig, FieldDef

    schema = CategorySchema(
        category_id="glasses",
        label_zh="智能眼镜",
        template_version="1",
        discovery=DiscoveryConfig(product="智能眼镜"),
        fields=[
            FieldDef(name="品牌", description="d", example="x"),
        ],
        output_columns=[],
    )
    dev = DiscoveredDevice(
        brand="雷鸟",
        model="V4",
        discovery_sources=["https://example.com/a", "https://example.com/a"],
    )
    doubao = MagicMock()
    doubao.search.return_value = {"Result": {"WebResults": []}}
    doubao.hits.return_value = []
    settings = Settings(collect_max_urls_per_device=5)
    urls = plan_urls_for_device(dev, schema, settings, search=doubao)
    assert len(urls) == 1
    assert urls[0].url == "https://example.com/a"


def test_collect_stage_mocked(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("DATA_ROOT", str(data))
    monkeypatch.setenv("DOUBAO_API_KEY", "test-doubao")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("TEMPLATE_DIR", str(Path(__file__).resolve().parents[1] / "category_templates"))

    from terminal_insight_v2.config import Settings
    from terminal_insight_v2.store import ensure_memory_dirs
    import terminal_insight_v2.stages.collect as collect_mod
    import terminal_insight_v2.store.db as db_mod

    s = Settings()
    monkeypatch.setattr(collect_mod, "settings", s)
    monkeypatch.setattr(db_mod, "settings", s)

    ensure_memory_dirs(root=s.memory_root())
    run_dir = data / "runs" / "test-run"
    run_dir.mkdir(parents=True)

    ctx = StageContext(
        run_id="test-run",
        category="glasses",
        schema_fingerprint="fp",
        date_start="2026-01-01",
        date_end="2026-07-31",
        run_dir=str(run_dir),
    )
    devices = [DiscoveredDevice(brand="雷鸟", model="V4", category="glasses")]
    planned = [
        PlannedUrl(url="https://example.com/spec", link_role="third_party", tier="P3"),
    ]
    fetch_result = FetchResult(
        url="https://example.com/spec",
        final_url="https://example.com/spec",
        http_status=200,
        fetch_method="http_get",
        content_md="雷鸟 V4 参数内容 " * 40,
        raw_status="markdown_only",
    )

    planned_url = planned[0]
    mock_fetch_return = (planned_url, fetch_result, "snap:test123", "llm-wiki/raw/dev/src/snap")

    with (
        patch("terminal_insight_v2.stages.collect.load_category_schema") as load_schema,
        patch("terminal_insight_v2.stages.collect.discover_devices", return_value=(devices, [])),
        patch("terminal_insight_v2.stages.collect.plan_urls_for_device", return_value=planned),
        patch("terminal_insight_v2.stages.collect._fetch_and_persist", return_value=mock_fetch_return),
        patch("terminal_insight_v2.stages.collect.upsert_device", return_value="glasses:雷鸟:v4"),
    ):
        mock_schema = MagicMock()
        mock_schema.fingerprint = "abc123"
        mock_schema.category_id = "glasses"
        load_schema.return_value = mock_schema

        result = CollectStage().run(ctx)

    assert result.status in ("ok", "partial")
    manifest = json.loads((run_dir / "collection_manifest.json").read_text(encoding="utf-8"))
    assert manifest["devices"][0]["brand"] == "雷鸟"
    assert manifest["devices"][0]["sources"][0]["snapshot_id"] == "snap:test123"
    assert (run_dir / "sources.html").exists()

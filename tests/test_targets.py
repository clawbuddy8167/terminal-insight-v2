"""Targeted collect parse + collect skip-discovery."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from terminal_insight_v2.models.stage import StageContext
from terminal_insight_v2.sourcing.plan_urls import PlannedUrl
from terminal_insight_v2.stages.collect import CollectStage
from terminal_insight_v2.targets import parse_targets
from terminal_insight_v2.fetch.simple import FetchResult


def test_parse_target_text_formats_and_dedupe():
    text = """
# comment
品类: phone
2026-07-01~2026-08-11
华为 | Mate X7
OPPO, Find X9 Ultra
小米\t17 Pro Max
huawei Mate X7
MateX7
"""
    result = parse_targets(text)
    pairs = [(t.brand, t.model) for t in result.targets]
    assert ("华为", "Mate X7") in pairs
    assert ("OPPO", "Find X9 Ultra") in pairs
    assert ("小米", "17 Pro Max") in pairs
    assert len([p for p in pairs if p[1] == "Mate X7"]) == 1
    assert any(e.reason == "缺少型号" for e in result.errors)


def test_collect_targets_skips_discovery(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("DATA_ROOT", str(data))
    monkeypatch.setenv("DOUBAO_API_KEY", "test-doubao")
    monkeypatch.setenv("TEMPLATE_DIR", str(Path(__file__).resolve().parents[1] / "category_templates"))

    from terminal_insight_v2.config import Settings
    from terminal_insight_v2.store import ensure_memory_dirs
    import terminal_insight_v2.stages.collect as collect_mod
    import terminal_insight_v2.store.db as db_mod

    s = Settings(_env_file=None, data_root=str(data), doubao_api_key="test-doubao", openai_api_key="")
    monkeypatch.setattr(collect_mod, "settings", s)
    monkeypatch.setattr(db_mod, "settings", s)
    monkeypatch.setattr(collect_mod, "resolve_search_provider", lambda _s: MagicMock(call_count=0))
    monkeypatch.setattr(collect_mod, "LLMProvider", lambda _s: MagicMock(call_count=0))
    ensure_memory_dirs(root=s.memory_root())
    run_dir = data / "runs" / "target-run"
    run_dir.mkdir(parents=True)

    ctx = StageContext(
        run_id="target-run",
        category="phone",
        schema_fingerprint="fp",
        date_start="2026-07-01",
        date_end="2026-08-11",
        run_dir=str(run_dir),
        extras={"targets": [{"brand": "华为", "model": "Mate X7"}]},
    )
    planned = [PlannedUrl(url="https://example.com/mate", link_role="third_party", tier="P3")]
    fetch_result = FetchResult(
        url="https://example.com/mate",
        final_url="https://example.com/mate",
        http_status=200,
        fetch_method="http_get",
        content_md="华为 Mate X7 参数 " * 40,
        raw_status="markdown_only",
    )
    mock_fetch = (planned[0], fetch_result, "snap:t1", "llm-wiki/raw/x")

    with (
            patch("terminal_insight_v2.stages.collect.load_category_schema") as load_schema,
            patch("terminal_insight_v2.stages.collect.discover_devices") as discover,
        patch("terminal_insight_v2.stages.collect.plan_urls_for_device", return_value=planned),
        patch("terminal_insight_v2.stages.collect._fetch_and_persist", return_value=mock_fetch),
        patch("terminal_insight_v2.stages.collect.upsert_device", return_value="phone:huawei:matex7"),
    ):
        mock_schema = MagicMock()
        mock_schema.fingerprint = "fp"
        mock_schema.category_id = "phone"
        load_schema.return_value = mock_schema
        result = CollectStage().run(ctx)

    discover.assert_not_called()
    assert result.metrics.get("collect_mode") == "targets"
    assert result.metrics.get("llm_calls") == 0
    manifest = json.loads((run_dir / "collection_manifest.json").read_text(encoding="utf-8"))
    assert manifest["devices"][0]["brand"] == "华为"
    assert manifest["devices"][0]["model"] == "Mate X7"


def test_gui_parse_targets():
    from terminal_insight_v2.gui.api import GuiApi

    res = GuiApi().parse_targets("荣耀 | 600 Pro\n只有品牌")
    assert res["ok"]
    assert res["targets"][0]["brand"] == "荣耀"
    assert res["targets"][0]["model"] == "600 Pro"
    assert res["errors"]

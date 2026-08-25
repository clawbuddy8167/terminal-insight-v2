"""Vote + hypothesis mapping integration."""
from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook

from terminal_insight_v2.hypothesis.models import HypothesisMappingPayload, HypothesisMappingDraft
from terminal_insight_v2.models.stage import StageContext
from terminal_insight_v2.vote.api import run_vote
from terminal_insight_v2.vote.excel_write import HYPOTHESIS_HEADERS, HYPOTHESIS_SHEET_NAME
from terminal_insight_v2.vote.models import (
    AudienceAssessmentDraft,
    AudienceReviewPayload,
    ClusterDraft,
    ClusterPayload,
    HotspotRationale,
    HotspotVote,
    VOTER_IDS,
    VoterBallotPayload,
)


class FakeLLM:
    def __init__(self, *, map_hypotheses: bool = False) -> None:
        self.call_count = 0
        self.map_hypotheses = map_hypotheses

    def chat_json(self, system: str, user: str, model, **kwargs):
        self.call_count += 1
        name = getattr(model, "__name__", "")
        if name == "ClusterPayload":
            return ClusterPayload(
                clusters=[
                    ClusterDraft(direction="高端影像升级", hotspot_ids=[1, 3, 5, 7, 9, 11]),
                    ClusterDraft(
                        direction="超大容量电池与长续航", hotspot_ids=[2, 4, 6, 8, 10, 12]
                    ),
                ]
            )
        if name == "AudienceReviewPayload":
            return AudienceReviewPayload(
                assessments=[
                    AudienceAssessmentDraft(
                        hotspot_index=1,
                        relevance=3,
                        why_it_matters="影像",
                        action_implication="跟进",
                        caveat="",
                    ),
                    AudienceAssessmentDraft(
                        hotspot_index=2,
                        relevance=2,
                        why_it_matters="续航",
                        action_implication="核对",
                        caveat="",
                    ),
                ]
            )
        if name == "HypothesisMappingPayload":
            if not self.map_hypotheses:
                return HypothesisMappingPayload(mappings=[])
            return HypothesisMappingPayload(
                mappings=[
                    HypothesisMappingDraft(
                        hypothesis_id="H1",
                        hotspot_index=1,
                        stance="support",
                        note="影像旗舰",
                    ),
                    HypothesisMappingDraft(
                        hypothesis_id="H4",
                        hotspot_index=2,
                        stance="support",
                        note="大电池",
                    ),
                ]
            )
        voter = next((vid for vid in VOTER_IDS if f"热点投票人 {vid}" in system), "AAA")
        return VoterBallotPayload(
            hotspots=[
                HotspotVote(
                    title=f"{voter}-影像",
                    brand="OPPO",
                    model="Find X9 Ultra",
                    rationale=HotspotRationale(innovation="10倍光变"),
                    axis_tags=[voter],
                ),
                HotspotVote(
                    title=f"{voter}-续航",
                    brand="小米",
                    model="17 Max",
                    rationale=HotspotRationale(user="8000mAh 电池"),
                    axis_tags=[voter],
                ),
            ]
        )


def _resolved_payload() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-hypo-1",
        "category": "phone",
        "input_revision": "verify:run-hypo-1",
        "items": [
            {
                "device_id": "phone:oppo:findx9ultra",
                "brand": "OPPO",
                "model": "Find X9 Ultra",
                "field_name": "屏幕显示技术",
                "display_text": "2K 120Hz",
                "policy": "unanimous",
            },
            {
                "device_id": "phone:xiaomi:17max",
                "brand": "小米",
                "model": "17 Max",
                "field_name": "功耗与续航管理",
                "display_text": "8000mAh 金沙江电池",
                "policy": "unanimous",
            },
        ],
    }


def _patch_settings(monkeypatch, tmp_path: Path):
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.vote.api as vote_api
    import terminal_insight_v2.hypothesis.loader as hypo_loader

    s = Settings(
        _env_file=None,
        data_root=str(tmp_path / "data"),
        openai_api_key="test-key",
    )
    monkeypatch.setattr(vote_api, "settings", s)
    monkeypatch.setattr(hypo_loader, "settings", s)
    return s


def test_vote_skips_hypothesis_llm_when_no_catalog(tmp_path: Path, monkeypatch):
    _patch_settings(monkeypatch, tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "resolved.json").write_text(
        json.dumps(_resolved_payload(), ensure_ascii=False), encoding="utf-8"
    )
    ctx = StageContext(
        run_id="run-hypo-1",
        category="phone",
        schema_fingerprint="fp",
        input_revision="verify:run-hypo-1",
        run_dir=str(run_dir),
    )
    llm = FakeLLM()
    result = run_vote(ctx, llm=llm)
    assert result.status == "ok"
    assert llm.call_count == 11
    assert result.metrics["hypothesis_mappings"] == 0
    assert result.metrics["hypotheses_loaded"] == 0
    data = json.loads((run_dir / "votes.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 4
    assert data["hypothesis_reviews"] == []


def test_vote_maps_hypotheses_and_excel(tmp_path: Path, monkeypatch):
    _patch_settings(monkeypatch, tmp_path)
    catalog = tmp_path / "hypo.json"
    catalog.write_text(
        json.dumps(
            {
                "year": 2026,
                "category": "phone",
                "source": "test",
                "hypotheses": [
                    {"id": "H1", "statement": "L3 下探"},
                    {"id": "H4", "statement": "续航转向能效"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "resolved.json").write_text(
        json.dumps(_resolved_payload(), ensure_ascii=False), encoding="utf-8"
    )
    ctx = StageContext(
        run_id="run-hypo-1",
        category="phone",
        schema_fingerprint="fp",
        input_revision="verify:run-hypo-1",
        run_dir=str(run_dir),
        extras={"hypotheses_path": str(catalog)},
    )
    llm = FakeLLM(map_hypotheses=True)
    result = run_vote(ctx, llm=llm)
    assert result.status == "ok"
    assert llm.call_count == 12
    assert result.metrics["hypothesis_mappings"] == 2
    data = json.loads((run_dir / "votes.json").read_text(encoding="utf-8"))
    assert data["hypothesis_reviews"][0]["hypothesis_id"] == "H1"
    assert data["hypothesis_reviews"][0]["stance"] == "support"
    wb = load_workbook(result.artifacts["excel"])
    hws = wb[HYPOTHESIS_SHEET_NAME]
    assert [c.value for c in hws[1]] == HYPOTHESIS_HEADERS
    assert hws.max_row == 3
    assert hws.cell(2, 1).value == "H1"

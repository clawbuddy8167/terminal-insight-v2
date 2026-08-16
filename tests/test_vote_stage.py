"""Vote stage: mocked LLM ballots → votes.json + Excel sheet."""
from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook

from terminal_insight_v2.models.stage import StageContext
from terminal_insight_v2.vote.api import run_vote
from terminal_insight_v2.vote.excel_write import HEADERS, SHEET_NAME
from terminal_insight_v2.vote.models import (
    ClusterDraft,
    ClusterPayload,
    HotspotRationale,
    HotspotVote,
    VOTER_IDS,
    VoterBallot,
    VoterBallotPayload,
)
from terminal_insight_v2.vote.service import _heuristic_clusters, flatten_hotspots


class FakeLLM:
    def __init__(self) -> None:
        self.call_count = 0

    def chat_json(self, system: str, user: str, model, **kwargs):
        self.call_count += 1
        name = getattr(model, "__name__", "")
        if name == "ClusterPayload":
            return ClusterPayload(
                clusters=[
                    ClusterDraft(direction="高端影像升级", hotspot_ids=[1, 3, 5, 7, 9, 11]),
                    ClusterDraft(direction="超大容量电池与长续航", hotspot_ids=[2, 4, 6, 8, 10, 12]),
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
        "run_id": "run-vote-1",
        "category": "phone",
        "input_revision": "verify:run-vote-1",
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


def test_vote_stage_writes_votes_and_excel(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.vote.api as vote_api

    s = Settings(_env_file=None, data_root=str(tmp_path / "data"), openai_api_key="test-key")
    monkeypatch.setattr(vote_api, "settings", s)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "resolved.json").write_text(
        json.dumps(_resolved_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    ctx = StageContext(
        run_id="run-vote-1",
        category="phone",
        schema_fingerprint="fp",
        date_start="2026-07-01",
        date_end="2026-08-11",
        input_revision="verify:run-vote-1",
        run_dir=str(run_dir),
    )
    result = run_vote(ctx, llm=FakeLLM())
    assert result.status == "ok"
    assert result.metrics["voters"] == 6
    assert result.metrics["hotspots"] == 12
    assert result.metrics["clusters"] == 2

    data = json.loads((run_dir / "votes.json").read_text(encoding="utf-8"))
    assert [v["voter_id"] for v in data["voters"]] == list(VOTER_IDS)
    assert data["voters"][0]["frame_name"] == "路线标尺"
    assert data["voters"][0]["reference_frame"]
    assert data["voters"][0]["hotspots"][0]["axis_tags"] == ["AAA"]
    assert data["clusters"][0]["voter_ids"]
    assert data["clusters"][0]["axes_preserved"][0]["lens"]

    wb = load_workbook(result.artifacts["excel"])
    ws = wb[SHEET_NAME]
    assert [c.value for c in ws[1]] == HEADERS
    assert ws.max_row == 13
    assert ws.cell(2, 1).value == data["voters"][0]["reference_frame"]
    assert ws.cell(2, 2).value == data["voters"][0]["framing"]


def test_heuristic_clusters_keep_axes():
    ballots = [
        VoterBallot(
            voter_id="AAA",
            reference_frame="产业范式 / 技术路线分岔",
            framing="赛道",
            hotspots=[
                HotspotVote(
                    title="长焦双路线",
                    brand="华为",
                    model="Pura 90",
                    rationale=HotspotRationale(innovation="影像范式"),
                )
            ],
        ),
        VoterBallot(
            voter_id="CCC",
            reference_frame="硬规格 × 价位带",
            framing="价位",
            hotspots=[
                HotspotVote(
                    title="2000元万级电池",
                    brand="vivo",
                    model="Y600 Pro",
                    rationale=HotspotRationale(innovation="续航下沉"),
                )
            ],
        ),
    ]
    clusters = _heuristic_clusters(flatten_hotspots(ballots))
    names = {c.direction for c in clusters}
    assert "高端影像升级" in names
    assert "超大容量电池与长续航" in names
    by_dir = {c.direction: c for c in clusters}
    assert by_dir["高端影像升级"].voter_ids == ["AAA"]
    assert by_dir["高端影像升级"].axes_preserved[0].lens == "路线对垒"
    assert by_dir["超大容量电池与长续航"].voter_ids == ["CCC"]

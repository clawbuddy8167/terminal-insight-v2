"""Audience review: fixed profiles, sanitization, partial failure."""
from __future__ import annotations

import json
from pathlib import Path

from terminal_insight_v2.models.stage import StageContext
from terminal_insight_v2.vote.api import run_vote
from terminal_insight_v2.vote.audience_profiles import AUDIENCE_PROFILES, audience_for
from terminal_insight_v2.vote.audience_prompts import (
    audience_system,
    number_hotspots_for_audience,
)
from terminal_insight_v2.vote.audience_service import collect_audience_reviews
from terminal_insight_v2.vote.models import (
    AUDIENCE_IDS,
    AudienceAssessmentDraft,
    AudienceReviewPayload,
    HotspotRationale,
    HotspotVote,
    VotesArtifact,
    VoterBallot,
)
from terminal_insight_v2.vote.service import cluster_hotspots, flatten_hotspots

from test_vote_stage import FakeLLM, _resolved_payload


def _ballots() -> list[VoterBallot]:
    return [
        VoterBallot(
            voter_id="AAA",
            frame_name="路线标尺",
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
            frame_name="价位规格",
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


def test_four_fixed_audience_profiles():
    assert tuple(p.audience_id for p in AUDIENCE_PROFILES) == AUDIENCE_IDS
    for profile in AUDIENCE_PROFILES:
        assert profile.name
        assert profile.decision_question
        assert profile.forbidden
        assert audience_for(profile.audience_id) is profile


def test_audience_prompt_forbids_external_facts():
    entries = flatten_hotspots(_ballots())
    text = audience_system(audience_for("REG"), "phone")
    assert "不提名新热点" in text
    assert "hotspot_index" in text
    assert "不要新增热点、机型、销量、政策文件或外部数字" in text
    listing = "\n".join(number_hotspots_for_audience(entries, _ballots()))
    assert "1." in listing
    assert "长焦双路线" in listing


def test_sanitize_drops_bad_index_score_and_dupes():
    entries = flatten_hotspots(_ballots())

    class DirtyLLM:
        call_count = 0

        def chat_json(self, system, user, model, **kwargs):
            self.call_count += 1
            return AudienceReviewPayload(
                assessments=[
                    AudienceAssessmentDraft(hotspot_index=1, relevance=3, why_it_matters="ok"),
                    AudienceAssessmentDraft(hotspot_index=1, relevance=2, why_it_matters="dup"),
                    AudienceAssessmentDraft(hotspot_index=9, relevance=2, why_it_matters="oob"),
                    AudienceAssessmentDraft(hotspot_index=2, relevance=9, why_it_matters="score"),
                    AudienceAssessmentDraft(hotspot_index=0, relevance=1, why_it_matters="zero"),
                    AudienceAssessmentDraft(
                        hotspot_index=2,
                        relevance=1,
                        why_it_matters="keep",
                        caveat="投影未给销量",
                    ),
                ]
            )

    reviews, errors = collect_audience_reviews(
        _ballots(), DirtyLLM(), category="phone", profiles=AUDIENCE_PROFILES[:1]
    )
    assert not errors
    items = reviews[0].assessments
    assert [a.hotspot_index for a in items] == [1, 2]
    assert items[0].relevance == 3
    assert items[0].title == "长焦双路线"
    assert items[1].why_it_matters == "keep"


def test_empty_hotspots_skip_audience_llm():
    llm = FakeLLM()
    reviews, errors = collect_audience_reviews([], llm)
    assert reviews == []
    assert errors == []
    assert llm.call_count == 0


def test_cluster_llm_failure_has_no_keyword_fallback():
    class FailLLM:
        call_count = 0

        def chat_json(self, system, user, model, **kwargs):
            self.call_count += 1
            name = getattr(model, "__name__", "")
            if name == "ClusterPayload":
                raise RuntimeError("boom")
            raise AssertionError("unexpected")

    clusters, errors = cluster_hotspots(_ballots(), FailLLM())
    assert clusters == []
    assert errors == ["cluster: boom"]
    assert "其他观察" not in str(clusters)


def test_cluster_leftover_becomes_singleton_not_bucket():
    class PartialLLM:
        call_count = 0

        def chat_json(self, system, user, model, **kwargs):
            from terminal_insight_v2.vote.models import ClusterDraft, ClusterPayload

            return ClusterPayload(
                clusters=[ClusterDraft(direction="模型命名方向", hotspot_ids=[1])]
            )

    clusters, errors = cluster_hotspots(_ballots(), PartialLLM())
    assert not errors
    assert len(clusters) == 2
    assert clusters[0].direction == "模型命名方向"
    assert clusters[1].direction == "2000元万级电池"
    assert clusters[1].mention_count == 1


def test_one_audience_failure_keeps_others(tmp_path: Path, monkeypatch):
    class FlakyLLM(FakeLLM):
        def chat_json(self, system, user, model, **kwargs):
            name = getattr(model, "__name__", "")
            if name == "AudienceReviewPayload" and "审阅人 OEM" in system:
                raise RuntimeError("boom")
            return super().chat_json(system, user, model, **kwargs)

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
    result = run_vote(ctx, llm=FlakyLLM())
    assert result.status == "partial"
    assert result.metrics["voters_with_hotspots"] == 6
    assert result.metrics["audiences_reviewed"] == 3
    assert any("OEM:" in e for e in result.errors)
    data = json.loads((run_dir / "votes.json").read_text(encoding="utf-8"))
    by_id = {r["audience_id"]: r for r in data["audience_reviews"]}
    assert by_id["REG"]["assessments"]
    assert by_id["CON"]["assessments"]
    assert by_id["OEM"]["assessments"] == []
    assert by_id["SUP"]["assessments"]
    assert data["audience_reviews"][0]["assessments"][0]["title"]


def test_old_votes_json_without_audience_reviews_loads():
    artifact = VotesArtifact.model_validate(
        {
            "schema_version": 1,
            "run_id": "old",
            "category": "phone",
            "voters": [],
            "clusters": [],
        }
    )
    assert artifact.audience_reviews == []
    assert artifact.schema_version == 1

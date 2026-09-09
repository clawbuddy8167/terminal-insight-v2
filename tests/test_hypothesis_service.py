"""Hypothesis mapping service: per-pass retry resilience."""
from __future__ import annotations

from terminal_insight_v2.hypothesis.models import (
    Hypothesis,
    HypothesisMappingDraft,
    HypothesisMappingPayload,
    HypothesisSet,
)
from terminal_insight_v2.hypothesis.service import map_hypotheses


class FlakyHypothesisLLM:
    """Fails the first N chat_json calls, then returns a stable mapping."""

    def __init__(self, *, fail_first: int = 1) -> None:
        self.call_count = 0
        self.fail_first = fail_first

    def chat_json(self, system: str, user: str, model, **kwargs):
        self.call_count += 1
        if self.call_count <= self.fail_first:
            raise ValueError("empty LLM content")
        return HypothesisMappingPayload(
            mappings=[
                HypothesisMappingDraft(
                    hypothesis_id="H1",
                    hotspot_index=1,
                    stance="support",
                    evidence="屏幕显示技术：2K 120Hz",
                    strength=3,
                    note="",
                ),
            ]
        )


def _hypo_set() -> HypothesisSet:
    return HypothesisSet(
        schema_version=2,
        year=2026,
        category="phone",
        source="test",
        hypotheses=[Hypothesis(id="H1", statement="L3 下探")],
    )


def _entries() -> list[tuple[str, dict]]:
    return [
        (
            "AAA",
            {
                "title": "影像旗舰",
                "brand": "OPPO",
                "model": "Find X9 Ultra",
                "frame_name": "创新",
                "rationale_text": "10倍光变",
            },
        ),
    ]


def test_map_hypotheses_retries_flaky_pass():
    llm = FlakyHypothesisLLM(fail_first=1)
    reviews, disputes, errors = map_hypotheses(_hypo_set(), _entries(), llm)
    assert llm.call_count >= 2
    assert errors == []
    assert len(reviews) == 1
    assert reviews[0].hypothesis_id == "H1"
    assert disputes == []


def test_map_hypotheses_one_pass_fails_yields_disputes():
    llm = FlakyHypothesisLLM(fail_first=999)
    reviews, disputes, errors = map_hypotheses(_hypo_set(), _entries(), llm)
    assert reviews == []
    assert disputes == []
    assert errors
    assert any("pass1" in e for e in errors)
    assert any("pass2" in e for e in errors)

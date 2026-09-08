"""Hypothesis ledger contracts: catalog, per-run mapping, cross-run settlement."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Stance = Literal["support", "weaken", "unrelated"]
STANCES: tuple[Stance, ...] = ("support", "weaken", "unrelated")

Confidence = Literal["direct_quote", "inferred", "extrapolated"]
CONFIDENCES: tuple[Confidence, ...] = ("direct_quote", "inferred", "extrapolated")

Verdict = Literal["confirmed", "partial", "falsified", "insufficient", "alert"]
VERDICTS: tuple[Verdict, ...] = (
    "confirmed",
    "partial",
    "falsified",
    "insufficient",
    "alert",
)


class Hypothesis(BaseModel):
    id: str
    statement: str
    lead_indicators: List[str] = Field(default_factory=list)
    falsify_when: str = ""
    vendor_implication: str = ""
    frames: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    confidence: Confidence = "inferred"

    @field_validator("id")
    @classmethod
    def _id_nonempty(cls, value: str) -> str:
        clipped = (value or "").strip()
        if not clipped:
            raise ValueError("hypothesis id must be non-empty")
        return clipped

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: object) -> object:
        if value is None or value == "":
            return "inferred"
        return value


class HypothesisSet(BaseModel):
    """Year-level input: falsifiable propositions distilled from prior bluebook."""

    schema_version: int = 2
    year: int
    category: str
    source: str = ""
    hypotheses: List[Hypothesis] = Field(default_factory=list)

    @field_validator("hypotheses")
    @classmethod
    def _unique_ids(cls, items: List[Hypothesis]) -> List[Hypothesis]:
        seen: set[str] = set()
        for h in items:
            if h.id in seen:
                raise ValueError(f"duplicate hypothesis id: {h.id}")
            seen.add(h.id)
        return items


class HypothesisMappingDraft(BaseModel):
    """LLM output for one (hypothesis, hotspot) pair."""

    hypothesis_id: str
    hotspot_index: int
    stance: Stance
    evidence: str = ""
    strength: int = 1
    note: str = ""

    @field_validator("strength", mode="before")
    @classmethod
    def _clamp_strength(cls, value: object) -> int:
        try:
            n = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 1
        return max(1, min(3, n))


class HypothesisMappingPayload(BaseModel):
    """LLM output: mappings only; identity stamped by the stage."""

    mappings: List[HypothesisMappingDraft] = Field(default_factory=list)


class HypothesisReview(BaseModel):
    """Stamped mapping row written into votes.json."""

    hypothesis_id: str
    hotspot_index: int
    voter_id: str = ""
    title: str = ""
    brand: str = ""
    model: str = ""
    stance: Stance
    evidence: str = ""
    strength: int = 1
    note: str = ""
    statement: str = ""


class StanceCounts(BaseModel):
    support: int = 0
    weaken: int = 0
    unrelated: int = 0


class QuarterStance(BaseModel):
    run_id: str
    counts: StanceCounts = Field(default_factory=StanceCounts)


class RepresentativeHotspot(BaseModel):
    run_id: str
    title: str = ""
    brand: str = ""
    model: str = ""
    stance: Stance
    voter_id: str = ""


class HypothesisSettlement(BaseModel):
    hypothesis_id: str
    statement: str = ""
    verdict: Verdict
    by_quarter: List[QuarterStance] = Field(default_factory=list)
    representatives: List[RepresentativeHotspot] = Field(default_factory=list)
    voter_coverage: List[str] = Field(default_factory=list)
    note: str = ""


class OemSliceItem(BaseModel):
    """Moved from audience_reviews OEM rows; no new facts."""

    run_id: str
    title: str = ""
    brand: str = ""
    model: str = ""
    relevance: int = 0
    action_implication: str = ""
    why_it_matters: str = ""
    caveat: str = ""


class SettlementArtifact(BaseModel):
    schema_version: int = 1
    year: Optional[int] = None
    category: str = ""
    hypothesis_source: str = ""
    run_ids: List[str] = Field(default_factory=list)
    generated_at: str = ""
    settlements: List[HypothesisSettlement] = Field(default_factory=list)
    oem_slice: List[OemSliceItem] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


def empty_stance_counts() -> Dict[str, int]:
    return {"support": 0, "weaken": 0, "unrelated": 0}

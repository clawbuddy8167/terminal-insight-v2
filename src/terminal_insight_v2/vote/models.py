"""Vote stage contracts: ballots, clusters, and the votes.json artifact."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

VoterId = Literal["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
VOTER_IDS: tuple[VoterId, ...] = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")


class HotspotRationale(BaseModel):
    innovation: str = ""
    market: str = ""
    user: str = ""
    discussion: str = ""


class HotspotVote(BaseModel):
    title: str
    brand: str = ""
    model: str = ""
    rationale: HotspotRationale = Field(default_factory=HotspotRationale)
    axis_tags: List[str] = Field(default_factory=list)

    @field_validator("rationale", mode="before")
    @classmethod
    def _coerce_rationale(cls, value: object) -> object:
        if value is None:
            return {}
        if isinstance(value, str):
            return {"innovation": value}
        return value


class VoterBallotPayload(BaseModel):
    """LLM output for one voter (hotspots only; identity is stamped by the stage)."""

    hotspots: List[HotspotVote] = Field(default_factory=list)


class VoterBallot(BaseModel):
    voter_id: VoterId
    frame_name: str = ""
    reference_frame: str
    framing: str
    hotspots: List[HotspotVote] = Field(default_factory=list)


class ClusterAxis(BaseModel):
    voter_id: str
    lens: str = ""


class ClusterDevice(BaseModel):
    brand: str = ""
    model: str = ""


class DirectionCluster(BaseModel):
    direction: str
    mention_count: int = 0
    voter_ids: List[str] = Field(default_factory=list)
    devices: List[ClusterDevice] = Field(default_factory=list)
    axes_preserved: List[ClusterAxis] = Field(default_factory=list)


class ClusterDraft(BaseModel):
    direction: str
    hotspot_ids: List[int] = Field(default_factory=list)


class ClusterPayload(BaseModel):
    """LLM output: 1-based hotspot_ids referring to the numbered ballot list."""

    clusters: List[ClusterDraft] = Field(default_factory=list)


class VotesArtifact(BaseModel):
    schema_version: int = 1
    run_id: str
    category: str
    schema_fingerprint: str = ""
    input_revision: str = ""
    generated_at: str = ""
    voters: List[VoterBallot] = Field(default_factory=list)
    clusters: List[DirectionCluster] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


def flatten_rationale(rationale: Optional[HotspotRationale]) -> str:
    if rationale is None:
        return ""
    parts: List[str] = []
    for label, text in (
        ("创新", rationale.innovation),
        ("市场", rationale.market),
        ("用户", rationale.user),
        ("讨论", rationale.discussion),
    ):
        clipped = (text or "").strip()
        if clipped:
            parts.append(f"{label}：{clipped}")
    return "；".join(parts)

"""AI capability view data models."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# Ordered capability ladder, low → high. "待判断" is excluded from scoring.
CAPABILITY_STAGES: List[str] = [
    "单点AI辅助",
    "感知与理解",
    "长期记忆",
    "Agent执行",
    "安全与服务",
]

_STAGE_RANK: Dict[str, int] = {name: i + 1 for i, name in enumerate(CAPABILITY_STAGES)}

# "待判断" / "未知" mean the row was not assessed — not a real stage.
UNASSESSED = frozenset({"待判断", "未知", ""})


def stage_rank(raw: str) -> Optional[int]:
    """Map raw stage text to 1..5 rank; None if unassessed or unknown."""
    text = (raw or "").strip()
    if text in UNASSESSED:
        return None
    return _STAGE_RANK.get(text)


def stage_label(rank: int) -> str:
    if 1 <= rank <= len(CAPABILITY_STAGES):
        return CAPABILITY_STAGES[rank - 1]
    return f"L{rank}"


class DeviceAICard(BaseModel):
    """One device's AI capability profile, parsed from resolved items."""

    device_id: str
    brand: str = ""
    model: str = ""
    price: Optional[float] = None
    price_band: str = ""
    stage_raw: str = ""
    stage_rank: Optional[int] = None
    agent_exec: Optional[bool] = None
    continuous_sense: Optional[bool] = None
    long_memory: Optional[bool] = None
    ai_entry: str = ""
    ai_native: str = ""
    ai_tags: str = ""
    ai_features: str = ""
    nominated_by: List[str] = Field(default_factory=list)

    @property
    def assessed(self) -> bool:
        return self.stage_rank is not None

    @property
    def bool_score(self) -> int:
        """Count of True among the three capability booleans (0-3)."""
        return sum(
            1
            for v in (self.agent_exec, self.continuous_sense, self.long_memory)
            if v is True
        )


class AIQuadrantPoint(BaseModel):
    device_id: str
    brand: str
    model: str
    x: float
    y: float
    stage_label: str = ""
    price_band: str = ""
    bool_score: int = 0
    nominated_by: List[str] = Field(default_factory=list)


class AIQuadrantArtifact(BaseModel):
    run_id: str
    category: str
    stage_ladder: List[str] = Field(default_factory=lambda: list(CAPABILITY_STAGES))
    points: List[AIQuadrantPoint] = Field(default_factory=list)
    unassessed: List[DeviceAICard] = Field(default_factory=list)
    skipped_no_price: List[DeviceAICard] = Field(default_factory=list)
    stage_counts: Dict[str, int] = Field(default_factory=dict)
    origin_x_median: Optional[float] = None

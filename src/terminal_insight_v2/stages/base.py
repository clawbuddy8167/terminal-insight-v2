"""Stage protocol and stub implementation."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from terminal_insight_v2.models import StageContext, StageResult


@runtime_checkable
class Stage(Protocol):
    name: str

    def prereq(self, ctx: StageContext) -> None: ...

    def run(self, ctx: StageContext) -> StageResult: ...


class StubStage:
    """Placeholder until a real stage is implemented."""

    def __init__(self, name: str = "stub") -> None:
        self.name = name

    def prereq(self, ctx: StageContext) -> None:
        return None

    def run(self, ctx: StageContext) -> StageResult:
        return StageResult(
            stage=self.name,
            status="skipped",
            output_revision=f"{self.name}:stub",
            metrics={"note": "stage not implemented yet"},
        )

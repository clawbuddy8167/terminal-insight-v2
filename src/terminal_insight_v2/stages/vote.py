"""Stage 6 — Vote: six reference-frame ballots + light clustering."""
from __future__ import annotations

from terminal_insight_v2.models.stage import StageContext, StageResult
from terminal_insight_v2.stages.base import Stage
from terminal_insight_v2.vote import require_vote_inputs, run_vote


class VoteStage(Stage):
    name = "vote"

    def prereq(self, ctx: StageContext) -> None:
        require_vote_inputs(ctx)

    def run(self, ctx: StageContext) -> StageResult:
        return run_vote(ctx)

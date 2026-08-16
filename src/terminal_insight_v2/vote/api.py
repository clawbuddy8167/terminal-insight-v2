"""Public Vote stage entry: prereq + run_vote(ctx) -> StageResult."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from terminal_insight_v2.config import settings
from terminal_insight_v2.models.stage import StageContext, StageResult
from terminal_insight_v2.providers.llm import LLMProvider
from terminal_insight_v2.store.db import utc_now

from .excel_write import row_count, write_votes_excel
from .models import VOTER_IDS, VotesArtifact
from .project import project_from_path
from .service import cluster_hotspots, collect_ballots

VOTES_NAME = "votes.json"


def resolved_path(ctx: StageContext) -> Path:
    return Path(ctx.run_dir) / "resolved.json"


def require_vote_inputs(ctx: StageContext) -> None:
    """Raise if Vote cannot run. Does not skip."""
    if not (settings.openai_api_key or "").strip():
        raise RuntimeError("OPENAI_API_KEY is required for vote")
    path = resolved_path(ctx)
    if not path.exists():
        raise FileNotFoundError(f"缺少 resolved.json（run={ctx.run_id}）；请先跑 verify")


def run_vote(ctx: StageContext, *, llm: Optional[LLMProvider] = None) -> StageResult:
    require_vote_inputs(ctx)
    path = resolved_path(ctx)
    projection = project_from_path(
        path,
        category=ctx.category,
        input_revision=ctx.input_revision,
    )
    provider = llm or LLMProvider(settings)
    ballots, errors = collect_ballots(projection, provider)
    clusters = cluster_hotspots(ballots, provider)
    artifact = VotesArtifact(
        schema_version=1,
        run_id=ctx.run_id,
        category=ctx.category,
        schema_fingerprint=ctx.schema_fingerprint,
        input_revision=projection.input_revision,
        generated_at=utc_now(),
        voters=ballots,
        clusters=clusters,
        errors=errors,
    )
    run_dir = Path(ctx.run_dir)
    votes_path = run_dir / VOTES_NAME
    votes_path.write_text(
        json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    excel_path = write_votes_excel(run_dir, artifact, category=ctx.category)
    n = row_count(artifact)
    filled_voters = sum(1 for b in ballots if b.hotspots)
    if filled_voters == 0:
        status = "failed"
    elif errors or filled_voters < len(VOTER_IDS):
        status = "partial"
    else:
        status = "ok"
    return StageResult(
        stage="vote",
        status=status,
        output_revision=f"vote:{ctx.run_id}:{projection.input_revision}:n{n}",
        metrics={
            "voters": len(ballots),
            "voters_with_hotspots": filled_voters,
            "hotspots": n,
            "clusters": len(clusters),
            "llm_calls": provider.call_count,
            "devices_projected": len(projection.devices),
        },
        artifacts={
            "votes.json": str(votes_path),
            "excel": str(excel_path),
        },
        errors=errors[:30],
    )

"""Public Vote stage entry: prereq + run_vote(ctx) -> StageResult."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from terminal_insight_v2.config import settings
from terminal_insight_v2.hypothesis.api import load_for_vote, map_entries
from terminal_insight_v2.models.stage import StageContext, StageResult
from terminal_insight_v2.providers.llm import LLMProvider
from terminal_insight_v2.store.db import utc_now

from .audience_profiles import AUDIENCE_PROFILES
from .audience_service import collect_audience_reviews
from .excel_write import row_count, write_votes_excel
from .models import VOTER_IDS, VotesArtifact, VoterBallot, flatten_rationale
from .project import project_from_path
from .service import cluster_hotspots, collect_ballots, flatten_hotspots

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


def _ballot_entries(ballots: Sequence[VoterBallot]) -> List[Tuple[str, dict]]:
    """Build hypothesis-mapping entries without hypothesis importing vote."""
    entries: List[Tuple[str, dict]] = []
    by_voter = {b.voter_id: b for b in ballots}
    for voter_id, hs in flatten_hotspots(ballots):
        ballot = by_voter.get(voter_id)
        entries.append(
            (
                voter_id,
                {
                    "title": hs.title,
                    "brand": hs.brand,
                    "model": hs.model,
                    "frame_name": ballot.frame_name if ballot else "",
                    "rationale_text": flatten_rationale(hs.rationale),
                },
            )
        )
    return entries


def run_vote(ctx: StageContext, *, llm: Optional[LLMProvider] = None) -> StageResult:
    require_vote_inputs(ctx)
    path = resolved_path(ctx)
    key_specs: List[str] = []
    try:
        from terminal_insight_v2.category import load_category_schema

        schema = load_category_schema(ctx.category, persist=False)
        key_specs = [f.name for f in schema.fields if f.key_spec]
    except Exception:  # noqa: BLE001
        key_specs = []
    projection = project_from_path(
        path,
        category=ctx.category,
        input_revision=ctx.input_revision,
        key_spec_names=key_specs,
    )
    provider = llm or LLMProvider(settings, thinking_enabled=True)
    ballots, errors = collect_ballots(projection, provider)
    clusters, cluster_errors = cluster_hotspots(ballots, provider)
    reviews, audience_errors = collect_audience_reviews(
        ballots, provider, category=ctx.category
    )
    extras_path = str((ctx.extras or {}).get("hypotheses_path") or "")
    hypo_set, _hypo_path = load_for_vote(
        category=ctx.category, extras_path=extras_path
    )
    hypo_reviews, hypo_disputes, hypo_errors = map_entries(
        hypo_set,
        _ballot_entries(ballots),
        provider,
        category=ctx.category,
    )
    errors = list(errors) + list(cluster_errors) + list(audience_errors) + list(
        hypo_errors
    )
    if hypo_disputes:
        errors.append(
            f"hypothesis: {len(hypo_disputes)} dual-pass disputes "
            f"(excluded from settlement)"
        )
    artifact = VotesArtifact(
        schema_version=5,
        run_id=ctx.run_id,
        category=ctx.category,
        schema_fingerprint=ctx.schema_fingerprint,
        input_revision=projection.input_revision,
        generated_at=utc_now(),
        voters=ballots,
        clusters=clusters,
        audience_reviews=reviews,
        hypothesis_reviews=hypo_reviews,
        hypothesis_disputes=hypo_disputes,
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
    filled_audiences = sum(1 for r in reviews if r.assessments)
    expected_audiences = len(AUDIENCE_PROFILES) if n else 0
    hypo_failed = bool(hypo_errors)
    artifacts = {
        "votes.json": str(votes_path),
        "excel": str(excel_path),
    }
    quadrant_points = 0
    try:
        from terminal_insight_v2.quadrant.api import write_for_run as write_quadrant

        q_art, q_json, q_html = write_quadrant(run_dir)
        artifacts["quadrant.json"] = str(q_json)
        artifacts["quadrant.html"] = str(q_html)
        quadrant_points = len(q_art.points)
    except Exception as exc:  # noqa: BLE001
        # Research view only — never flip Vote to failed/partial by itself.
        artifacts["quadrant_error"] = str(exc)
    if filled_voters == 0:
        status = "failed"
    elif (
        errors
        or filled_voters < len(VOTER_IDS)
        or filled_audiences < expected_audiences
        or hypo_failed
    ):
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
            "audiences": expected_audiences,
            "audiences_reviewed": filled_audiences,
            "hypothesis_mappings": len(hypo_reviews),
            "hypothesis_disputes": len(hypo_disputes),
            "hypotheses_loaded": 0 if hypo_set is None else len(hypo_set.hypotheses),
            "llm_calls": provider.call_count,
            "devices_projected": len(projection.devices),
            "quadrant_points": quadrant_points,
        },
        artifacts=artifacts,
        errors=errors[:30],
    )

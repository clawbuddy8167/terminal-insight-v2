"""Audience reviews scored per numbered hotspot nomination."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from terminal_insight_v2.providers.llm import LLMProvider

from .audience_profiles import AUDIENCE_PROFILES, AudienceProfile
from .audience_prompts import audience_system, audience_user
from .models import (
    AudienceAssessment,
    AudienceAssessmentDraft,
    AudienceReview,
    AudienceReviewPayload,
    HotspotVote,
    VoterBallot,
)
from .service import flatten_hotspots

_TEXT_CHARS = 400


def collect_audience_reviews(
    ballots: Sequence[VoterBallot],
    llm: LLMProvider,
    *,
    category: str = "",
    profiles: Sequence[AudienceProfile] = AUDIENCE_PROFILES,
) -> Tuple[List[AudienceReview], List[str]]:
    """Score each numbered hotspot for every audience.

    Empty hotspot list skips all calls. One audience failure does not drop others.
    """
    entries = flatten_hotspots(ballots)
    if not entries:
        return [], []
    by_voter = {b.voter_id: b for b in ballots}
    reviews: List[AudienceReview] = []
    errors: List[str] = []
    for profile in profiles:
        try:
            payload = llm.chat_json(
                audience_system(profile, category),
                audience_user(profile, entries, ballots),
                AudienceReviewPayload,
                temperature=0.25,
                max_tokens=12288,
            )
            assessments = _sanitize_assessments(
                payload.assessments, entries, by_voter
            )
            if not assessments:
                errors.append(
                    f"{profile.audience_id}: empty assessments "
                    f"(raw={len(payload.assessments)}, hotspots={len(entries)})"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{profile.audience_id}: {exc}")
            assessments = []
        reviews.append(
            AudienceReview(
                audience_id=profile.audience_id,
                name=profile.name,
                assessments=assessments,
            )
        )
    return reviews, errors


def _sanitize_assessments(
    drafts: Sequence[AudienceAssessmentDraft],
    entries: Sequence[Tuple[str, HotspotVote]],
    by_voter: dict[str, VoterBallot],
) -> List[AudienceAssessment]:
    n = len(entries)
    seen: set[int] = set()
    out: List[AudienceAssessment] = []
    for draft in drafts:
        idx = int(draft.hotspot_index)
        if idx < 1 or idx > n or idx in seen:
            continue
        relevance = int(draft.relevance)
        if relevance < 0 or relevance > 3:
            continue
        seen.add(idx)
        voter_id, hs = entries[idx - 1]
        ballot = by_voter.get(voter_id)
        out.append(
            AudienceAssessment(
                hotspot_index=idx,
                voter_id=voter_id,
                frame_name=ballot.frame_name if ballot else "",
                title=hs.title,
                brand=hs.brand,
                model=hs.model,
                relevance=relevance,
                why_it_matters=_clip(draft.why_it_matters),
                action_implication=_clip(draft.action_implication),
                caveat=_clip(draft.caveat),
            )
        )
    return out


def _clip(text: str) -> str:
    return (text or "").strip()[:_TEXT_CHARS]

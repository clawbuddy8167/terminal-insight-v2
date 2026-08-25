"""Map numbered hotspots onto a HypothesisSet via one LLM call."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from terminal_insight_v2.providers.llm import LLMProvider

from .models import (
    HypothesisMappingDraft,
    HypothesisMappingPayload,
    HypothesisReview,
    HypothesisSet,
    STANCES,
)
from .prompts import mapping_system, mapping_user, numbered_hotspot_lines

_NOTE_CHARS = 400


def map_hypotheses(
    hypo_set: Optional[HypothesisSet],
    entries: Sequence[Tuple[str, dict]],
    llm: LLMProvider,
    *,
    category: str = "",
) -> Tuple[List[HypothesisReview], List[str]]:
    """Score hotspots against hypotheses.

    Empty hypo_set or empty entries → zero LLM calls, empty reviews.
    LLM failure → error string + empty reviews (caller marks Vote partial).
    """
    if hypo_set is None or not hypo_set.hypotheses or not entries:
        return [], []
    known_ids = {h.id for h in hypo_set.hypotheses}
    by_id = {h.id: h for h in hypo_set.hypotheses}
    lines = numbered_hotspot_lines(entries)
    try:
        payload = llm.chat_json(
            mapping_system(category or hypo_set.category),
            mapping_user(hypo_set, lines),
            HypothesisMappingPayload,
            temperature=0.2,
            max_tokens=8192,
        )
        reviews = _sanitize(payload.mappings, entries, known_ids, by_id)
        if not reviews and payload.mappings:
            return [], [
                f"hypothesis: all {len(payload.mappings)} mappings rejected "
                f"(hotspots={len(entries)}, hypotheses={len(known_ids)})"
            ]
        return reviews, []
    except Exception as exc:  # noqa: BLE001
        return [], [f"hypothesis: {exc}"]


def _sanitize(
    drafts: Sequence[HypothesisMappingDraft],
    entries: Sequence[Tuple[str, dict]],
    known_ids: set[str],
    by_id: dict,
) -> List[HypothesisReview]:
    n = len(entries)
    seen: set[tuple[str, int]] = set()
    out: List[HypothesisReview] = []
    for draft in drafts:
        hid = (draft.hypothesis_id or "").strip()
        idx = int(draft.hotspot_index)
        stance = draft.stance
        if hid not in known_ids:
            continue
        if idx < 1 or idx > n:
            continue
        if stance not in STANCES:
            continue
        key = (hid, idx)
        if key in seen:
            continue
        seen.add(key)
        voter_id, hs = entries[idx - 1]
        hypo = by_id[hid]
        out.append(
            HypothesisReview(
                hypothesis_id=hid,
                hotspot_index=idx,
                voter_id=voter_id,
                title=str(hs.get("title") or ""),
                brand=str(hs.get("brand") or ""),
                model=str(hs.get("model") or ""),
                stance=stance,
                note=_clip(draft.note),
                statement=hypo.statement,
            )
        )
    return out


def _clip(text: str) -> str:
    return (text or "").strip()[:_NOTE_CHARS]

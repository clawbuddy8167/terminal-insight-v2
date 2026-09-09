"""Map numbered hotspots onto a HypothesisSet via dual-pass LLM consensus."""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence, Tuple

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
_EVIDENCE_CHARS = 400
_PASS_TEMPERATURES = (0.2, 0.6)
_PASS_OUTER_RETRIES = 4
_PASS_MAX_TOKENS = 16384
_PASS_PARSE_RETRIES = 5


def map_hypotheses(
    hypo_set: Optional[HypothesisSet],
    entries: Sequence[Tuple[str, dict]],
    llm: LLMProvider,
    *,
    category: str = "",
) -> Tuple[List[HypothesisReview], List[HypothesisReview], List[str]]:
    """Score hotspots against hypotheses with dual-pass consensus.

    Returns (reviews, disputes, errors).
    Empty hypo_set or empty entries → zero LLM calls.
    Two passes at temperatures 0.2 / 0.6; matching stance → reviews,
    conflicting or one-sided → disputes (excluded from settlement).
    """
    if hypo_set is None or not hypo_set.hypotheses or not entries:
        return [], [], []
    known_ids = {h.id for h in hypo_set.hypotheses}
    by_id = {h.id: h for h in hypo_set.hypotheses}
    lines = numbered_hotspot_lines(entries)
    system = mapping_system(category or hypo_set.category)
    user = mapping_user(hypo_set, lines)
    passes: List[List[HypothesisReview]] = []
    errors: List[str] = []
    for pass_no, temp in enumerate(_PASS_TEMPERATURES, start=1):
        stamped, err = _run_mapping_pass(
            llm,
            system,
            user,
            temperature=temp,
            entries=entries,
            known_ids=known_ids,
            by_id=by_id,
        )
        if stamped is None:
            errors.append(f"hypothesis: pass{pass_no} (temp={temp}): {err}")
            passes.append([])
        else:
            passes.append(stamped)

    if not any(passes):
        return [], [], errors or ["hypothesis: all passes failed"]

    reviews, disputes = _consensus(passes[0], passes[1])
    if not reviews and not disputes and any(passes):
        total = sum(len(p) for p in passes)
        rejected = (
            f"hypothesis: all {total} mappings rejected "
            f"(hotspots={len(entries)}, hypotheses={len(known_ids)})"
        )
        return [], [], errors + [rejected]
    return reviews, disputes, errors


def _run_mapping_pass(
    llm: LLMProvider,
    system: str,
    user: str,
    *,
    temperature: float,
    entries: Sequence[Tuple[str, dict]],
    known_ids: set[str],
    by_id: dict,
) -> Tuple[Optional[List[HypothesisReview]], str]:
    """Run one dual-pass temperature with outer retries (API flakiness)."""
    last_err = "unknown"
    for attempt in range(_PASS_OUTER_RETRIES):
        try:
            payload = llm.chat_json(
                system,
                user,
                HypothesisMappingPayload,
                temperature=temperature,
                max_tokens=_PASS_MAX_TOKENS,
                parse_retries=_PASS_PARSE_RETRIES,
            )
            return _sanitize(payload.mappings, entries, known_ids, by_id), ""
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            if attempt + 1 < _PASS_OUTER_RETRIES:
                time.sleep(min(8.0, 0.6 * (attempt + 1)))
    return None, last_err


def _consensus(
    pass_a: Sequence[HypothesisReview],
    pass_b: Sequence[HypothesisReview],
) -> Tuple[List[HypothesisReview], List[HypothesisReview]]:
    by_a: Dict[tuple[str, int], HypothesisReview] = {
        (r.hypothesis_id, r.hotspot_index): r for r in pass_a
    }
    by_b: Dict[tuple[str, int], HypothesisReview] = {
        (r.hypothesis_id, r.hotspot_index): r for r in pass_b
    }
    keys = sorted(set(by_a) | set(by_b))
    reviews: List[HypothesisReview] = []
    disputes: List[HypothesisReview] = []
    for key in keys:
        a = by_a.get(key)
        b = by_b.get(key)
        if a is None or b is None:
            survivor = a or b
            assert survivor is not None
            disputes.append(
                survivor.model_copy(
                    update={
                        "note": _dispute_note(
                            survivor.note,
                            a.stance if a else None,
                            b.stance if b else None,
                        )
                    }
                )
            )
            continue
        if a.stance == b.stance:
            strength = min(int(a.strength or 1), int(b.strength or 1))
            evidence = (a.evidence or "").strip() or (b.evidence or "").strip()
            note = (a.note or "").strip() or (b.note or "").strip()
            reviews.append(
                a.model_copy(
                    update={
                        "strength": strength,
                        "evidence": evidence[:_EVIDENCE_CHARS],
                        "note": note[:_NOTE_CHARS],
                    }
                )
            )
        else:
            disputes.append(
                a.model_copy(
                    update={
                        "note": _dispute_note(a.note, a.stance, b.stance),
                        "evidence": (a.evidence or b.evidence or "")[
                            :_EVIDENCE_CHARS
                        ],
                    }
                )
            )
    return reviews, disputes


def _dispute_note(
    base: str,
    stance_a: Optional[str],
    stance_b: Optional[str],
) -> str:
    label_a = stance_a or "missing"
    label_b = stance_b or "missing"
    prefix = f"双跑不一致: pass1={label_a}, pass2={label_b}"
    clipped = (base or "").strip()
    if clipped:
        return f"{prefix}; {clipped}"[:_NOTE_CHARS]
    return prefix[:_NOTE_CHARS]


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
        evidence = (draft.evidence or "").strip()
        if not evidence:
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
                evidence=evidence[:_EVIDENCE_CHARS],
                strength=int(draft.strength or 1),
                note=_clip(draft.note),
                statement=hypo.statement,
            )
        )
    return out


def _clip(text: str) -> str:
    return (text or "").strip()[:_NOTE_CHARS]

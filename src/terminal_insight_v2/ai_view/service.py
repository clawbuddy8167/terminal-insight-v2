"""Build price × AI-capability-stage quadrant from resolved.json."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from terminal_insight_v2.vote.project import load_resolved

from .models import (
    CAPABILITY_STAGES,
    AIQuadrantArtifact,
    AIQuadrantPoint,
    DeviceAICard,
    stage_label,
)
from .parse import parse_ai_cards


def _norm_key(brand: str, model: str) -> str:
    return f"{(brand or '').strip()}|{(model or '').strip()}".lower()


def _nominations(votes: Optional[Mapping[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    if not votes:
        return out
    for ballot in votes.get("voters") or []:
        if not isinstance(ballot, Mapping):
            continue
        voter_id = str(ballot.get("voter_id") or "").strip()
        for hs in ballot.get("hotspots") or []:
            if not isinstance(hs, Mapping):
                continue
            key = _norm_key(str(hs.get("brand") or ""), str(hs.get("model") or ""))
            if not key.strip("|"):
                continue
            bucket = out.setdefault(key, [])
            if voter_id and voter_id not in bucket:
                bucket.append(voter_id)
    return out


def build_ai_quadrant(
    *,
    run_id: str,
    category: str,
    resolved: Mapping[str, Any],
    votes: Optional[Mapping[str, Any]] = None,
) -> AIQuadrantArtifact:
    cards = parse_ai_cards(resolved)
    nominations = _nominations(votes)

    points: List[AIQuadrantPoint] = []
    unassessed: List[DeviceAICard] = []
    skipped_no_price: List[DeviceAICard] = []
    stage_counts: Dict[str, int] = {s: 0 for s in CAPABILITY_STAGES}

    for card in cards:
        key = _norm_key(card.brand, card.model)
        card.nominated_by = list(nominations.get(key, []))
        if card.price is None:
            skipped_no_price.append(card)
            continue
        if card.stage_rank is None:
            unassessed.append(card)
            continue
        label = stage_label(card.stage_rank)
        stage_counts[label] = stage_counts.get(label, 0) + 1
        points.append(
            AIQuadrantPoint(
                device_id=card.device_id,
                brand=card.brand,
                model=card.model,
                x=card.price,
                y=float(card.stage_rank),
                stage_label=label,
                price_band=card.price_band,
                bool_score=card.bool_score,
                nominated_by=card.nominated_by,
            )
        )

    origin_x = None
    if points:
        origin_x = float(statistics.median([p.x for p in points]))

    return AIQuadrantArtifact(
        run_id=run_id,
        category=category,
        points=points,
        unassessed=unassessed,
        skipped_no_price=skipped_no_price,
        stage_counts=stage_counts,
        origin_x_median=origin_x,
    )


def build_from_run_dir(run_dir: Path) -> AIQuadrantArtifact:
    run_dir = Path(run_dir)
    resolved_path = run_dir / "resolved.json"
    if not resolved_path.is_file():
        raise FileNotFoundError(f"缺少 resolved.json: {resolved_path}")
    resolved = load_resolved(resolved_path)
    votes = None
    votes_path = run_dir / "votes.json"
    if votes_path.is_file():
        votes = json.loads(votes_path.read_text(encoding="utf-8"))
    return build_ai_quadrant(
        run_id=str(resolved.get("run_id") or run_dir.name),
        category=str(resolved.get("category") or ""),
        resolved=resolved,
        votes=votes if isinstance(votes, dict) else None,
    )

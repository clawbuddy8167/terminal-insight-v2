"""Public hypothesis API: resolve path, map in Vote, settle across runs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from terminal_insight_v2.providers.llm import LLMProvider

from .loader import resolve_hypotheses_path, try_load_hypothesis_set
from .models import HypothesisReview, HypothesisSet, SettlementArtifact
from .service import map_hypotheses
from .settle import settle_runs
from .excel_write import write_settlement_excel


def load_for_vote(
    *,
    category: str = "",
    extras_path: str = "",
) -> Tuple[Optional[HypothesisSet], Optional[Path]]:
    """Resolve and load catalog for Vote. Missing file → (None, None)."""
    path = resolve_hypotheses_path(category=category, extras_path=extras_path)
    if path is None:
        return None, None
    if not path.is_file():
        return None, path
    return try_load_hypothesis_set(path), path


def map_entries(
    hypo_set: Optional[HypothesisSet],
    entries: Sequence[Tuple[str, dict]],
    llm: LLMProvider,
    *,
    category: str = "",
) -> Tuple[List[HypothesisReview], List[str]]:
    """Map pre-built (voter_id, hotspot_dict) entries — Vote builds the dicts."""
    return map_hypotheses(hypo_set, entries, llm, category=category)


def run_settle(
    *,
    hypothesis_path: Path,
    run_ids: Sequence[str],
    out_dir: Path,
    runs_root: Optional[Path] = None,
) -> SettlementArtifact:
    """Settle multiple quarterly votes.json against a hypothesis catalog."""
    from .loader import load_hypothesis_set

    hypo_set = load_hypothesis_set(hypothesis_path)
    artifact = settle_runs(hypo_set, run_ids, runs_root=runs_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "settlement.json"
    path.write_text(
        json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_settlement_excel(out_dir / "settlement.xlsx", artifact)
    return artifact


__all__ = [
    "load_for_vote",
    "map_entries",
    "run_settle",
    "HypothesisSet",
    "HypothesisReview",
    "SettlementArtifact",
]

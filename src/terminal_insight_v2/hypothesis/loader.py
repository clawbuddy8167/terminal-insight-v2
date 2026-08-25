"""Load HypothesisSet from JSON path; resolve default catalog locations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from terminal_insight_v2.config import PROJECT_ROOT, settings

from .models import HypothesisSet


def load_hypothesis_set(path: Path) -> HypothesisSet:
    """Load and validate a hypothesis catalog. Raises on missing/invalid file."""
    if not path.is_file():
        raise FileNotFoundError(f"假说文件不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"假说文件不是 JSON 对象: {path}")
    return HypothesisSet.model_validate(data)


def try_load_hypothesis_set(path: Optional[Path]) -> Optional[HypothesisSet]:
    """Return None when path is missing or empty; re-raise validation errors."""
    if path is None:
        return None
    if not path.is_file():
        return None
    return load_hypothesis_set(path)


def resolve_hypotheses_path(
    *,
    category: str = "",
    explicit: str = "",
    extras_path: str = "",
) -> Optional[Path]:
    """Resolve catalog path: extras → settings → data/hypotheses/{category}.json.

    Returns None when no candidate exists (Vote should skip mapping LLM).
    """
    for raw in (extras_path, explicit, (settings.hypotheses_path or "").strip()):
        clipped = (raw or "").strip()
        if not clipped:
            continue
        p = Path(clipped)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    cat = (category or settings.category or "").strip()
    if not cat:
        return None
    default = settings.data_path() / "hypotheses" / f"{cat}.json"
    if default.is_file():
        return default
    # Also accept phone-2026 style year-suffixed catalogs under data/hypotheses/
    folder = settings.data_path() / "hypotheses"
    if folder.is_dir():
        matches = sorted(folder.glob(f"{cat}-*.json"))
        if matches:
            return matches[-1]
    return None

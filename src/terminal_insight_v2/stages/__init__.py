"""Pipeline stages."""

from typing import Dict

from .base import Stage, StubStage
from .backfill import BackfillStage
from .collect import CollectStage
from .extract import ExtractStage
from .excel_stage import ExcelStage
from .verify import VerifyStage

_STAGES: Dict[str, Stage] = {
    "collect": CollectStage(),
    "extract": ExtractStage(),
    "backfill": BackfillStage(),
    "verify": VerifyStage(),
    "excel": ExcelStage(),
    "vote": StubStage("vote"),
}


def get_stage(name: str) -> Stage:
    stage = _STAGES.get(name)
    if stage is None:
        return StubStage(name=name)
    return stage


__all__ = [
    "BackfillStage",
    "CollectStage",
    "ExtractStage",
    "VerifyStage",
    "ExcelStage",
    "Stage",
    "StubStage",
    "get_stage",
]

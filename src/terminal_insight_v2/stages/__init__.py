"""Pipeline stages (stubs until M2+)."""

from typing import Dict

from .base import Stage, StubStage


def get_stage(name: str) -> Stage:
    """Return a stage implementation (stub until M2+)."""
    return StubStage(name=name)


__all__ = ["Stage", "StubStage", "get_stage"]

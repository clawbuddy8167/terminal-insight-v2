"""Hypothesis research layer — catalog, Vote mapping, cross-run settlement."""

from .api import load_for_vote, map_entries, run_settle

__all__ = ["load_for_vote", "map_entries", "run_settle"]
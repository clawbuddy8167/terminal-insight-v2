"""HypothesisSet load / stance validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from terminal_insight_v2.hypothesis.loader import load_hypothesis_set, resolve_hypotheses_path
from terminal_insight_v2.hypothesis.models import HypothesisMappingDraft, HypothesisSet


def test_load_phone_2026_catalog():
    path = Path(__file__).resolve().parents[1] / "data" / "hypotheses" / "phone-2026.json"
    assert path.is_file()
    hypo = load_hypothesis_set(path)
    assert hypo.year == 2026
    assert hypo.category == "phone"
    assert len(hypo.hypotheses) >= 8
    assert hypo.hypotheses[0].id == "H1"


def test_duplicate_id_rejected(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "year": 2026,
                "category": "phone",
                "hypotheses": [
                    {"id": "H1", "statement": "a"},
                    {"id": "H1", "statement": "b"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_hypothesis_set(path)


def test_invalid_stance_rejected():
    with pytest.raises(ValidationError):
        HypothesisMappingDraft(
            hypothesis_id="H1",
            hotspot_index=1,
            stance="maybe",  # type: ignore[arg-type]
        )


def test_resolve_prefers_explicit(tmp_path: Path, monkeypatch):
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.hypothesis.loader as loader

    catalog = tmp_path / "custom.json"
    catalog.write_text(
        json.dumps(
            {
                "year": 2026,
                "category": "phone",
                "hypotheses": [{"id": "H1", "statement": "x"}],
            }
        ),
        encoding="utf-8",
    )
    s = Settings(_env_file=None, data_root=str(tmp_path / "data"))
    monkeypatch.setattr(loader, "settings", s)
    resolved = resolve_hypotheses_path(category="phone", extras_path=str(catalog))
    assert resolved == catalog

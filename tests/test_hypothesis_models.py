"""HypothesisSet load / stance validation / catalog v2."""
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
    assert hypo.schema_version == 2
    assert hypo.year == 2026
    assert hypo.category == "phone"
    assert len(hypo.hypotheses) >= 8
    assert hypo.hypotheses[0].id == "H1"
    ids = {h.id for h in hypo.hypotheses}
    assert "H4a" in ids and "H4b" in ids
    assert "H4" not in ids
    h4a = next(h for h in hypo.hypotheses if h.id == "H4a")
    assert h4a.source_refs
    assert h4a.confidence in ("direct_quote", "inferred", "extrapolated")


def test_duplicate_id_rejected(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
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
            evidence="x",
        )


def test_strength_clamped():
    draft = HypothesisMappingDraft(
        hypothesis_id="H1",
        hotspot_index=1,
        stance="support",
        evidence="电池容量：10000mAh",
        strength=9,
    )
    assert draft.strength == 3


def test_invalid_confidence_rejected():
    with pytest.raises(ValidationError):
        HypothesisSet.model_validate(
            {
                "schema_version": 2,
                "year": 2026,
                "category": "phone",
                "hypotheses": [
                    {
                        "id": "H1",
                        "statement": "x",
                        "confidence": "guess",
                    }
                ],
            }
        )


def test_resolve_prefers_explicit(tmp_path: Path, monkeypatch):
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.hypothesis.loader as loader

    catalog = tmp_path / "custom.json"
    catalog.write_text(
        json.dumps(
            {
                "schema_version": 2,
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

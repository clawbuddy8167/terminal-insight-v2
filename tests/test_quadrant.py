"""Quadrant builder unit tests."""
from __future__ import annotations

from terminal_insight_v2.quadrant.service import build_quadrant, nominations_from_votes


def test_nominations_and_points():
    resolved = {
        "run_id": "r1",
        "category": "phone",
        "items": [
            {
                "device_id": "phone:a:m1",
                "brand": "A",
                "model": "M1",
                "field_name": "起售价",
                "display_text": "2999元起",
                "policy": "unanimous",
            },
            {
                "device_id": "phone:a:m1",
                "brand": "A",
                "model": "M1",
                "field_name": "功耗与续航管理",
                "display_text": "6000mAh；90W",
                "policy": "unanimous",
            },
            {
                "device_id": "phone:b:m2",
                "brand": "B",
                "model": "M2",
                "field_name": "起售价",
                "display_text": "6999元",
                "policy": "unanimous",
            },
            {
                "device_id": "phone:b:m2",
                "brand": "B",
                "model": "M2",
                "field_name": "功耗与续航管理",
                "display_text": "5000mAh；100W",
                "policy": "unanimous",
            },
            {
                "device_id": "phone:c:m3",
                "brand": "C",
                "model": "M3",
                "field_name": "起售价",
                "display_text": "1999元",
                "policy": "unanimous",
            },
        ],
    }
    votes = {
        "voters": [
            {
                "voter_id": "CCC",
                "hotspots": [{"title": "t", "brand": "A", "model": "M1"}],
            }
        ]
    }
    noms = nominations_from_votes(votes)
    assert "a|m1" in noms
    art = build_quadrant(
        run_id="r1",
        category="phone",
        resolved=resolved,
        votes=votes,
    )
    assert len(art.points) == 2
    m1 = next(p for p in art.points if p.model == "M1")
    assert m1.x == 2999.0
    assert m1.y == 6000.0
    assert m1.nominated_by == ["CCC"]
    assert art.origin is not None
    assert any(s.model == "M3" for s in art.skipped)
    assert len(art.points_watt) == 2

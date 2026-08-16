"""Vote projection compression tests."""
from __future__ import annotations

from pathlib import Path

from terminal_insight_v2.vote.project import project_resolved, render_projection


def test_project_drops_identity_and_missing():
    data = {
        "category": "phone",
        "input_revision": "rev-1",
        "items": [
            {
                "device_id": "phone:a:m1",
                "brand": "A",
                "model": "M1",
                "field_name": "品牌",
                "display_text": "A",
                "policy": "identity",
            },
            {
                "device_id": "phone:a:m1",
                "brand": "A",
                "model": "M1",
                "field_name": "机型",
                "display_text": "M1",
                "policy": "identity",
            },
            {
                "device_id": "phone:a:m1",
                "brand": "A",
                "model": "M1",
                "field_name": "防水和防护",
                "display_text": "",
                "policy": "missing",
            },
            {
                "device_id": "phone:a:m1",
                "brand": "A",
                "model": "M1",
                "field_name": "屏幕显示技术",
                "display_text": "OLED 120Hz",
                "policy": "unanimous",
            },
            {
                "device_id": "phone:b:m2",
                "brand": "B",
                "model": "M2",
                "field_name": "品牌",
                "display_text": "B",
                "policy": "identity",
            },
        ],
    }
    proj = project_resolved(data, source_path=Path("resolved.json"), category="phone")
    assert proj.input_revision == "rev-1"
    assert len(proj.devices) == 1
    assert proj.devices[0].brand == "A"
    assert proj.devices[0].fields == [("屏幕显示技术", "OLED 120Hz")]
    text = render_projection(proj)
    assert "OLED 120Hz" in text
    assert "M2" not in text


def test_project_prefers_ctx_revision():
    data = {"category": "phone", "input_revision": "old", "items": []}
    proj = project_resolved(
        data,
        source_path=Path("resolved.json"),
        input_revision="from-ctx",
    )
    assert proj.input_revision == "from-ctx"
    assert proj.devices == []

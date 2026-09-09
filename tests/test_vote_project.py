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


def test_project_key_spec_preferred_when_truncating():
    items = []
    for i, name in enumerate(
        [
            "前沿通信能力",
            "声学与音频",
            "智能传感与交互",
            "AI底层能力",
            "核心宣发亮点与差异化功能",
            "发布时间",
            "起售价",
            "电池容量",
            "充电功率",
            "防水和防护",
            "核心算力与存储",
            "屏幕显示技术",
            "功耗与续航管理",
            "额外字段甲",
            "额外字段乙",
        ]
    ):
        items.append(
            {
                "device_id": "phone:a:m1",
                "brand": "A",
                "model": "M1",
                "field_name": name,
                "display_text": f"v{i}",
                "policy": "unanimous",
            }
        )
    data = {"category": "phone", "input_revision": "rev-2", "items": items}
    key_specs = {
        "起售价",
        "电池容量",
        "充电功率",
        "防水和防护",
        "核心算力与存储",
        "屏幕显示技术",
    }
    proj = project_resolved(
        data,
        source_path=Path("resolved.json"),
        key_spec_names=key_specs,
    )
    names = [n for n, _ in proj.devices[0].fields]
    assert len(names) == 14
    for k in key_specs:
        assert k in names
    assert "额外字段乙" not in names

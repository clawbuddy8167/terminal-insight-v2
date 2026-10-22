"""AI view: parse + quadrant."""
from __future__ import annotations

from terminal_insight_v2.ai_view.models import CAPABILITY_STAGES, stage_rank
from terminal_insight_v2.ai_view.parse import parse_ai_cards
from terminal_insight_v2.ai_view.service import build_ai_quadrant


def _resolved(items):
    return {"category": "phone", "run_id": "test", "items": items}


def test_stage_rank_ordering():
    assert stage_rank("单点AI辅助") == 1
    assert stage_rank("感知与理解") == 2
    assert stage_rank("长期记忆") == 3
    assert stage_rank("Agent执行") == 4
    assert stage_rank("安全与服务") == 5
    assert stage_rank("待判断") is None
    assert stage_rank("未知") is None
    assert stage_rank("") is None
    assert stage_rank("不存在的阶段") is None


def test_parse_ai_cards_splits_fields():
    items = [
        {"device_id": "d1", "brand": "OPPO", "model": "Find X9",
         "field_name": "起售价", "display_text": "4999元"},
        {"device_id": "d1", "brand": "OPPO", "model": "Find X9",
         "field_name": "AI最高能力阶段", "display_text": "Agent执行"},
        {"device_id": "d1", "brand": "OPPO", "model": "Find X9",
         "field_name": "Agent执行", "display_text": "是"},
        {"device_id": "d1", "brand": "OPPO", "model": "Find X9",
         "field_name": "持续感知", "display_text": "未知"},
        {"device_id": "d1", "brand": "OPPO", "model": "Find X9",
         "field_name": "长期记忆", "display_text": "否"},
        {"device_id": "d1", "brand": "OPPO", "model": "Find X9",
         "field_name": "AI底层能力", "display_text": "YOYO 智能体、AI会议参谋"},
        {"device_id": "d2", "brand": "vivo", "model": "X300",
         "field_name": "起售价", "display_text": "3999元"},
        {"device_id": "d2", "brand": "vivo", "model": "X300",
         "field_name": "AI最高能力阶段", "display_text": "待判断"},
    ]
    cards = parse_ai_cards(_resolved(items))
    assert len(cards) == 2
    d1 = next(c for c in cards if c.device_id == "d1")
    assert d1.price == 4999.0
    assert d1.price_band == "中高端"
    assert d1.stage_rank == 4
    assert d1.agent_exec is True
    assert d1.continuous_sense is None
    assert d1.long_memory is False
    assert d1.bool_score == 1
    assert "YOYO" in d1.ai_features
    d2 = next(c for c in cards if c.device_id == "d2")
    assert d2.stage_rank is None
    assert d2.assessed is False


def test_build_ai_quadrant_separates_assessed():
    items = [
        {"device_id": "d1", "brand": "A", "model": "M1",
         "field_name": "起售价", "display_text": "4999元"},
        {"device_id": "d1", "brand": "A", "model": "M1",
         "field_name": "AI最高能力阶段", "display_text": "Agent执行"},
        {"device_id": "d2", "brand": "B", "model": "M2",
         "field_name": "起售价", "display_text": "1999元"},
        {"device_id": "d2", "brand": "B", "model": "M2",
         "field_name": "AI最高能力阶段", "display_text": "待判断"},
        {"device_id": "d3", "brand": "C", "model": "M3",
         "field_name": "AI最高能力阶段", "display_text": "感知与理解"},
    ]
    art = build_ai_quadrant(
        run_id="t", category="phone", resolved=_resolved(items)
    )
    assert len(art.points) == 1
    assert art.points[0].stage_label == "Agent执行"
    assert art.points[0].y == 4.0
    assert len(art.unassessed) == 1
    assert art.unassessed[0].device_id == "d2"
    assert len(art.skipped_no_price) == 1
    assert art.skipped_no_price[0].device_id == "d3"
    assert art.stage_counts["Agent执行"] == 1
    assert art.origin_x_median == 4999.0


def test_stage_ladder_has_five():
    assert len(CAPABILITY_STAGES) == 5

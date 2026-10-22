"""Parse resolved.json items into DeviceAICard objects."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

from .models import DeviceAICard, UNASSESSED, stage_rank

_TRUE = frozenset({"是", "true", "yes", "1", "支持"})
_FALSE = frozenset({"否", "false", "no", "0", "不支持"})

_PRICE_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _parse_bool(text: str) -> Optional[bool]:
    t = (text or "").strip().lower()
    if t in UNASSESSED or t in {"", "待判断", "未知"}:
        return None
    if t in _TRUE:
        return True
    if t in _FALSE:
        return False
    return None


def _parse_price(text: str) -> Optional[float]:
    m = _PRICE_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _price_band(price: Optional[float]) -> str:
    if price is None:
        return ""
    if price < 2000:
        return "入门"
    if price < 4000:
        return "中端"
    if price < 6000:
        return "中高端"
    return "旗舰"


def parse_ai_cards(resolved: Mapping[str, Any]) -> List[DeviceAICard]:
    """Group resolved items by device and build AI capability cards."""
    items = resolved.get("items") or []
    if not isinstance(items, list):
        return []
    cards: Dict[str, DeviceAICard] = {}
    for it in items:
        if not isinstance(it, Mapping):
            continue
        device_id = str(it.get("device_id") or "").strip()
        if not device_id:
            continue
        card = cards.get(device_id)
        if card is None:
            card = DeviceAICard(
                device_id=device_id,
                brand=str(it.get("brand") or "").strip(),
                model=str(it.get("model") or "").strip(),
            )
            cards[device_id] = card
        field = str(it.get("field_name") or "").strip()
        text = str(it.get("display_text") or "").strip()
        if field == "起售价":
            card.price = _parse_price(text)
            card.price_band = _price_band(card.price)
        elif field == "AI最高能力阶段":
            card.stage_raw = text
            card.stage_rank = stage_rank(text)
        elif field == "Agent执行":
            card.agent_exec = _parse_bool(text)
        elif field == "持续感知":
            card.continuous_sense = _parse_bool(text)
        elif field == "长期记忆":
            card.long_memory = _parse_bool(text)
        elif field == "AI主要交互入口":
            card.ai_entry = text
        elif field == "AI原生程度":
            card.ai_native = text
        elif field == "AI功能标签":
            card.ai_tags = text
        elif field in ("AI底层能力", "接入AI大模型", "传感器与健康"):
            # Long-form AI description — keep the richest one.
            if len(text) > len(card.ai_features):
                card.ai_features = text
    return list(cards.values())

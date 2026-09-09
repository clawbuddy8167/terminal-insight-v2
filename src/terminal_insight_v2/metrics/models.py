"""Typed metric values derived from resolved display_text."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

MetricKind = Literal["price", "mah", "watt", "weight_g"]

PriceBand = Literal["入门", "中端", "中高端", "旗舰"]


class ParsedValue(BaseModel):
    kind: MetricKind
    value: float
    unit: str
    source_field: str
    dedicated: bool = False
    raw: str = ""


class DeviceMetrics(BaseModel):
    device_id: str
    brand: str = ""
    model: str = ""
    values: Dict[MetricKind, ParsedValue] = Field(default_factory=dict)
    price_band: Optional[PriceBand] = None

    def get(self, kind: MetricKind) -> Optional[float]:
        pv = self.values.get(kind)
        return None if pv is None else pv.value

"""Quadrant artifact contracts."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

YAxisKind = Literal["mah", "watt"]


class AxisSpec(BaseModel):
    kind: str
    label: str
    unit: str


class OriginSpec(BaseModel):
    x_median: float
    y_median: float


class QuadrantPoint(BaseModel):
    device_id: str
    brand: str = ""
    model: str = ""
    x: float
    y: float
    y_kind: YAxisKind = "mah"
    price_band: Optional[str] = None
    nominated_by: List[str] = Field(default_factory=list)


class SkippedDevice(BaseModel):
    device_id: str
    brand: str = ""
    model: str = ""
    reason: str


class QuadrantArtifact(BaseModel):
    schema_version: int = 1
    run_id: str
    category: str = ""
    slice_note: str = "CCC 切片：价位 × 硬指标；非六参考系综合地图"
    axes: dict = Field(default_factory=dict)
    origin: Optional[OriginSpec] = None
    points: List[QuadrantPoint] = Field(default_factory=list)
    points_watt: List[QuadrantPoint] = Field(default_factory=list)
    skipped: List[SkippedDevice] = Field(default_factory=list)
    quadrant_labels: dict = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)

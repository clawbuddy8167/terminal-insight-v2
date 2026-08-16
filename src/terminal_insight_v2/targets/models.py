"""Contracts for targeted collect (one row = one device)."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class DeviceTarget(BaseModel):
    brand: str
    model: str


class ParseIssue(BaseModel):
    line_no: int
    raw: str
    reason: str


class ParseTargetsResult(BaseModel):
    targets: List[DeviceTarget] = Field(default_factory=list)
    errors: List[ParseIssue] = Field(default_factory=list)

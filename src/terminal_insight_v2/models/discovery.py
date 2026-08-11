"""Discovery / collect domain models."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class DiscoveredDevice(BaseModel):
    brand: str
    model: str
    release_date: str = ""
    category: str = "phone"
    discovery_sources: List[str] = Field(default_factory=list)


class DeviceList(BaseModel):
    devices: List[DiscoveredDevice] = Field(default_factory=list)

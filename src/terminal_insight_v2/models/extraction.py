"""LLM extraction payload models."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    name: str
    value: str = ""
    snippet: str = ""


class ExtractSnapshotPayload(BaseModel):
    fields: List[ExtractedField] = Field(default_factory=list)

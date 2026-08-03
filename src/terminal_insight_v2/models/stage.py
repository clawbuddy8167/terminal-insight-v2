"""Stage protocol I/O models."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class StageContext(BaseModel):
    run_id: str
    category: str
    schema_fingerprint: str = ""
    device_ids: Optional[List[str]] = None
    backfill_round: int = 0
    date_start: str = ""
    date_end: str = ""
    input_revision: str = ""
    run_dir: str = ""
    extras: Dict[str, Any] = Field(default_factory=dict)


class StageResult(BaseModel):
    stage: str
    status: Literal["ok", "partial", "failed", "skipped"] = "ok"
    output_revision: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)

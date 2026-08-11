"""Search hit model (Doubao / Tavily)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SourceHit(BaseModel):
    url: str = ""
    title: str = ""
    site_name: str = ""
    snippet: str = ""
    rank_score: Optional[float] = None

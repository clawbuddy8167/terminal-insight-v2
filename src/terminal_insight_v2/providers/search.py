"""Search provider protocol + Doubao / Tavily selection."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Sequence

from rich.console import Console

from terminal_insight_v2.config import Settings
from terminal_insight_v2.models.source_hit import SourceHit
from terminal_insight_v2.providers.doubao import DoubaoProvider
from terminal_insight_v2.providers.tavily import TavilyProvider

console = Console()


class SearchProvider(Protocol):
    call_count: int

    def search(
        self,
        query: str,
        *,
        count: Optional[int] = None,
        sites: Optional[Sequence[str]] = None,
        need_content: bool = False,
    ) -> Dict[str, Any]: ...

    def hits(self, body: Dict[str, Any]) -> List[SourceHit]: ...


def format_hits_for_llm(hits: List[SourceHit], *, query: str = "") -> str:
    return DoubaoProvider.format_hits_for_llm(hits, query=query)


def resolve_search_provider(settings: Settings) -> SearchProvider:
    """Pick search backend: auto prefers Doubao, falls back to Tavily on probe failure."""
    backend = (settings.discovery_backend or "auto").strip().lower()
    has_doubao = bool((settings.doubao_api_key or "").strip())
    has_tavily = bool((settings.tavily_api_key or "").strip())

    if backend == "tavily":
        if not has_tavily:
            raise RuntimeError("DISCOVERY_BACKEND=tavily but TAVILY_API_KEY is empty")
        console.log("[search] using Tavily")
        return TavilyProvider(settings)

    if backend == "doubao":
        if not has_doubao:
            raise RuntimeError("DISCOVERY_BACKEND=doubao but DOUBAO_API_KEY is empty")
        console.log("[search] using Doubao")
        return DoubaoProvider(settings)

    # auto
    if has_doubao:
        doubao = DoubaoProvider(settings)
        try:
            doubao.search("smartwatch", count=1)
            console.log("[search] using Doubao")
            return doubao
        except Exception as exc:  # noqa: BLE001
            console.log(f"[search] Doubao unavailable ({exc}); trying Tavily")
    if has_tavily:
        console.log("[search] using Tavily")
        return TavilyProvider(settings)
    raise RuntimeError("No search backend available: set DOUBAO_API_KEY or TAVILY_API_KEY")

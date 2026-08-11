"""Tavily Search API client (discovery / URL planning fallback)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import httpx

from terminal_insight_v2.config import Settings
from terminal_insight_v2.models.source_hit import SourceHit

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.call_count = 0

    def search(
        self,
        query: str,
        *,
        count: Optional[int] = None,
        sites: Optional[Sequence[str]] = None,
        need_content: bool = False,
    ) -> Dict[str, Any]:
        key = (self.settings.tavily_api_key or "").strip()
        if not key:
            raise RuntimeError("TAVILY_API_KEY is not set")
        q = (query or "").strip()
        if not q:
            raise ValueError("Tavily query must be non-empty")
        payload: Dict[str, Any] = {
            "api_key": key,
            "query": q,
            "max_results": count if count is not None else self.settings.tavily_max_results,
            "search_depth": self.settings.tavily_search_depth,
            "include_answer": False,
            "topic": "general",
        }
        if sites:
            cleaned = [s.strip() for s in sites if (s or "").strip()]
            if cleaned:
                payload["include_domains"] = cleaned[:10]
        timeout = httpx.Timeout(self.settings.tavily_timeout)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(TAVILY_SEARCH_URL, json=payload)
            resp.raise_for_status()
            body = resp.json()
        body["query"] = q
        self.call_count += 1
        return body

    def hits(self, body: Dict[str, Any]) -> List[SourceHit]:
        out: List[SourceHit] = []
        for hit in body.get("results") or []:
            url = (hit.get("url") or "").strip()
            content = (hit.get("content") or "").strip()
            score = hit.get("score")
            out.append(
                SourceHit(
                    url=url,
                    title=(hit.get("title") or "").strip(),
                    site_name="",
                    snippet=content[:800],
                    rank_score=float(score) if isinstance(score, (int, float)) else None,
                )
            )
        return out

    @staticmethod
    def format_hits_for_llm(hits: List[SourceHit], *, query: str = "") -> str:
        lines: List[str] = []
        if query:
            lines.append(f"### 检索: {query}")
        for idx, hit in enumerate(hits, start=1):
            lines.append(f"[{idx}] {hit.title}")
            if hit.url:
                lines.append(f"    URL: {hit.url}")
            if hit.snippet:
                sn = hit.snippet.replace("\n", " ").strip()
                lines.append(f"    摘要: {sn[:480]}{'…' if len(hit.snippet) > 480 else ''}")
        return "\n".join(lines).strip()

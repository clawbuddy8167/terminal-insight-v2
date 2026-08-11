"""Doubao Search API client."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Sequence

import httpx

from terminal_insight_v2.config import Settings
from terminal_insight_v2.models.source_hit import SourceHit

DOUBAO_SEARCH_URL = "https://open.feedcoopapi.com/search_api/web_search"
DOUBAO_QUERY_MAX_LEN = 100


class DoubaoSearchError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(f"Doubao search error {code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable


class _SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timestamps: Deque[float] = deque()

    def acquire(self, qps: float) -> None:
        limit = max(0.1, float(qps))
        capacity = max(1, int(limit) if limit == int(limit) else int(limit) + 1)
        while True:
            sleep_for = 0.0
            with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= 1.0:
                    self._timestamps.popleft()
                if len(self._timestamps) < capacity:
                    self._timestamps.append(now)
                    return
                sleep_for = 1.0 - (now - self._timestamps[0]) + 0.001
            time.sleep(max(0.01, sleep_for))


def truncate_query(query: str) -> str:
    q = (query or "").strip()
    if len(q) <= DOUBAO_QUERY_MAX_LEN:
        return q
    return q[:DOUBAO_QUERY_MAX_LEN]


class DoubaoProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._limiter = _SlidingWindowRateLimiter()
        self.call_count = 0
        self.retry_count = 0
        self._lock = threading.Lock()

    def search(
        self,
        query: str,
        *,
        count: Optional[int] = None,
        sites: Optional[Sequence[str]] = None,
        need_content: bool = False,
    ) -> Dict[str, Any]:
        key = (self.settings.doubao_api_key or "").strip()
        if not key:
            raise RuntimeError("DOUBAO_API_KEY is not set")
        q = truncate_query(query)
        if not q:
            raise ValueError("Doubao search Query must be non-empty")

        max_retries = max(0, int(self.settings.doubao_max_retries))
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                self._limiter.acquire(self.settings.doubao_max_qps)
                body = self._post(q, key=key, count=count, sites=sites, need_content=need_content)
                with self._lock:
                    self.call_count += 1
                return body
            except DoubaoSearchError as exc:
                last_exc = exc
                if not exc.retryable or attempt >= max_retries:
                    raise
                with self._lock:
                    self.retry_count += 1
                time.sleep(min(8.0, 0.8 * (2**attempt)))
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                retryable = True
                if isinstance(exc, httpx.HTTPStatusError):
                    retryable = exc.response.status_code in (408, 425, 429, 500, 502, 503, 504)
                if not retryable or attempt >= max_retries:
                    raise
                with self._lock:
                    self.retry_count += 1
                time.sleep(min(8.0, 0.8 * (2**attempt)))
        raise last_exc or RuntimeError("Doubao search failed")

    def _post(
        self,
        query: str,
        *,
        key: str,
        count: Optional[int],
        sites: Optional[Sequence[str]],
        need_content: bool,
    ) -> Dict[str, Any]:
        filt: Dict[str, Any] = {"NeedContent": bool(need_content), "NeedUrl": True}
        if sites:
            cleaned = [s.strip() for s in sites if (s or "").strip()]
            if cleaned:
                filt["Sites"] = "|".join(cleaned[:20])
        payload: Dict[str, Any] = {
            "Query": query,
            "SearchType": "web",
            "Count": count if count is not None else self.settings.doubao_max_results,
            "Filter": filt,
        }
        fmt = (self.settings.doubao_content_formats or "text").strip()
        if fmt:
            payload["ContentFormats"] = fmt
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(self.settings.doubao_timeout)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(DOUBAO_SEARCH_URL, json=payload, headers=headers)
            if resp.status_code in (408, 425, 429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            body = resp.json()
        meta = body.get("ResponseMetadata") or {}
        err = meta.get("Error")
        if err:
            code = str(err.get("Code") or err.get("CodeN") or "?")
            msg = err.get("Message") or str(err)
            retryable = code in {"700429", "429", "RateLimit", "InternalError"}
            raise DoubaoSearchError(code, msg, retryable=retryable)
        body["query"] = query
        return body

    def hits(self, body: Dict[str, Any]) -> List[SourceHit]:
        out: List[SourceHit] = []
        result = body.get("Result") or {}
        for hit in result.get("WebResults") or []:
            url = (hit.get("Url") or "").strip()
            snippet = ""
            for key in ("Summary", "Content", "Snippet"):
                text = (hit.get(key) or "").strip()
                if text:
                    snippet = text
                    break
            score = hit.get("RankScore")
            out.append(
                SourceHit(
                    url=url,
                    title=(hit.get("Title") or "").strip(),
                    site_name=(hit.get("SiteName") or "").strip(),
                    snippet=snippet[:800],
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
            site_s = f" · {hit.site_name}" if hit.site_name else ""
            lines.append(f"[{idx}] {hit.title}{site_s}")
            if hit.url:
                lines.append(f"    URL: {hit.url}")
            if hit.snippet:
                sn = hit.snippet.replace("\n", " ").strip()
                lines.append(f"    摘要: {sn[:480]}{'…' if len(hit.snippet) > 480 else ''}")
        return "\n".join(lines).strip()

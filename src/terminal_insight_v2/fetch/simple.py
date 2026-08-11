"""HTTP fetch with optional Jina Reader fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from terminal_insight_v2.config import Settings


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    http_status: int = 0
    fetch_method: str = ""
    raw_html: str = ""
    content_md: str = ""
    raw_status: str = "failed"  # ok | markdown_only | failed
    error: str = ""


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n\n".join(lines)


def _jina_reader(url: str, *, timeout: float) -> FetchResult:
    reader_url = f"https://r.jina.ai/{url}"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(reader_url, headers={"Accept": "text/plain"})
            body = resp.text or ""
            if len(body.strip()) < 80:
                return FetchResult(url=url, fetch_method="jina_reader", error="empty jina body")
            return FetchResult(
                url=url,
                final_url=url,
                http_status=resp.status_code,
                fetch_method="jina_reader",
                content_md=body.strip(),
                raw_status="markdown_only",
            )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(url=url, fetch_method="jina_reader", error=str(exc))


def fetch_url(url: str, settings: Settings) -> FetchResult:
    u = (url or "").strip()
    if not u.startswith("http"):
        return FetchResult(url=u, error="invalid url")
    timeout = float(settings.http_timeout)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; TerminalInsight/2.0; +https://example.local/bot)"
        ),
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(u, headers=headers)
            ctype = (resp.headers.get("content-type") or "").lower()
            text = resp.text or ""
            final = str(resp.url)
            if "html" in ctype and len(text) > 200:
                md = _html_to_text(text)
                if len(md) >= max(80, settings.fetch_min_body_len // 3):
                    return FetchResult(
                        url=u,
                        final_url=final,
                        http_status=resp.status_code,
                        fetch_method="http_get",
                        raw_html=text[:2_000_000],
                        content_md=md,
                        raw_status="ok",
                    )
            if len(text.strip()) >= settings.fetch_min_body_len and "html" not in ctype:
                return FetchResult(
                    url=u,
                    final_url=final,
                    http_status=resp.status_code,
                    fetch_method="http_get",
                    content_md=text.strip(),
                    raw_status="markdown_only",
                )
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        if settings.jina_reader_enabled:
            j = _jina_reader(u, timeout=timeout + 30)
            if j.raw_status != "failed":
                return j
            return FetchResult(url=u, fetch_method="http_get", error=err)
        return FetchResult(url=u, fetch_method="http_get", error=err)

    if settings.jina_reader_enabled:
        j = _jina_reader(u, timeout=timeout + 30)
        if j.raw_status != "failed":
            return j
    return FetchResult(url=u, fetch_method="http_get", error="body too short")

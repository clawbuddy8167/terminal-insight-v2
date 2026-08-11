"""Plan candidate source URLs per device."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence
from urllib.parse import urlparse

from terminal_insight_v2.category.schema import CategorySchema
from terminal_insight_v2.config import Settings
from terminal_insight_v2.models.discovery import DiscoveredDevice
from terminal_insight_v2.models.source_hit import SourceHit
from terminal_insight_v2.providers.doubao import truncate_query
from terminal_insight_v2.providers.search import SearchProvider


@dataclass
class PlannedUrl:
    url: str
    title: str = ""
    site: str = ""
    link_role: str = "third_party"
    tier: str = "web"
    source_kind: str = "web"
    discovered_by: str = "collect"


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").replace("www.", "")
    except Exception:
        return ""


def tier_for_url(url: str, schema: CategorySchema) -> tuple[str, str, str]:
    """Return (tier, source_kind, link_role) for a URL against category named sources."""
    host = _host(url)
    for src in schema.sources:
        if not src.enabled:
            continue
        for dom in src.domains:
            if dom and dom in host:
                role = "official_spec" if src.source_kind == "official_spec" else (
                    "official_mall" if src.source_kind == "official_mall" else "named"
                )
                return src.tier, src.source_kind, role
    return "P3", "web", "third_party"


def plan_urls_for_device(
    dev: DiscoveredDevice,
    schema: CategorySchema,
    settings: Settings,
    *,
    search: SearchProvider,
    extra_hits: Sequence[SourceHit] = (),
    max_urls: Optional[int] = None,
) -> List[PlannedUrl]:
    cap = max_urls if max_urls is not None else settings.collect_max_urls_per_device
    seen: set[str] = set()
    out: List[PlannedUrl] = []

    def add(url: str, title: str = "", site: str = "", by: str = "discovery") -> None:
        u = (url or "").strip()
        if not u.startswith("http"):
            return
        key = u.rstrip("/").lower()
        if key in seen:
            return
        seen.add(key)
        tier, kind, role = tier_for_url(u, schema)
        out.append(
            PlannedUrl(
                url=u,
                title=title,
                site=site or _host(u),
                link_role=role,
                tier=tier,
                source_kind=kind,
                discovered_by=by,
            )
        )

    for u in dev.discovery_sources:
        add(u, by="discovery_list")

    product = schema.discovery.product
    q = truncate_query(f"{dev.brand} {dev.model} {product} 参数 评测")
    try:
        body = search.search(q)
        for hit in search.hits(body):
            add(hit.url, hit.title, hit.site_name, "search")
    except Exception:
        pass

    for hit in extra_hits:
        blob = f"{hit.title} {hit.snippet} {dev.brand} {dev.model}"
        if dev.brand in blob or dev.model in blob:
            add(hit.url, hit.title, hit.site_name, "discovery_pool")

    for src in sorted(schema.sources, key=lambda s: s.priority):
        if not src.enabled or not src.auto_search:
            continue
        for dom in src.domains[:3]:
            sq = truncate_query(f"{dev.brand} {dev.model} site:{dom}")
            try:
                body = search.search(sq, sites=[dom])
                for hit in search.hits(body):
                    add(hit.url, hit.title, hit.site_name, f"named:{src.source_key}")
            except Exception:
                continue

    return out[: max(1, cap)]

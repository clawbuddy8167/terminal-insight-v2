"""Device discovery via search (Doubao/Tavily) + LLM."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from rich.console import Console

from terminal_insight_v2.category.schema import CategorySchema
from terminal_insight_v2.config import Settings
from terminal_insight_v2.models.discovery import DeviceList, DiscoveredDevice
from terminal_insight_v2.models.source_hit import SourceHit
from terminal_insight_v2.prompts import discovery_system, discovery_user
from terminal_insight_v2.providers.llm import LLMProvider
from terminal_insight_v2.providers.search import SearchProvider, format_hits_for_llm, resolve_search_provider

console = Console()


_ENGLISH_PRODUCT = {
    "phone": "smartphone",
    "watch": "smartwatch",
    "glasses": "AI glasses",
}


def build_discovery_queries(schema: CategorySchema, date_start: str, date_end: str) -> List[str]:
    product = schema.discovery.product
    english = _ENGLISH_PRODUCT.get(schema.category_id, product)
    queries = [
        f"{date_start}到{date_end}发布的{product}新品 上市",
        f"{date_start} {date_end} {product} 发布会 新品",
        f"{english} launched {date_start} {date_end}",
        f"new {english} release {date_start} to {date_end}",
        f"全球 {product} {date_start}到{date_end} 发布 新品",
    ]
    for brand in schema.discovery.search_brands[:10]:
        queries.append(f"{brand} {product} {date_start}到{date_end} 发布")
    seen: set[str] = set()
    out: List[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def discover_devices(
    schema: CategorySchema,
    settings: Settings,
    *,
    date_start: str,
    date_end: str,
    search: Optional[SearchProvider] = None,
    llm: Optional[LLMProvider] = None,
) -> tuple[List[DiscoveredDevice], List[SourceHit]]:
    search = search or resolve_search_provider(settings)
    llm = llm or LLMProvider(settings)
    queries = build_discovery_queries(schema, date_start, date_end)
    workers = max(1, settings.discover_max_workers)
    bodies = []
    console.log(f"[discover] {len(queries)} queries, workers={workers}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(search.search, q): q for q in queries}
        for fut in as_completed(futs):
            q = futs[fut]
            try:
                bodies.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                console.log(f"[discover] query failed {q!r}: {exc}")

    hits: List[SourceHit] = []
    for body in bodies:
        hits.extend(search.hits(body))
    context = format_hits_for_llm(hits)
    if not context.strip():
        console.log("[discover] empty context")
        return [], hits

    parsed = llm.chat_json(
        discovery_system(schema),
        discovery_user(schema, date_start, date_end, context),
        DeviceList,
        temperature=0.1,
        max_tokens=8192,
    )
    seen: set[tuple[str, str]] = set()
    devices: List[DiscoveredDevice] = []
    urls = [h.url for h in hits if h.url][:20]
    for d in parsed.devices:
        brand = (d.brand or "").strip()
        model = (d.model or "").strip()
        if not brand or not model:
            continue
        key = (brand.lower(), model.lower())
        if key in seen:
            continue
        seen.add(key)
        devices.append(
            DiscoveredDevice(
                brand=brand,
                model=model,
                release_date=(d.release_date or "").strip(),
                category=schema.category_id,
                discovery_sources=urls[:5],
            )
        )
    console.log(f"[discover] {len(devices)} devices")
    return devices, hits

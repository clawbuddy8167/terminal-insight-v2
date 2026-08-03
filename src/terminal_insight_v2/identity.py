"""Stable device / source identity helpers."""
from __future__ import annotations

import hashlib
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse, urlunparse

_BRAND_ALIASES = {
    "红米": "Redmi",
    "redmi": "Redmi",
    "xiaomi": "小米",
    "mi": "小米",
    "huawei": "华为",
    "honor": "荣耀",
    "oppo": "OPPO",
    "vivo": "vivo",
    "iqoo": "iQOO",
    "samsung": "三星",
    "apple": "Apple",
    "苹果": "Apple",
    "oneplus": "一加",
    "realme": "真我",
    "nubia": "努比亚",
}

_NORM_STRIP = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_STORAGE_SUFFIX = re.compile(
    r"[\s\-_]*(?:\d+\s*\+\s*)?\d+\s*(?:GB|TB|G|T)(?:\s*/\s*(?:\d+\s*\+\s*)?\d+\s*(?:GB|TB|G|T))*\s*$",
    re.I,
)


def _stable_norm(text: str) -> str:
    s = (text or "").strip().lower().replace("\u3000", "")
    return _NORM_STRIP.sub("", s)


def canonical_brand(brand: str) -> str:
    raw = (brand or "").strip()
    if not raw:
        return ""
    return _BRAND_ALIASES.get(raw) or _BRAND_ALIASES.get(raw.lower()) or raw


def brand_norm(brand: str) -> str:
    return _stable_norm(canonical_brand(brand))


def base_model_name(model: str) -> str:
    s = (model or "").strip()
    s = _STORAGE_SUFFIX.sub("", s).strip()
    return s or (model or "").strip()


def model_norm(model: str) -> str:
    return _stable_norm(base_model_name(model))


def device_id(
    category: str,
    brand: str,
    model: str,
    *,
    region: str = "CN",
) -> str:
    cat = (category or "phone").strip().lower() or "phone"
    bn = brand_norm(brand) or _stable_norm(brand)
    mn = model_norm(model) or _stable_norm(model)
    reg = (region or "CN").strip().upper() or "CN"
    if reg == "CN":
        return f"{cat}:{bn}:{mn}"
    return f"{cat}:{bn}:{mn}:{reg.lower()}"


def normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # Strip common reader prefixes
    for prefix in ("https://r.jina.ai/", "http://r.jina.ai/"):
        if u.startswith(prefix):
            u = u[len(prefix) :]
            break
    parsed = urlparse(u)
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # Drop tracking query keys
    drop = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "spm"}
    q = parse_qs(parsed.query, keep_blank_values=False)
    kept = {k: v for k, v in q.items() if k.lower() not in drop}
    query = "&".join(
        f"{k}={v[0]}" if len(v) == 1 else "&".join(f"{k}={x}" for x in v)
        for k, v in sorted(kept.items())
    )
    return urlunparse((scheme, netloc, path, "", query, ""))


def source_id(url: str) -> Optional[str]:
    norm = normalize_url(url)
    if not norm.startswith("http"):
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def content_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def blob_id_from_sha(sha256: str) -> str:
    return f"blob:{sha256[:32]}"


__all__ = [
    "base_model_name",
    "blob_id_from_sha",
    "brand_norm",
    "canonical_brand",
    "content_sha256",
    "device_id",
    "model_norm",
    "normalize_url",
    "source_id",
]

"""Stable device / source identity helpers."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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


@dataclass(frozen=True)
class UrlMatchVerdict:
    ok: bool
    reason: str = ""


_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TOKEN_SPLIT = re.compile(r"[\s\-_/·•]+")
_SIBLING_SUFFIXES = ("proplus", "pro+", "pro", "ultra", "plus", "max", "turbo", "supreme", "leading")


def compact_key(text: str) -> str:
    return _NON_ALNUM.sub("", (text or "").lower())


def model_tokens(model: str) -> list[str]:
    out: list[str] = []
    for raw in _TOKEN_SPLIT.split((model or "").strip()):
        tok = compact_key(raw)
        if len(tok) >= 2:
            out.append(tok)
    return out


def page_has_sibling_upgrade(blob: str, model: str) -> bool:
    if not blob or not model:
        return False
    norm = compact_key(blob)
    key = compact_key(model)
    if not norm or not key:
        return False
    for suf in _SIBLING_SUFFIXES:
        if key.endswith(suf):
            continue
        if (key + suf) in norm:
            return True
    m = re.match(r"^((?:[a-z]+)?\d+)([a-z]{0,4})$", key)
    if not m:
        return False
    base, claimed_suf = m.group(1), m.group(2)
    if not claimed_suf:
        for probe in ("pro", "ultra", "plus", "max", "e", "s", "t", "i"):
            if (base + probe) in norm:
                return True
    return False


def blob_matches_model(blob: str, brand: str, model: str) -> UrlMatchVerdict:
    """Heuristic: page text must mention target model."""
    text = f"{blob or ''}"
    if not model.strip():
        return UrlMatchVerdict(True, reason="empty_model_skip")
    norm = compact_key(text)
    key = compact_key(model)
    brand_key = compact_key(brand)
    if not key:
        return UrlMatchVerdict(True, reason="empty_key")
    if key not in norm:
        toks = model_tokens(model)
        if not (toks and all(t in norm for t in toks)):
            return UrlMatchVerdict(False, reason="model_not_found")
    if page_has_sibling_upgrade(text, model):
        return UrlMatchVerdict(False, reason="sibling_upgrade")
    if brand_key and len(brand_key) >= 2 and brand_key not in norm:
        return UrlMatchVerdict(True, reason="brand_soft_miss")
    return UrlMatchVerdict(True, reason="ok")


__all__ = [
    "UrlMatchVerdict",
    "base_model_name",
    "blob_id_from_sha",
    "blob_matches_model",
    "brand_norm",
    "canonical_brand",
    "compact_key",
    "content_sha256",
    "device_id",
    "model_norm",
    "model_tokens",
    "normalize_url",
    "source_id",
]

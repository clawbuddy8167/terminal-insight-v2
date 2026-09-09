"""Parse display_text into price / mAh / W / g using schema validators."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from terminal_insight_v2.category.schema import FieldDef

from .models import DeviceMetrics, MetricKind, ParsedValue, PriceBand

_MAH = re.compile(r"(\d+(?:\.\d+)?)\s*mAh", re.I)
_WATT = re.compile(r"(\d+(?:\.\d+)?)\s*W\b", re.I)
# Avoid matching 5G as watt: require W with word boundary (already in _WATT)
_WEIGHT = re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.I)
# 1.2万 / 4499元起 / ¥3,299
_WAN = re.compile(r"(\d+(?:\.\d+)?)\s*万")
_PRICE_NUM = re.compile(r"(?:¥|￥)?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")


def price_band_cny(price: Optional[float]) -> Optional[PriceBand]:
    """Phone CNY bands (research view only — not a fact field)."""
    if price is None:
        return None
    if price < 2000:
        return "入门"
    if price < 4000:
        return "中端"
    if price < 6000:
        return "中高端"
    return "旗舰"


def parse_price(text: str) -> Optional[float]:
    t = (text or "").strip()
    if not t:
        return None
    m = _WAN.search(t)
    if m:
        return float(m.group(1)) * 10000.0
    m = _PRICE_NUM.search(t)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def parse_mah(text: str) -> Optional[float]:
    m = _MAH.search(text or "")
    return float(m.group(1)) if m else None


def parse_watt(text: str) -> Optional[float]:
    """Largest charge-like W token (5G is excluded by requiring a trailing W)."""
    matches = [float(m.group(1)) for m in _WATT.finditer(text or "")]
    if not matches:
        return None
    charge_like = [v for v in matches if 5 <= v <= 500]
    return max(charge_like) if charge_like else max(matches)


def parse_weight_g(text: str) -> Optional[float]:
    m = _WEIGHT.search(text or "")
    return float(m.group(1)) if m else None


_PARSERS = {
    "price": parse_price,
    "mah": parse_mah,
    "watt": parse_watt,
    "weight_g": parse_weight_g,
}

_UNITS = {"price": "元", "mah": "mAh", "watt": "W", "weight_g": "g"}


def metric_kinds_for_field(field: Optional[FieldDef], field_name: str = "") -> Set[MetricKind]:
    """Which metric kinds a field can yield, from data_type / validators."""
    kinds: Set[MetricKind] = set()
    if field is None:
        # Heuristic fallback when schema row missing (old runs / unknown fields)
        name = field_name
        if "价" in name or name in {"起售价"}:
            kinds.add("price")
        if "电池" in name or "续航" in name or "功耗" in name:
            kinds.add("mah")
            kinds.add("watt")
        if "充电" in name and "电池" not in name:
            kinds.add("watt")
        if "重量" in name:
            kinds.add("weight_g")
        return kinds

    if field.data_type == "price":
        kinds.add("price")
    vals = set(field.validators or [])
    if "mah" in vals:
        kinds.add("mah")
    if "watt" in vals:
        kinds.add("watt")
    if "weight_g" in vals:
        kinds.add("weight_g")
    if "has_digit" in vals and field.data_type == "price":
        kinds.add("price")
    return kinds


def is_dedicated(field: Optional[FieldDef], kind: MetricKind, field_name: str = "") -> bool:
    kinds = metric_kinds_for_field(field, field_name)
    return kind in kinds and len(kinds) == 1


def extract_from_text(
    text: str,
    kinds: Iterable[MetricKind],
    *,
    source_field: str,
    dedicated: bool,
) -> List[ParsedValue]:
    out: List[ParsedValue] = []
    for kind in kinds:
        parser = _PARSERS[kind]
        val = parser(text)
        if val is None:
            continue
        out.append(
            ParsedValue(
                kind=kind,
                value=val,
                unit=_UNITS[kind],
                source_field=source_field,
                dedicated=dedicated,
                raw=(text or "")[:120],
            )
        )
    return out


def _pick_best(candidates: List[ParsedValue]) -> Optional[ParsedValue]:
    if not candidates:
        return None
    dedicated = [c for c in candidates if c.dedicated]
    pool = dedicated if dedicated else candidates
    # Prefer larger absolute value for mah/watt when from same class of source
    return max(pool, key=lambda c: (c.dedicated, c.value))


def parse_device_fields(
    rows: Sequence[Mapping[str, Any]],
    field_defs: Optional[Mapping[str, FieldDef]] = None,
) -> DeviceMetrics:
    """Parse one device's resolved rows into DeviceMetrics."""
    defs = field_defs or {}
    device_id = ""
    brand = ""
    model = ""
    by_kind: Dict[MetricKind, List[ParsedValue]] = {
        "price": [],
        "mah": [],
        "watt": [],
        "weight_g": [],
    }

    for row in rows:
        did = str(row.get("device_id") or "").strip()
        if did and not device_id:
            device_id = did
        b = str(row.get("brand") or "").strip()
        if b and not brand:
            brand = b
        m = str(row.get("model") or "").strip()
        if m and not model:
            model = m
        if str(row.get("policy") or "") == "missing":
            continue
        fname = str(row.get("field_name") or "").strip()
        text = str(row.get("display_text") or "").strip()
        if not fname or not text:
            continue
        fdef = defs.get(fname)
        kinds = metric_kinds_for_field(fdef, fname)
        if not kinds:
            continue
        for pv in extract_from_text(
            text,
            kinds,
            source_field=fname,
            dedicated=False,
        ):
            pv.dedicated = is_dedicated(fdef, pv.kind, fname)
            by_kind[pv.kind].append(pv)

    values: Dict[MetricKind, ParsedValue] = {}
    for kind, cands in by_kind.items():
        best = _pick_best(cands)
        if best is not None:
            values[kind] = best

    price = values["price"].value if "price" in values else None
    return DeviceMetrics(
        device_id=device_id or f"{brand}:{model}".strip(":"),
        brand=brand,
        model=model,
        values=values,
        price_band=price_band_cny(price),
    )


def parse_resolved_items(
    items: Sequence[Mapping[str, Any]],
    field_defs: Optional[Mapping[str, FieldDef]] = None,
) -> List[DeviceMetrics]:
    """Group resolved items by device_id and parse metrics."""
    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    order: List[str] = []
    for row in items:
        if not isinstance(row, Mapping):
            continue
        did = str(row.get("device_id") or "").strip()
        brand = str(row.get("brand") or "").strip()
        model = str(row.get("model") or "").strip()
        if not did:
            did = f"{brand}:{model}".strip(":")
        if not did:
            continue
        if did not in grouped:
            grouped[did] = []
            order.append(did)
        grouped[did].append(row)
    return [parse_device_fields(grouped[did], field_defs) for did in order]

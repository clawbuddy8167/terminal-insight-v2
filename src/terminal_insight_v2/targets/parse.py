"""Deterministic parse of a brand/model paste box. One device per line."""
from __future__ import annotations

import re
from typing import List, Tuple

from terminal_insight_v2.identity import base_model_name, brand_norm, canonical_brand, model_norm

from .models import DeviceTarget, ParseIssue, ParseTargetsResult

_SPLIT = re.compile(r"\s*[|｜,\t，]\s*")
_META = re.compile(
    r"^(?:品类|时间|日期|category|date|window)\s*[:：]",
    re.I,
)
_DATE_LINE = re.compile(
    r"^(?:phone|watch|glasses|[a-z][a-z0-9_]*)?\s*"
    r"\d{4}-\d{2}-\d{2}\s*[~～—\-至到]\s*\d{4}-\d{2}-\d{2}\s*$",
    re.I,
)


def parse_target_text(text: str) -> ParseTargetsResult:
    """Parse pasted lines into unique brand+model pairs.

    Accepts ``品牌 | 型号``, tab, comma, or ``品牌 型号``.
    Skips blanks, ``#`` comments, and category/date header lines.
    Model-only lines are errors. Duplicate pairs are dropped.
    """
    targets: List[DeviceTarget] = []
    errors: List[ParseIssue] = []
    seen: set[Tuple[str, str]] = set()
    for idx, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip().replace("\u3000", " ")
        if not line or line.startswith("#") or _META.match(line) or _DATE_LINE.match(line):
            continue
        brand, model, reason = _split_line(line)
        if reason:
            errors.append(ParseIssue(line_no=idx, raw=raw, reason=reason))
            continue
        brand = canonical_brand(brand)
        model = base_model_name(model)
        key = (brand_norm(brand), model_norm(model))
        if key in seen:
            continue
        seen.add(key)
        targets.append(DeviceTarget(brand=brand, model=model))
    return ParseTargetsResult(targets=targets, errors=errors)


def _split_line(line: str) -> Tuple[str, str, str]:
    if _SPLIT.search(line):
        parts = [p.strip() for p in _SPLIT.split(line) if p.strip()]
        if len(parts) < 2:
            return "", "", "缺少型号"
        return parts[0], " ".join(parts[1:]), ""
    bits = line.split()
    if len(bits) < 2:
        return bits[0] if bits else "", "", "缺少型号"
    return bits[0], " ".join(bits[1:]), ""

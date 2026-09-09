"""Compress resolved.json into a token-bounded vote projection."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

IDENTITY_FIELDS = frozenset({"品牌", "机型"})
SKIP_POLICIES = frozenset({"missing"})
MAX_DEVICES = 48
MAX_FIELDS_PER_DEVICE = 14
MAX_VALUE_CHARS = 180


@dataclass
class DeviceCard:
    device_id: str
    brand: str
    model: str
    fields: List[tuple[str, str]] = field(default_factory=list)


@dataclass
class VoteProjection:
    category: str
    input_revision: str
    devices: List[DeviceCard]
    source_path: Path


def _items_from_resolved(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = data.get("items")
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return []


def revision_of(data: Dict[str, Any], fallback: str = "") -> str:
    existing = str(data.get("input_revision") or "").strip()
    if existing:
        return existing
    blob = json.dumps(data.get("items") or [], ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return fallback or f"resolved:{digest}"


def load_resolved(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"resolved.json 不是对象: {path}")
    return data


def _trim_fields(
    fields: List[tuple[str, str]],
    *,
    key_spec_names: Optional[Set[str]] = None,
    limit: int = MAX_FIELDS_PER_DEVICE,
) -> List[tuple[str, str]]:
    """Keep key_spec fields first, then fill remaining slots in encounter order."""
    if len(fields) <= limit:
        return fields
    keys = key_spec_names or set()
    primary = [f for f in fields if f[0] in keys]
    secondary = [f for f in fields if f[0] not in keys]
    kept = primary[:limit]
    if len(kept) < limit:
        kept.extend(secondary[: limit - len(kept)])
    return kept


def project_resolved(
    data: Dict[str, Any],
    *,
    source_path: Path,
    category: str = "",
    input_revision: str = "",
    key_spec_names: Optional[Sequence[str]] = None,
) -> VoteProjection:
    """Group non-empty spec fields by device; drop identity-only / missing noise."""
    key_set: Set[str] = set(key_spec_names or ())
    grouped: Dict[str, DeviceCard] = {}
    for row in _items_from_resolved(data):
        did = str(row.get("device_id") or "").strip()
        brand = str(row.get("brand") or "").strip()
        model = str(row.get("model") or "").strip()
        if not did:
            did = f"{brand}:{model}".strip(":")
        if not did:
            continue
        card = grouped.get(did)
        if card is None:
            card = DeviceCard(device_id=did, brand=brand, model=model)
            grouped[did] = card
        if brand and not card.brand:
            card.brand = brand
        if model and not card.model:
            card.model = model

        fname = str(row.get("field_name") or "").strip()
        if not fname or fname in IDENTITY_FIELDS:
            continue
        if str(row.get("policy") or "") in SKIP_POLICIES:
            continue
        text = str(row.get("display_text") or "").strip()
        if not text:
            continue
        card.fields.append((fname, text[:MAX_VALUE_CHARS]))

    cards = [c for c in grouped.values() if c.fields]
    cards.sort(key=lambda c: (-len(c.fields), c.brand, c.model))
    trimmed: List[DeviceCard] = []
    for card in cards[:MAX_DEVICES]:
        trimmed.append(
            DeviceCard(
                device_id=card.device_id,
                brand=card.brand,
                model=card.model,
                fields=_trim_fields(card.fields, key_spec_names=key_set),
            )
        )
    rev = (input_revision or "").strip() or revision_of(
        data, fallback=f"resolved:{source_path.name}"
    )
    return VoteProjection(
        category=category or str(data.get("category") or ""),
        input_revision=rev,
        devices=trimmed,
        source_path=source_path,
    )


def render_projection(projection: VoteProjection) -> str:
    if not projection.devices:
        return "（投影为空：resolved 中没有可投票的非空规格字段）"
    blocks: List[str] = []
    for card in projection.devices:
        lines = [f"### {card.brand} {card.model}".strip()]
        for name, value in card.fields:
            lines.append(f"- {name}：{value}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def project_from_path(
    path: Path,
    *,
    category: str = "",
    input_revision: str = "",
    key_spec_names: Optional[Sequence[str]] = None,
) -> VoteProjection:
    return project_resolved(
        load_resolved(path),
        source_path=path,
        category=category,
        input_revision=input_revision,
        key_spec_names=key_spec_names,
    )


def devices_index(projection: VoteProjection) -> Sequence[tuple[str, str]]:
    return [(c.brand, c.model) for c in projection.devices]

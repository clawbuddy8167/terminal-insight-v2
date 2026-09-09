"""Public metrics API."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from terminal_insight_v2.category.schema import CategorySchema, FieldDef
from terminal_insight_v2.vote.project import load_resolved

from .models import DeviceMetrics
from .parse import parse_resolved_items, price_band_cny


def field_def_map(schema: Optional[CategorySchema]) -> Dict[str, FieldDef]:
    if schema is None:
        return {}
    return {f.name: f for f in schema.fields}


def parse_resolved_devices(
    data: Mapping[str, Any],
    *,
    schema: Optional[CategorySchema] = None,
) -> List[DeviceMetrics]:
    """Parse all devices in a resolved.json object."""
    items = data.get("items") or []
    if not isinstance(items, list):
        items = []
    return parse_resolved_items(items, field_def_map(schema))


def parse_resolved_path(
    path: Path,
    *,
    schema: Optional[CategorySchema] = None,
) -> List[DeviceMetrics]:
    return parse_resolved_devices(load_resolved(path), schema=schema)


__all__ = [
    "field_def_map",
    "parse_resolved_devices",
    "parse_resolved_path",
    "price_band_cny",
]

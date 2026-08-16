"""Public entry for targeted collect lists."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Sequence

from terminal_insight_v2.models.discovery import DiscoveredDevice

from .models import DeviceTarget, ParseTargetsResult
from .parse import parse_target_text

TARGETS_NAME = "targets.json"


def parse_targets(text: str) -> ParseTargetsResult:
    """Parse a paste box into unique brand+model targets."""
    return parse_target_text(text)


def coerce_targets(raw: Any) -> List[DeviceTarget]:
    """Normalize GUI/CLI payloads into DeviceTarget rows. Invalid items dropped."""
    if not raw:
        return []
    if isinstance(raw, str):
        return list(parse_target_text(raw).targets)
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[DeviceTarget] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        brand = str(item.get("brand") or "").strip()
        model = str(item.get("model") or "").strip()
        if not brand or not model:
            continue
        key = (brand.lower(), model.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(DeviceTarget(brand=brand, model=model))
    return out


def devices_from_targets(
    targets: Sequence[DeviceTarget],
    *,
    category: str,
) -> List[DiscoveredDevice]:
    """Turn confirmed targets into collect devices. Does not search or invent models."""
    cat = (category or "phone").strip() or "phone"
    return [
        DiscoveredDevice(brand=t.brand, model=t.model, category=cat)
        for t in targets
        if t.brand.strip() and t.model.strip()
    ]


def write_targets_file(
    run_dir: Path,
    targets: Iterable[DeviceTarget],
    *,
    category: str = "",
    date_start: str = "",
    date_end: str = "",
    mode: str = "targets",
) -> Path:
    path = Path(run_dir) / TARGETS_NAME
    payload = {
        "schema_version": 1,
        "mode": mode,
        "category": category,
        "date_start": date_start,
        "date_end": date_end,
        "targets": [t.model_dump() for t in targets],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_targets_file(run_dir: Path) -> List[DeviceTarget]:
    path = Path(run_dir) / TARGETS_NAME
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        return coerce_targets(data.get("targets"))
    return coerce_targets(data)

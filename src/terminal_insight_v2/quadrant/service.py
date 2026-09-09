"""Build quadrant points from resolved metrics + optional votes."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from terminal_insight_v2.category.schema import CategorySchema
from terminal_insight_v2.metrics.api import parse_resolved_devices
from terminal_insight_v2.metrics.models import DeviceMetrics
from terminal_insight_v2.vote.project import load_resolved

from .models import (
    AxisSpec,
    OriginSpec,
    QuadrantArtifact,
    QuadrantPoint,
    SkippedDevice,
    YAxisKind,
)


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def _norm_key(brand: str, model: str) -> str:
    return f"{(brand or '').strip()}|{(model or '').strip()}".lower()


def nominations_from_votes(votes_data: Optional[Mapping[str, Any]]) -> Dict[str, List[str]]:
    """Map brand|model → voter_ids that nominated the device."""
    out: Dict[str, List[str]] = {}
    if not votes_data:
        return out
    for ballot in votes_data.get("voters") or []:
        if not isinstance(ballot, Mapping):
            continue
        voter_id = str(ballot.get("voter_id") or "").strip()
        for hs in ballot.get("hotspots") or []:
            if not isinstance(hs, Mapping):
                continue
            key = _norm_key(str(hs.get("brand") or ""), str(hs.get("model") or ""))
            if not key.strip("|"):
                continue
            bucket = out.setdefault(key, [])
            if voter_id and voter_id not in bucket:
                bucket.append(voter_id)
    return out


def _points_for_y(
    devices: Sequence[DeviceMetrics],
    nominations: Mapping[str, List[str]],
    y_kind: YAxisKind,
) -> Tuple[List[QuadrantPoint], List[SkippedDevice]]:
    points: List[QuadrantPoint] = []
    skipped: List[SkippedDevice] = []
    for dm in devices:
        price = dm.get("price")
        y = dm.get(y_kind)
        if price is None and y is None:
            skipped.append(
                SkippedDevice(
                    device_id=dm.device_id,
                    brand=dm.brand,
                    model=dm.model,
                    reason="缺价且缺纵轴指标",
                )
            )
            continue
        if price is None:
            skipped.append(
                SkippedDevice(
                    device_id=dm.device_id,
                    brand=dm.brand,
                    model=dm.model,
                    reason="缺价",
                )
            )
            continue
        if y is None:
            reason = "缺电池" if y_kind == "mah" else "缺充电功率"
            skipped.append(
                SkippedDevice(
                    device_id=dm.device_id,
                    brand=dm.brand,
                    model=dm.model,
                    reason=reason,
                )
            )
            continue
        key = _norm_key(dm.brand, dm.model)
        points.append(
            QuadrantPoint(
                device_id=dm.device_id,
                brand=dm.brand,
                model=dm.model,
                x=price,
                y=y,
                y_kind=y_kind,
                price_band=dm.price_band,
                nominated_by=list(nominations.get(key, [])),
            )
        )
    return points, skipped


def build_quadrant(
    *,
    run_id: str,
    category: str,
    resolved: Mapping[str, Any],
    votes: Optional[Mapping[str, Any]] = None,
    schema: Optional[CategorySchema] = None,
) -> QuadrantArtifact:
    devices = parse_resolved_devices(resolved, schema=schema)
    nominations = nominations_from_votes(votes)
    points_mah, skipped_mah = _points_for_y(devices, nominations, "mah")
    points_watt, _skipped_watt = _points_for_y(devices, nominations, "watt")

    # Primary skip list is for default mah axis; watt-only gaps stay on watt series.
    origin = None
    if points_mah:
        origin = OriginSpec(
            x_median=_median([p.x for p in points_mah]),
            y_median=_median([p.y for p in points_mah]),
        )

    y_label = "电池容量"
    return QuadrantArtifact(
        run_id=run_id,
        category=category,
        axes={
            "x": AxisSpec(kind="price", label="起售价", unit="元").model_dump(),
            "y_mah": AxisSpec(kind="mah", label=y_label, unit="mAh").model_dump(),
            "y_watt": AxisSpec(kind="watt", label="充电功率", unit="W").model_dump(),
        },
        origin=origin,
        points=points_mah,
        points_watt=points_watt,
        skipped=skipped_mah,
        quadrant_labels={
            "high_x_high_y": f"高价高{y_label}",
            "low_x_high_y": f"低价高{y_label}",
            "low_x_low_y": f"低价低{y_label}",
            "high_x_low_y": f"高价低{y_label}",
        },
        errors=[],
    )


def build_from_run_dir(
    run_dir: Path,
    *,
    schema: Optional[CategorySchema] = None,
) -> QuadrantArtifact:
    run_dir = Path(run_dir)
    resolved_path = run_dir / "resolved.json"
    if not resolved_path.is_file():
        raise FileNotFoundError(f"缺少 resolved.json: {resolved_path}")
    resolved = load_resolved(resolved_path)
    votes = None
    votes_path = run_dir / "votes.json"
    if votes_path.is_file():
        votes = json.loads(votes_path.read_text(encoding="utf-8"))
    run_id = str(resolved.get("run_id") or run_dir.name)
    category = str(resolved.get("category") or "")
    if schema is None and category:
        try:
            from terminal_insight_v2.category import load_category_schema

            schema = load_category_schema(category, persist=False)
        except Exception:  # noqa: BLE001
            schema = None
    return build_quadrant(
        run_id=run_id,
        category=category,
        resolved=resolved,
        votes=votes if isinstance(votes, dict) else None,
        schema=schema,
    )

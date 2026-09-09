"""Metrics research helpers — parse display_text into comparable quantities.

Not a pipeline stage. Does not write facts.db / resolved.json / Gold.
"""

from .api import parse_resolved_devices, price_band_cny
from .models import DeviceMetrics, MetricKind, ParsedValue

__all__ = [
    "DeviceMetrics",
    "MetricKind",
    "ParsedValue",
    "parse_resolved_devices",
    "price_band_cny",
]

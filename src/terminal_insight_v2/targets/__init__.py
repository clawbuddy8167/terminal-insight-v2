"""Targeted collect — parse brand/model lists; skip window discovery."""

from .api import (
    coerce_targets,
    devices_from_targets,
    load_targets_file,
    parse_targets,
    write_targets_file,
)
from .models import DeviceTarget, ParseIssue, ParseTargetsResult

__all__ = [
    "DeviceTarget",
    "ParseIssue",
    "ParseTargetsResult",
    "coerce_targets",
    "devices_from_targets",
    "load_targets_file",
    "parse_targets",
    "write_targets_file",
]

"""Resolve bundled GUI static assets (dev + PyInstaller)."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> str:
    """Absolute path to a resource under this package (e.g. ``static/index.html``)."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "terminal_insight_v2" / "gui"
    else:
        base = Path(__file__).resolve().parent
    return str(base / relative)


def index_html_path() -> str:
    return resource_path("static/index.html")

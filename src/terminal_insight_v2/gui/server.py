"""PyWebView window host.

Usage:
    python run_gui.py
    python -m terminal_insight_v2.gui
"""
from __future__ import annotations

import os
import sys

from .api import GuiApi
from .resource import index_html_path
from .stdio_utf8 import force_utf8_stdio


def _gui_backend() -> str | None:
    """Prefer Edge WebView2 on Windows; avoid ambiguous auto-pick when possible."""
    forced = (os.environ.get("PYWEBVIEW_GUI") or "").strip().lower()
    if forced:
        return forced
    if sys.platform.startswith("win"):
        return "edgechromium"
    return None


def start() -> None:
    force_utf8_stdio()
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "缺少 pywebview。请执行: pip install 'terminal-insight-v2[gui]' "
            "或 pip install pywebview"
        ) from exc

    api = GuiApi()
    webview.create_window(
        title="Terminal Insight v2",
        url=index_html_path(),
        js_api=api,
        width=1280,
        height=860,
        min_size=(960, 640),
    )
    gui = _gui_backend()
    if gui:
        webview.start(debug=False, gui=gui)
    else:
        webview.start(debug=False)


if __name__ == "__main__":
    start()

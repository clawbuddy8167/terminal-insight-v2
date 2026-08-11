"""PyWebView window host.

Usage:
    python run_gui.py
    python -m terminal_insight_v2.gui
"""
from __future__ import annotations

from .api import GuiApi
from .resource import index_html_path


def start() -> None:
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
    webview.start(debug=False)


if __name__ == "__main__":
    start()

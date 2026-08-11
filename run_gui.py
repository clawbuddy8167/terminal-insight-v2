#!/usr/bin/env python3
"""terminal-insight-v2 GUI entry point.

Usage:
    python run_gui.py
    python -m terminal_insight_v2.gui
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from terminal_insight_v2.gui.server import start  # noqa: E402

if __name__ == "__main__":
    start()

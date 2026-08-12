"""force_utf8_stdio normalizes Windows charmap / None streams."""
from __future__ import annotations

import io

from terminal_insight_v2.gui.stdio_utf8 import force_utf8_stdio


def test_force_utf8_stdio_reconfigures_existing_streams(monkeypatch):
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)

    force_utf8_stdio()

    import sys

    sys.stdout.write("到货")
    sys.stdout.flush()
    assert (sys.stdout.encoding or "").lower().replace("-", "") == "utf8"
    assert (sys.stderr.encoding or "").lower().replace("-", "") == "utf8"


def test_force_utf8_stdio_replaces_none_streams(monkeypatch):
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)

    force_utf8_stdio()

    import sys

    assert sys.stdout is not None
    assert sys.stderr is not None
    sys.stdout.write("中文")
    sys.stdout.flush()

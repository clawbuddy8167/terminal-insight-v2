"""Force UTF-8 stdio early (Windows charmap / windowed exe)."""
from __future__ import annotations

import io
import os
import sys
from typing import TextIO, Optional


def _reconfigure(stream: Optional[TextIO]) -> Optional[TextIO]:
    if stream is None:
        return None
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
            return stream
        except Exception:
            pass
    encoding = getattr(stream, "encoding", None) or ""
    if encoding.lower().replace("-", "") == "utf8":
        return stream
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        try:
            return io.TextIOWrapper(
                buffer,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
                write_through=True,
            )
        except Exception:
            return stream
    return stream


def _null_utf8() -> TextIO:
    return io.TextIOWrapper(
        open(os.devnull, "wb"),
        encoding="utf-8",
        errors="replace",
        line_buffering=True,
        write_through=True,
    )


def force_utf8_stdio() -> None:
    """Make stdout/stderr UTF-8 so Rich can log Chinese on Windows.

    Safe to call multiple times. Windowed (console=False) exes often have
    ``None`` or ``charmap`` streams; both are normalized here.
    """
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    out = _reconfigure(getattr(sys, "stdout", None))
    err = _reconfigure(getattr(sys, "stderr", None))
    if out is None:
        out = _null_utf8()
    if err is None:
        err = _null_utf8()
    sys.stdout = out
    sys.stderr = err

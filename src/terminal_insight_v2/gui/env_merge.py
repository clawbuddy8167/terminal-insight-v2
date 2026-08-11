"""Merge KEY=value updates into a .env file without wiping unrelated keys."""
from __future__ import annotations

from pathlib import Path
from typing import Dict


def merge_env_file(path: Path, updates: Dict[str, str]) -> None:
    """Replace or append keys in ``updates``; preserve comments and blank lines."""
    pending = {str(k): str(v) for k, v in updates.items()}
    out_lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                out_lines.append(line)
                continue
            key, _, _rest = line.partition("=")
            key = key.strip()
            if key in pending:
                out_lines.append(f"{key}={pending.pop(key)}")
            else:
                out_lines.append(line)
    for key, val in pending.items():
        out_lines.append(f"{key}={val}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(out_lines) + ("\n" if out_lines else ""),
        encoding="utf-8",
    )


__all__ = ["merge_env_file"]

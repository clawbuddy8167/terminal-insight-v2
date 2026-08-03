"""Discover and load compiled category schemas."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from terminal_insight_v2.config import settings

from .compiler import CategoryCompileError, compile_template
from .schema import CategorySchema


def load_category_schema(
    category: str,
    *,
    template_dir: Optional[Path] = None,
    persist: bool = True,
) -> CategorySchema:
    """Compile ``{template_dir}/{category}.xlsx`` (required)."""
    base = Path(template_dir) if template_dir else settings.templates_path()
    path = base / f"{category}.xlsx"
    if not path.is_file():
        raise CategoryCompileError(
            [f"未找到品类模板: {path}（请放入 category_templates/{category}.xlsx）"],
            path=str(path),
        )
    return compile_template(path, persist=persist)


def list_category_ids(*, template_dir: Optional[Path] = None) -> list[str]:
    base = Path(template_dir) if template_dir else settings.templates_path()
    if not base.is_dir():
        return []
    return sorted(p.stem for p in base.glob("*.xlsx") if not p.name.startswith("_"))


__all__ = ["list_category_ids", "load_category_schema"]

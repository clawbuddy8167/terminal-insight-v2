"""Frozen vs dev project root resolution."""
from __future__ import annotations

from pathlib import Path

from terminal_insight_v2.config import Settings, resolve_project_root


def test_resolve_project_root_dev():
    root = resolve_project_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "terminal_insight_v2").is_dir()


def test_templates_path_prefers_project_dir(tmp_path: Path, monkeypatch):
    tpl = tmp_path / "category_templates"
    tpl.mkdir()
    (tpl / "phone.xlsx").write_bytes(b"x")
    monkeypatch.setattr("terminal_insight_v2.config.PROJECT_ROOT", tmp_path)
    s = Settings()
    assert s.templates_path() == tpl

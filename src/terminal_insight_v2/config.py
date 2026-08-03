"""Runtime settings (env / .env)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    category: str = "phone"
    date_start: str = ""
    date_end: str = ""
    data_root: str = "data"
    template_dir: str = "category_templates"
    extract_target_sources: int = 10
    backfill_max_rounds: int = 3
    collect_max_workers: int = 4
    doubao_max_qps: float = 4.0
    report_mode: Literal["research", "gold"] = "research"

    doubao_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    openai_timeout: float = 120.0

    memory_db_path: str = ""  # empty → data/memory/facts.db

    def data_path(self) -> Path:
        p = Path(self.data_root)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def memory_root(self) -> Path:
        return self.data_path() / "memory"

    def runs_root(self) -> Path:
        return self.data_path() / "runs"

    def templates_path(self) -> Path:
        p = Path(self.template_dir)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def db_path(self) -> Path:
        raw = (self.memory_db_path or "").strip()
        if raw:
            p = Path(raw)
            return p if p.is_absolute() else PROJECT_ROOT / p
        return self.memory_root() / "facts.db"


settings = Settings()

STAGES = ("collect", "extract", "backfill", "verify", "excel", "vote")

__all__ = ["PROJECT_ROOT", "STAGES", "Settings", "settings"]

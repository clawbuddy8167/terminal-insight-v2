"""Runtime settings (env / .env)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


def resolve_project_root() -> Path:
    """Repo root in dev; directory containing the frozen exe when packaged."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = resolve_project_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Prefer project .env over ambient shell env (Cursor often injects stale keys).
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    category: str = "phone"
    date_start: str = ""
    date_end: str = ""
    data_root: str = "data"
    template_dir: str = "category_templates"
    extract_target_sources: int = 10
    backfill_max_rounds: int = 3
    backfill_urls_per_device: int = 4
    backfill_queries_per_device: int = 3
    collect_max_workers: int = 4
    extract_max_workers: int = 4
    collect_fetch_workers: int = 4
    collect_max_urls_per_device: int = 8
    discover_max_workers: int = 4
    doubao_max_qps: float = 4.0
    report_mode: Literal["research", "gold"] = "research"

    doubao_api_key: str = ""
    doubao_max_results: int = 10
    doubao_timeout: float = 60.0
    doubao_max_retries: int = 3
    doubao_content_formats: str = "text"
    discovery_backend: str = "auto"  # auto|doubao|tavily
    tavily_api_key: str = ""
    tavily_max_results: int = 8
    tavily_search_depth: str = "advanced"
    tavily_timeout: float = 60.0
    openai_api_key: str = ""
    openai_base_url: str = "https://api.deepseek.com/v1"
    openai_model: str = "deepseek-v4-pro"
    openai_timeout: float = 120.0
    http_timeout: float = 30.0
    jina_reader_enabled: bool = True
    fetch_min_body_len: int = 300
    hypotheses_path: str = ""  # optional year catalog; empty → data/hypotheses/{category}*.json

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
        if p.is_absolute():
            return p
        cand = PROJECT_ROOT / p
        if cand.is_dir():
            return cand
        # Frozen onedir: bundled templates live under _MEIPASS
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            bundled = Path(sys._MEIPASS) / p
            if bundled.is_dir():
                return bundled
        return cand

    def db_path(self) -> Path:
        raw = (self.memory_db_path or "").strip()
        if raw:
            p = Path(raw)
            return p if p.is_absolute() else PROJECT_ROOT / p
        return self.memory_root() / "facts.db"


settings = Settings()

STAGES = ("collect", "extract", "backfill", "verify", "excel", "vote")

__all__ = [
    "PROJECT_ROOT",
    "STAGES",
    "Settings",
    "resolve_project_root",
    "settings",
]

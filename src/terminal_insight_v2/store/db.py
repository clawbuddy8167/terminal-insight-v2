"""SQLite connection, migrations, and path helpers."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from terminal_insight_v2.config import settings

_SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
_lock = threading.RLock()

_SCHEMA_MIGRATIONS = (
    (1, "v001.sql", "initial evidence-first facts schema"),
)
_TARGET_SCHEMA_VERSION = _SCHEMA_MIGRATIONS[-1][0]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def memory_root(*, root: Optional[Path] = None) -> Path:
    base = root or settings.memory_root()
    base.mkdir(parents=True, exist_ok=True)
    return base


def ensure_memory_dirs(*, root: Optional[Path] = None) -> Path:
    base = memory_root(root=root)
    for name in ("blobs", "compiled", "llm-wiki/raw", "llm-wiki/canonical", "llm-wiki/gold",
                 "llm-wiki/indexes/research", "llm-wiki/indexes/report", "exports", "imports"):
        (base / name).mkdir(parents=True, exist_ok=True)
    settings.runs_root().mkdir(parents=True, exist_ok=True)
    return base


def db_path(*, root: Optional[Path] = None) -> Path:
    if root is not None:
        return memory_root(root=root) / "facts.db"
    return settings.db_path()


def blobs_dir(*, root: Optional[Path] = None) -> Path:
    d = memory_root(root=root) / "blobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _apply_schema(conn: sqlite3.Connection) -> None:
    row = conn.execute("PRAGMA user_version").fetchone()
    version = int(row[0]) if row else 0
    if version >= _TARGET_SCHEMA_VERSION:
        return
    for target, filename, description in _SCHEMA_MIGRATIONS:
        if version >= target:
            continue
        ddl = (_SCHEMA_DIR / filename).read_text(encoding="utf-8")
        conn.executescript(ddl)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at, description) "
            "VALUES (?, ?, ?)",
            (target, utc_now(), description),
        )
        conn.execute(f"PRAGMA user_version = {int(target)}")
        conn.commit()
        version = target


def connect(*, readonly: bool = False, root: Optional[Path] = None) -> sqlite3.Connection:
    ensure_memory_dirs(root=root)
    path = db_path(root=root)
    if readonly and not path.exists():
        with _lock:
            bootstrap = sqlite3.connect(str(path))
            try:
                bootstrap.execute("PRAGMA journal_mode=WAL")
                bootstrap.execute("PRAGMA foreign_keys=ON")
                _apply_schema(bootstrap)
            finally:
                bootstrap.close()
    uri = f"file:{path}?mode=ro" if readonly else str(path)
    conn = sqlite3.connect(uri, uri=readonly, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if not readonly:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if not readonly:
        with _lock:
            _apply_schema(conn)
    return conn


@contextmanager
def connection(*, readonly: bool = False, root: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    conn = connect(readonly=readonly, root=root)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(*, root: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    with connection(readonly=False, root=root) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def schema_version(*, root: Optional[Path] = None) -> int:
    with connection(readonly=True, root=root) as conn:
        row = conn.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0


__all__ = [
    "blobs_dir",
    "connect",
    "connection",
    "db_path",
    "ensure_memory_dirs",
    "memory_root",
    "schema_version",
    "transaction",
    "utc_now",
]

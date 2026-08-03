from pathlib import Path

from terminal_insight_v2.store.blobs import read_blob, write_blob
from terminal_insight_v2.store.db import connection, schema_version
from terminal_insight_v2.store.ledger import (
    begin_run,
    finish_run,
    finish_stage,
    get_run,
    list_stage_runs,
    start_stage,
)


def _patch_settings(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.store.db as db
    import terminal_insight_v2.store.ledger as ledger

    s = Settings()
    monkeypatch.setattr(db, "settings", s)
    monkeypatch.setattr(ledger, "settings", s)
    return s


def test_schema_migrates(tmp_path: Path, monkeypatch):
    s = _patch_settings(monkeypatch, tmp_path)
    root = s.memory_root()
    assert schema_version(root=root) == 1
    with connection(root=root) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "field_assertions" in tables
    assert "pipeline_runs" in tables
    assert "snapshots" in tables


def test_blob_roundtrip(tmp_path: Path, monkeypatch):
    s = _patch_settings(monkeypatch, tmp_path)
    root = s.memory_root()
    bid, sha, size, rel = write_blob(
        "<html>hello</html>",
        content_type="text/html",
        root=root,
    )
    assert bid.startswith("blob:")
    assert size > 0
    assert rel.endswith(".html")
    body = read_blob(sha, content_type="text/html", root=root)
    assert body == "<html>hello</html>"
    bid2, sha2, _, _ = write_blob(
        "<html>hello</html>",
        content_type="text/html",
        root=root,
    )
    assert sha2 == sha and bid2 == bid


def test_run_ledger(tmp_path: Path, monkeypatch):
    s = _patch_settings(monkeypatch, tmp_path)
    root = s.memory_root()
    meta = begin_run(
        category="phone",
        schema_fingerprint="fp-test",
        date_start="2026-07-01",
        date_end="2026-07-31",
        root=root,
    )
    run_id = meta["run_id"]
    assert (s.data_path() / meta["rel_path"] / "run.json").exists()

    st = start_stage(run_id, "collect", input_revision="r1", root=root)
    finish_stage(st["stage_run_id"], status="skipped", output_revision="o1", root=root)
    finish_run(run_id, status="ok", root=root)

    got = get_run(run_id, root=root)
    assert got is not None
    assert got["status"] == "ok"
    assert got["schema_fingerprint"] == "fp-test"
    stages = list_stage_runs(run_id, root=root)
    assert len(stages) == 1
    assert stages[0]["stage"] == "collect"
    assert stages[0]["status"] == "skipped"

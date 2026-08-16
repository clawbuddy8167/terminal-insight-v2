"""GUI api + env merge (no PyWebView window)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from terminal_insight_v2.gui.api import GuiApi, stages_from
from terminal_insight_v2.gui.env_merge import merge_env_file


def test_gui_parse_and_reject_empty_targets():
    from terminal_insight_v2.gui.api import GuiApi

    api = GuiApi()
    parsed = api.parse_targets("华为 | Mate X7")
    assert parsed["targets"][0]["model"] == "Mate X7"
    denied = api.run_pipeline(["collect"], {"collect_mode": "targets", "targets": []})
    assert not denied["ok"]


def test_stages_from_order():
    assert stages_from("verify") == ["verify", "excel", "vote"]


def test_merge_env_file_preserves_other_keys(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("FOO=1\n# comment\nBAR=keep\n", encoding="utf-8")
    merge_env_file(env, {"FOO": "2", "BAZ": "3"})
    text = env.read_text(encoding="utf-8")
    assert "FOO=2" in text
    assert "BAR=keep" in text
    assert "BAZ=3" in text
    assert "# comment" in text


def test_gui_list_runs_filesystem_fallback(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    runs = data / "runs" / "phone_20260101-20260131_20260101120000"
    runs.mkdir(parents=True)
    meta = {
        "run_id": "phone_20260101-20260131_20260101120000",
        "category": "phone",
        "date_start": "2026-01-01",
        "date_end": "2026-01-31",
        "status": "ok",
        "rel_path": "runs/phone_20260101-20260131_20260101120000",
        "created_at": "2026-01-01T12:00:00+00:00",
    }
    (runs / "run.json").write_text(json.dumps(meta), encoding="utf-8")
    (runs / "steps.json").write_text("[]", encoding="utf-8")
    (runs / "coverage_report.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "device_id": "phone:a:b",
                        "brand": "A",
                        "model": "B",
                        "filled": 1,
                        "total": 2,
                        "missing_fields": ["x"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("DATA_ROOT", str(data))
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.gui.api as gui_api
    import terminal_insight_v2.store.db as db
    import terminal_insight_v2.store.ledger as ledger

    s = Settings()
    monkeypatch.setattr(gui_api, "settings", s)
    monkeypatch.setattr(db, "settings", s)
    monkeypatch.setattr(ledger, "settings", s)

    # Empty DB → filesystem fallback
    from terminal_insight_v2.store import ensure_memory_dirs

    ensure_memory_dirs(root=s.memory_root())

    api = GuiApi()
    listed = api.list_runs(limit=10, category="phone")
    assert listed["ok"]
    assert any(r["run_id"] == meta["run_id"] for r in listed["runs"])

    sel = api.select_run(meta["run_id"])
    assert sel["ok"]
    cov = api.get_coverage()
    assert cov["ok"]
    assert len(cov["items"]) == 1
    prog = api.get_progress()
    assert prog["run_id"] == meta["run_id"]
    assert prog["artifacts"]["run_dir"]


def test_gui_run_pipeline_vote_without_resolved(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.gui.api as gui_api
    import terminal_insight_v2.orchestrator as orch
    import terminal_insight_v2.store.db as db
    import terminal_insight_v2.store.ledger as ledger
    import terminal_insight_v2.vote.api as vote_api

    s = Settings(_env_file=None, data_root=str(tmp_path / "data"), openai_api_key="")
    monkeypatch.setattr(gui_api, "settings", s)
    monkeypatch.setattr(orch, "settings", s)
    monkeypatch.setattr(db, "settings", s)
    monkeypatch.setattr(ledger, "settings", s)
    monkeypatch.setattr(vote_api, "settings", s)

    api = GuiApi()
    res = api.run_pipeline(["vote"], {"category": "phone", "date_start": "2026-07-01", "date_end": "2026-07-31"})
    assert res["ok"]
    deadline = time.time() + 10
    while api._running and time.time() < deadline:
        time.sleep(0.05)
    prog = api.get_progress()
    assert not prog["running"]
    assert prog["run_id"]
    assert prog["error"]

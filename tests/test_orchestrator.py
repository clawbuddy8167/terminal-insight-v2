from pathlib import Path

from terminal_insight_v2.orchestrator import normalize_stages, run_pipeline


def test_normalize_stages_order():
    assert normalize_stages(["vote", "collect"]) == ["collect", "vote"]
    assert normalize_stages(["all"]) == [
        "collect",
        "extract",
        "backfill",
        "verify",
        "excel",
        "vote",
    ]


def test_run_pipeline_vote_requires_resolved(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    from terminal_insight_v2.config import Settings
    import terminal_insight_v2.orchestrator as orch
    import terminal_insight_v2.store.db as db
    import terminal_insight_v2.store.ledger as ledger
    import terminal_insight_v2.vote.api as vote_api

    s = Settings(_env_file=None, data_root=str(tmp_path / "data"), openai_api_key="test-key")
    monkeypatch.setattr(db, "settings", s)
    monkeypatch.setattr(ledger, "settings", s)
    monkeypatch.setattr(orch, "settings", s)
    monkeypatch.setattr(vote_api, "settings", s)

    result = run_pipeline(
        category="phone",
        stages=["vote"],
        date_start="2026-07-01",
        date_end="2026-07-31",
        schema_fingerprint="fp",
        root=s.memory_root(),
    )
    assert result["status"] == "failed"
    assert (Path(result["run_dir"]) / "run.json").exists()

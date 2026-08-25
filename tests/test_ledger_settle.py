"""Cross-run ledger settle: deterministic verdicts."""
from __future__ import annotations

import json
from pathlib import Path

from terminal_insight_v2.hypothesis.loader import load_hypothesis_set
from terminal_insight_v2.hypothesis.settle import settle_runs


def _votes(
    *,
    run_id: str,
    mappings: list[dict],
    oem: bool = False,
) -> dict:
    reviews = []
    if oem:
        reviews.append(
            {
                "audience_id": "OEM",
                "name": "终端企业",
                "assessments": [
                    {
                        "hotspot_index": 1,
                        "title": "影像旗舰",
                        "brand": "OPPO",
                        "model": "X9",
                        "relevance": 3,
                        "action_implication": "跟进长焦",
                        "why_it_matters": "差异化",
                        "caveat": "",
                    },
                    {
                        "hotspot_index": 2,
                        "title": "低相关",
                        "relevance": 1,
                        "action_implication": "忽略",
                    },
                ],
            }
        )
    return {
        "schema_version": 4,
        "run_id": run_id,
        "category": "phone",
        "voters": [],
        "clusters": [],
        "audience_reviews": reviews,
        "hypothesis_reviews": mappings,
        "errors": [],
    }


def _write_run(root: Path, run_id: str, payload: dict) -> None:
    d = root / run_id
    d.mkdir(parents=True)
    (d / "votes.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_settle_confirmed_and_falsified(tmp_path: Path):
    catalog = tmp_path / "hypo.json"
    catalog.write_text(
        json.dumps(
            {
                "year": 2026,
                "category": "phone",
                "source": "test",
                "hypotheses": [
                    {"id": "H1", "statement": "L3 下探"},
                    {"id": "H2", "statement": "跨应用日用"},
                    {"id": "H3", "statement": "证据不足题"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runs = tmp_path / "runs"
    _write_run(
        runs,
        "q1",
        _votes(
            run_id="q1",
            mappings=[
                {
                    "hypothesis_id": "H1",
                    "hotspot_index": 1,
                    "title": "中端智能体",
                    "stance": "support",
                    "voter_id": "CCC",
                },
                {
                    "hypothesis_id": "H2",
                    "hotspot_index": 2,
                    "title": "封闭演示",
                    "stance": "weaken",
                    "voter_id": "AAA",
                },
            ],
            oem=True,
        ),
    )
    _write_run(
        runs,
        "q2",
        _votes(
            run_id="q2",
            mappings=[
                {
                    "hypothesis_id": "H1",
                    "hotspot_index": 1,
                    "title": "3000元 L3",
                    "stance": "support",
                    "voter_id": "CCC",
                },
                {
                    "hypothesis_id": "H2",
                    "hotspot_index": 2,
                    "title": "仍无第三方",
                    "stance": "weaken",
                    "voter_id": "FFF",
                },
            ],
        ),
    )
    _write_run(
        runs,
        "q3",
        _votes(run_id="q3", mappings=[]),
    )
    # q4 missing entirely

    hypo = load_hypothesis_set(catalog)
    art = settle_runs(hypo, ["q1", "q2", "q3", "q4"], runs_root=runs)
    by_id = {s.hypothesis_id: s for s in art.settlements}
    assert by_id["H1"].verdict == "confirmed"
    assert by_id["H2"].verdict == "falsified"
    assert by_id["H3"].verdict == "insufficient"
    assert any("q4" in e for e in art.errors)
    assert len(art.oem_slice) == 1
    assert art.oem_slice[0].action_implication == "跟进长焦"


def test_settle_partial_single_quarter(tmp_path: Path):
    catalog = tmp_path / "hypo.json"
    catalog.write_text(
        json.dumps(
            {
                "year": 2026,
                "category": "phone",
                "hypotheses": [{"id": "H1", "statement": "only one"}],
            }
        ),
        encoding="utf-8",
    )
    runs = tmp_path / "runs"
    _write_run(
        runs,
        "q1",
        _votes(
            run_id="q1",
            mappings=[
                {
                    "hypothesis_id": "H1",
                    "hotspot_index": 1,
                    "title": "信号",
                    "stance": "support",
                }
            ],
        ),
    )
    _write_run(runs, "q2", _votes(run_id="q2", mappings=[]))
    art = settle_runs(load_hypothesis_set(catalog), ["q1", "q2"], runs_root=runs)
    assert art.settlements[0].verdict == "partial"

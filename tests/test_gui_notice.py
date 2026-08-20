"""GUI completion banner must not look like a crash for partial runs."""
from __future__ import annotations

from terminal_insight_v2.gui.notice import annotate_steps, summarize_run_notice


PARTIAL_STEPS = [
    {
        "stage": "collect",
        "status": "partial",
        "metrics": {"devices": 3, "sources_ok": 20, "sources_failed": 4},
    },
    {"stage": "extract", "status": "ok", "metrics": {"assertions": 81}},
    {"stage": "backfill", "status": "ok", "metrics": {"rounds": 1, "missing_after": 5}},
    {"stage": "verify", "status": "ok", "metrics": {"resolutions": 39}},
    {"stage": "excel", "status": "ok", "metrics": {"rows": 3}},
    {
        "stage": "vote",
        "status": "partial",
        "metrics": {"voters": 6, "voters_with_hotspots": 5, "hotspots": 13},
    },
]


def test_partial_is_warn_not_error_and_says_excel_ok():
    notice = summarize_run_notice(
        PARTIAL_STEPS, run_status="partial", has_excel=True
    )
    assert notice is not None
    assert notice["level"] == "warn"
    assert notice["title"] == "跑完了，有些地方没抓全"
    assert "partial" not in notice["text"]
    assert "流水线结束" not in notice["text"]
    assert "4 个网页" in notice["text"]
    assert "1 套" in notice["text"]
    assert "Excel 可以打开" in notice["text"]


def test_stale_pipeline_ended_partial_is_folded():
    notice = summarize_run_notice(
        PARTIAL_STEPS,
        error="流水线结束: partial",
        has_excel=True,
    )
    assert notice is not None
    assert notice["level"] == "warn"
    assert "流水线结束" not in notice["text"]
    assert "跑完了" in notice["title"]


def test_ok_run_is_calm():
    steps = [
        {"stage": "collect", "status": "ok", "metrics": {"devices": 3, "sources_failed": 0}},
        {"stage": "excel", "status": "ok", "metrics": {"rows": 3}},
    ]
    notice = summarize_run_notice(steps, run_status="ok", has_excel=True)
    assert notice["level"] == "ok"
    assert notice["title"] == "跑完了"
    assert notice["text"] == "跑完了，可以打开 Excel"


def test_exception_stays_error():
    notice = summarize_run_notice([], error="RuntimeError: boom", has_excel=False)
    assert notice["level"] == "error"
    assert notice["title"] == "出错了"
    assert notice["text"] == "RuntimeError: boom"


def test_running_hides_banner():
    assert summarize_run_notice(PARTIAL_STEPS, running=True, has_excel=True) is None


def test_annotate_steps_uses_chinese():
    rows = annotate_steps(PARTIAL_STEPS)
    collect = rows[0]
    assert collect["label_zh"] == "采集"
    assert collect["status_zh"] == "有缺口"
    assert "4 页失败" in collect["summary_zh"]


def test_vote_audience_gap_phrase():
    steps = [
        {
            "stage": "vote",
            "status": "partial",
            "metrics": {
                "voters": 6,
                "voters_with_hotspots": 6,
                "audiences": 4,
                "audiences_reviewed": 3,
            },
        }
    ]
    notice = summarize_run_notice(steps, run_status="partial", has_excel=True)
    assert notice is not None
    assert "1 类受众" in notice["text"]
    rows = annotate_steps(steps)
    assert "6/6 套有热点" in rows[0]["summary_zh"]
    assert "3/4 类受众" in rows[0]["summary_zh"]

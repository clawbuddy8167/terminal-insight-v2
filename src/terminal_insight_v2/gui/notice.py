"""User-facing run outcome copy for the GUI header and log.

Pipeline status ``partial`` means finished-with-gaps, not a crash.
This module turns steps.json into Chinese that says what is missing
and that Excel is still usable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

STAGE_LABELS = {
    "collect": "采集",
    "extract": "抽取",
    "backfill": "补链",
    "verify": "校验",
    "excel": "Excel",
    "vote": "Vote",
}

STATUS_ZH = {
    "ok": "完成",
    "partial": "有缺口",
    "failed": "失败",
    "skipped": "跳过",
    "cancelled": "已取消",
}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value is False:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _metrics(step: Dict[str, Any]) -> Dict[str, Any]:
    raw = step.get("metrics")
    return raw if isinstance(raw, dict) else {}


def _gap_phrase(step: Dict[str, Any]) -> Optional[str]:
    stage = str(step.get("stage") or "")
    status = str(step.get("status") or "ok")
    if status in ("ok", "skipped"):
        return None
    m = _metrics(step)
    label = STAGE_LABELS.get(stage, stage)

    if stage == "collect":
        devices = _as_int(m.get("devices"))
        failed = _as_int(m.get("sources_failed"))
        if devices <= 0:
            return "没有发现机型，可改日期或改用定向机型"
        if failed > 0:
            return f"采集有 {failed} 个网页没抓到（可点「信源」核对）"
        return "采集未抓全"

    if stage == "extract":
        if _as_int(m.get("assertions")) <= 0 and _as_int(m.get("new_assertions")) <= 0:
            return "抽取没有写出字段"
        return "抽取不完整"

    if stage == "backfill":
        missing = _as_int(m.get("missing_after"))
        if missing > 0:
            return f"补链后仍缺 {missing} 个字段"
        return "补链未补全"

    if stage == "verify":
        return "校验没有形成可用决议" if _as_int(m.get("resolutions")) <= 0 else "校验未全部通过"

    if stage == "excel":
        return "Excel 没有写出机型" if _as_int(m.get("rows")) <= 0 else "Excel 未写全"

    if stage == "vote":
        voters = _as_int(m.get("voters"))
        filled = _as_int(m.get("voters_with_hotspots"))
        missing_voters = max(0, voters - filled) if voters else 0
        audiences = _as_int(m.get("audiences"))
        reviewed = _as_int(m.get("audiences_reviewed"))
        if filled <= 0:
            return "Vote 没有给出热点"
        if missing_voters:
            return f"Vote 有 {missing_voters} 套参考系没给出热点"
        if audiences and reviewed < audiences:
            return f"Vote 有 {audiences - reviewed} 类受众未完成审阅"
        return "Vote 不完整"

    if status == "failed":
        return f"{label}失败"
    return f"{label}未全部完成"


def _step_summary(step: Dict[str, Any]) -> str:
    stage = str(step.get("stage") or "")
    m = _metrics(step)
    if stage == "collect":
        parts = []
        if m.get("devices") is not None:
            parts.append(f"{_as_int(m.get('devices'))} 机")
        ok = m.get("sources_ok")
        fail = m.get("sources_failed")
        if ok is not None or fail is not None:
            parts.append(f"{_as_int(ok)} 页成功")
            if _as_int(fail) > 0:
                parts.append(f"{_as_int(fail)} 页失败")
        return "，".join(parts)
    if stage == "extract":
        n = m.get("assertions")
        return f"{_as_int(n)} 条字段" if n is not None else ""
    if stage == "backfill":
        parts = []
        if m.get("rounds") is not None:
            parts.append(f"{_as_int(m.get('rounds'))} 轮")
        if _as_int(m.get("missing_after")):
            parts.append(f"仍缺 {_as_int(m.get('missing_after'))} 字段")
        return "，".join(parts)
    if stage == "verify":
        parts = []
        if m.get("resolutions") is not None:
            parts.append(f"{_as_int(m.get('resolutions'))} 条决议")
        if _as_int(m.get("missing_fields")):
            parts.append(f"缺 {_as_int(m.get('missing_fields'))} 字段")
        return "，".join(parts)
    if stage == "excel":
        return f"{_as_int(m.get('rows'))} 行" if m.get("rows") is not None else ""
    if stage == "vote":
        filled = _as_int(m.get("voters_with_hotspots"))
        voters = _as_int(m.get("voters"))
        parts = []
        if voters:
            parts.append(f"{filled}/{voters} 套有热点")
        audiences = m.get("audiences")
        if audiences is not None:
            parts.append(
                f"{_as_int(m.get('audiences_reviewed'))}/{_as_int(audiences)} 类受众"
            )
        return "，".join(parts)
    return ""


def annotate_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Copy steps and attach Chinese label / status / summary for the GUI log."""
    out: List[Dict[str, Any]] = []
    for step in steps:
        row = dict(step)
        stage = str(step.get("stage") or "")
        status = str(step.get("status") or "ok")
        row["label_zh"] = STAGE_LABELS.get(stage, stage)
        row["status_zh"] = STATUS_ZH.get(status, status)
        row["summary_zh"] = _step_summary(step)
        out.append(row)
    return out


def _split_stale_status_error(error: Optional[str]) -> Tuple[Optional[str], str]:
    """Old GUI dumped ``流水线结束: partial`` into the error slot; fold it back."""
    raw = (error or "").strip()
    if not raw:
        return None, ""
    prefix = "流水线结束:"
    if raw.startswith(prefix):
        return None, raw[len(prefix) :].strip().lower()
    return raw, ""


def summarize_run_notice(
    steps: List[Dict[str, Any]],
    *,
    run_status: str = "",
    error: Optional[str] = None,
    running: bool = False,
    has_excel: bool = False,
) -> Optional[Dict[str, str]]:
    """Outcome banner. ``level`` is ok / warn / error. None while running."""
    if running:
        return None
    error, folded = _split_stale_status_error(error)
    if error:
        return {
            "level": "error",
            "title": "出错了",
            "detail": error,
            "text": error,
        }

    status = (run_status or folded or "").strip().lower()
    if not steps and not status:
        return None

    failed = status == "failed" or any(str(s.get("status")) == "failed" for s in steps)
    cancelled = status == "cancelled"
    gaps = [p for s in steps if (p := _gap_phrase(s))]

    usable = "Excel 可以打开。" if has_excel else "已完成的结果还在。"

    if failed:
        detail = "；".join(gaps) if gaps else "请查看阶段卡片或日志"
        title = "没跑完"
        return {
            "level": "error",
            "title": title,
            "detail": detail,
            "text": f"{title}：{detail}",
        }
    if cancelled:
        title = "已取消"
        return {
            "level": "warn",
            "title": title,
            "detail": usable,
            "text": f"{title}。{usable}",
        }
    if gaps or status == "partial":
        detail = "；".join(gaps) if gaps else "部分网页或字段没抓全"
        title = "跑完了，有些地方没抓全"
        extra = f"{detail}。{usable}"
        return {
            "level": "warn",
            "title": title,
            "detail": extra,
            "text": f"{title}。{extra}",
        }
    if steps or status == "ok":
        title = "跑完了"
        detail = "可以打开右上角 Excel" if has_excel else ""
        return {
            "level": "ok",
            "title": title,
            "detail": detail,
            "text": "跑完了，可以打开 Excel" if has_excel else title,
        }
    return None


__all__ = [
    "STAGE_LABELS",
    "STATUS_ZH",
    "annotate_steps",
    "summarize_run_notice",
]

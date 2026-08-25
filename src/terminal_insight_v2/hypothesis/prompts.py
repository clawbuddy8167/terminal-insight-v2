"""Prompts for mapping numbered hotspots onto falsifiable hypotheses."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from .models import Hypothesis, HypothesisSet

_NOTE_CHARS = 200
_STATEMENT_CHARS = 120


def mapping_system(category: str) -> str:
    label = category or "终端"
    return f"""你是{label}季度热点与年度假说的对照员。
你不提名新热点，只判断已有热点提名是否支持或削弱给定假说。

规则：
1. 只使用输入清单中的热点编号与假说 ID；不要新增热点、机型、销量、政策文件或外部数字。
2. hotspot_index 使用清单中的 1-based 编号。
3. stance 只能是 support / weaken / unrelated。
4. 每个 (hypothesis_id, hotspot_index) 最多一条；无关可省略或标 unrelated。
5. note 只能复述或压缩已有提名说明，禁止补写事实；可留空。
6. 只输出 JSON：{{"mappings":[{{"hypothesis_id":"H1","hotspot_index":1,"stance":"support","note":"..."}}]}}
"""


def mapping_user(
    hypo_set: HypothesisSet,
    hotspot_lines: Sequence[str],
) -> str:
    hypo_block = "\n".join(_format_hypothesis(h) for h in hypo_set.hypotheses)
    listing = "\n".join(hotspot_lines) if hotspot_lines else "（无热点）"
    return f"""假说目录（year={hypo_set.year} category={hypo_set.category} source={hypo_set.source}）
{hypo_block or "（无假说）"}

### 编号热点（唯一评估对象） ###
{listing}

请输出对照 JSON。"""


def _format_hypothesis(h: Hypothesis) -> str:
    statement = (h.statement or "").strip()[:_STATEMENT_CHARS]
    falsify = (h.falsify_when or "").strip()[:_NOTE_CHARS]
    frames = "、".join(h.frames) if h.frames else "—"
    leads = "；".join(h.lead_indicators[:4]) if h.lead_indicators else "—"
    return (
        f"- {h.id}: {statement}\n"
        f"  领先指标: {leads}\n"
        f"  证伪条件: {falsify or '—'}\n"
        f"  相关参考系: {frames}"
    )


def numbered_hotspot_lines(
    entries: Sequence[Tuple[str, dict]],
) -> List[str]:
    """Format (voter_id, hotspot_dict) for prompts without importing vote internals.

    Expected hotspot_dict keys: title, brand, model, rationale_text, frame_name.
    """
    lines: List[str] = []
    for i, (voter_id, hs) in enumerate(entries, start=1):
        title = str(hs.get("title") or "").strip() or "（无标题）"
        brand = str(hs.get("brand") or "").strip()
        model = str(hs.get("model") or "").strip()
        device = f"{brand} {model}".strip() or "（未绑定机型）"
        frame = str(hs.get("frame_name") or "").strip()
        rationale = str(hs.get("rationale_text") or "").strip()[:160]
        frame_bit = f"·{frame}" if frame else ""
        extra = f"\n   说明：{rationale}" if rationale else ""
        lines.append(f"{i}. [{voter_id}{frame_bit}] {title} — {device}{extra}")
    return lines

"""Prompts for one audience scoring numbered hotspot nominations."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from .audience_profiles import AudienceProfile
from .models import HotspotVote, VoterBallot, flatten_rationale

_RATIONALE_CHARS = 160


def audience_system(profile: AudienceProfile, category: str) -> str:
    axes = "、".join(profile.axes)
    label = category or "终端"
    return f"""你是{label}趋势报告的受众审阅人 {profile.audience_id}（{profile.name}）。
你不提名新热点，只给已有热点提名打分。

决策问题：{profile.decision_question}
关注轴：{axes}
语气：{profile.tone}
禁止：{profile.forbidden}

规则：
1. 只评估输入清单中的热点；不要新增热点、机型、销量、政策文件或外部数字。
2. hotspot_index 使用清单中的 1-based 编号；每个编号最多评估一次。
3. relevance 只能是 0 / 1 / 2 / 3（0=无关，3=必须关注）。
4. 证据不足时写入 caveat，why_it_matters / action_implication 可留空，禁止补写事实。
5. 只输出 JSON：{{"assessments":[{{"hotspot_index":1,"relevance":2,"why_it_matters":"...","action_implication":"...","caveat":"..."}}]}}
"""


def audience_user(
    profile: AudienceProfile,
    entries: Sequence[Tuple[str, HotspotVote]],
    ballots: Sequence[VoterBallot],
) -> str:
    listing = "\n".join(number_hotspots_for_audience(entries, ballots))
    return f"""受众：{profile.audience_id}（{profile.name}）
决策问题：{profile.decision_question}

### 编号热点（唯一评估对象） ###
{listing or "（无热点）"}

请按你的受众身份输出审阅 JSON。"""


def number_hotspots_for_audience(
    entries: Sequence[Tuple[str, HotspotVote]],
    ballots: Sequence[VoterBallot],
) -> List[str]:
    by_voter = {b.voter_id: b for b in ballots}
    lines: List[str] = []
    for i, (voter_id, hs) in enumerate(entries, start=1):
        ballot = by_voter.get(voter_id)
        frame = ballot.frame_name if ballot else voter_id
        ref = ballot.reference_frame if ballot else ""
        device = f"{hs.brand} {hs.model}".strip() or "（未绑定机型）"
        rationale = flatten_rationale(hs.rationale)[:_RATIONALE_CHARS]
        extra = f"\n   说明：{rationale}" if rationale else ""
        ref_bit = f" / {ref}" if ref else ""
        lines.append(f"{i}. [{voter_id}·{frame}{ref_bit}] {hs.title} — {device}{extra}")
    return lines


def number_hotspots_for_audience_from_ballots(
    ballots: Sequence[VoterBallot],
) -> List[str]:
    from .service import flatten_hotspots

    entries = flatten_hotspots(ballots)
    return number_hotspots_for_audience(entries, ballots)

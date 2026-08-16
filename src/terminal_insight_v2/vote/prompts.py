"""Build per-voter and clustering prompts. One voter = one reference frame."""
from __future__ import annotations

from typing import List, Sequence

from .models import HotspotVote
from .profiles import VoterProfile
from .project import VoteProjection, render_projection


def voter_system(profile: VoterProfile, category: str) -> str:
    axes = "、".join(profile.axes)
    anchors = "、".join(f"「{a}」" for a in profile.anchors)
    label = category or "终端"
    return f"""你是热点投票人 {profile.voter_id}（参考系名：{profile.name}）。你不是六人委员会的平均值。

参考系（稳定尺子，决定「凭什么重要」）：{profile.name} — {profile.reference_frame}
取景框（当季镜头，决定「把哪一块现实放进画面」）：{profile.framing}
坐标轴：{axes}
行文锚点：{anchors}
禁止：{profile.forbidden}

任务：基于给定的{label}参数投影，提名 2–3 个当季热点。
规则：
1. 只用你自己的参考系取景；不要模仿其他投票人（路线标尺、巧思定义、价位规格、选题展开、证据定位、痛点购机）。
2. 只能使用投影里出现的品牌/机型与字段，禁止编造未出现的机型、销量、播放量或官网未给出的数字。
3. 若投影证据不足以支撑某维度，该维度留空字符串，不要编造。
4. 每个热点必须能用你的尺子解释「为什么值得写」。
5. 只输出 JSON 对象：{{"hotspots":[{{"title":"...","brand":"...","model":"...","rationale":{{"innovation":"...","market":"...","user":"...","discussion":"..."}},"axis_tags":["..."]}}]}}
"""


def voter_user(profile: VoterProfile, projection: VoteProjection) -> str:
    body = render_projection(projection)
    return f"""投票人：{profile.voter_id}（{profile.name}）
参考系：{profile.name} — {profile.reference_frame}
取景框：{profile.framing}
品类：{projection.category or "terminal"}
input_revision：{projection.input_revision}

### 设备参数投影（唯一证据） ###
{body}

请按你的参考系提名 2–3 个热点 JSON。"""


def cluster_system() -> str:
    return """你是热点方向聚类助手。把多位投票人的热点按「技术方向」合并同类项。
规则：
1. 合并的是方向，不是含义：同一方向下必须保留每位投票人的坐标系（谁、哪套镜头），禁止把理由改写成同一套话。
2. 不要意见平均，不要发明新机型。
3. hotspot_ids 使用输入清单中的 1-based 编号。
4. 只输出 JSON：{{"clusters":[{{"direction":"...","hotspot_ids":[1,2]}}]}}
"""


def cluster_user(numbered: Sequence[str]) -> str:
    listing = "\n".join(numbered)
    return f"""### 热点清单 ###
{listing}

请输出方向聚类 JSON。"""


def number_hotspots(entries: Sequence[tuple[str, HotspotVote]]) -> List[str]:
    lines: List[str] = []
    for i, (voter_id, hs) in enumerate(entries, start=1):
        device = f"{hs.brand} {hs.model}".strip()
        tags = ",".join(hs.axis_tags) if hs.axis_tags else ""
        summary = (hs.rationale.innovation or hs.rationale.user or "").strip()
        extra = f" | {summary[:80]}" if summary else ""
        tag_bit = f" [{tags}]" if tags else ""
        lines.append(f"{i}. [{voter_id}] {hs.title} — {device}{tag_bit}{extra}")
    return lines

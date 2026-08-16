"""Stable AAA–FFF reference-frame × framing profiles (not self-reported)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .models import VOTER_IDS, VoterId


@dataclass(frozen=True)
class VoterProfile:
    voter_id: VoterId
    name: str
    reference_frame: str
    framing: str
    axes: Tuple[str, ...]
    anchors: Tuple[str, ...]
    forbidden: str
    lens: str


VOTER_PROFILES: Tuple[VoterProfile, ...] = (
    VoterProfile(
        voter_id="AAA",
        name="路线标尺",
        reference_frame="产业范式 / 技术路线分岔",
        framing="赛道级竞争格局与拐点叙事",
        axes=("代际节点", "路线分叉", "架构重构", "范式转移"),
        anchors=("标志着", "范式转移", "双路线竞争"),
        forbidden="不要写成价位规格清单或单品卖点手册；机型只是路线的载体。",
        lens="路线对垒",
    ),
    VoterProfile(
        voter_id="BBB",
        name="巧思定义",
        reference_frame="工程巧思 × 产品定义",
        framing="可命名的单点差异化方案",
        axes=("首创/稀缺", "定位叙事", "可感知卖点", "细分赛道"),
        anchors=("口袋哈苏", "实用主义大屏"),
        forbidden="不要做产业综述或纯规格对照；优先名字本身就是创新点的产品动作。",
        lens="产品巧思",
    ),
    VoterProfile(
        voter_id="CCC",
        name="价位规格",
        reference_frame="硬规格 × 价位带",
        framing="续航 / 影像 / 电竞的价位样本",
        axes=("硬指标", "价格带", "能力下放", "配置组合"),
        anchors=("在 X 价位首次实现 Y",),
        forbidden="不要写成路线对垒或痛点故事；对准「能买到的配置密度」。",
        lens="价位规格样本",
    ),
    VoterProfile(
        voter_id="DDD",
        name="选题展开",
        reference_frame="专题可展开性（研究选题）",
        framing="跨机趋势链，可下钻 / 可上卷",
        axes=("痛点普遍性", "可下钻", "可上卷", "跨品牌"),
        anchors=("适合作为重点热点", "具备进一步展开价值"),
        forbidden="不要只投单机卖点；先问能否写成后续洞察章节。",
        lens="选题展开链",
    ),
    VoterProfile(
        voter_id="EEE",
        name="证据定位",
        reference_frame="可核验的产品定位",
        framing="代表机肖像：官网 · 媒体 · 竞品 · 边界声明",
        axes=("技术创新", "市场/媒体", "用户吸引力", "信源分级"),
        anchors=("代表机", "未核验数据不采用"),
        forbidden="不要空喊热度；热点必须能被投影里的字段/价格撑住，定位标签要清晰。",
        lens="可核验代表机",
    ),
    VoterProfile(
        voter_id="FFF",
        name="痛点购机",
        reference_frame="痛点落差 → 购机意愿",
        framing="落差最大的单点；销量与传播作验证层",
        axes=("体验落差", "购机拉动", "社交传播", "竞品跟进"),
        anchors=("体验落差明显", "影响购买决策"),
        forbidden="销量与播放量只是验证层，不是唯一起点；不要写成规格清单。",
        lens="痛点验证",
    ),
)

_BY_ID = {p.voter_id: p for p in VOTER_PROFILES}


def profile_for(voter_id: str) -> VoterProfile:
    if voter_id not in _BY_ID:
        raise KeyError(f"未知投票人: {voter_id}; 可选: {list(VOTER_IDS)}")
    return _BY_ID[voter_id]

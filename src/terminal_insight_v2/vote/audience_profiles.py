"""Fixed audience lenses for post-cluster review (not voter reference frames)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .models import AUDIENCE_IDS, AudienceId


@dataclass(frozen=True)
class AudienceProfile:
    audience_id: AudienceId
    name: str
    decision_question: str
    axes: Tuple[str, ...]
    forbidden: str
    tone: str


AUDIENCE_PROFILES: Tuple[AudienceProfile, ...] = (
    AudienceProfile(
        audience_id="REG",
        name="工信/监管",
        decision_question="该方向是否涉及产业升级、关键技术、标准、安全或市场秩序？",
        axes=("产业升级", "关键技术自主", "标准协同", "安全与合规", "市场秩序"),
        forbidden="不要写成购机攻略或品牌公关稿；不要编造政策文件号、未出现的销量或渗透率。",
        tone="政策与产业治理口吻：关注可监管、可对标、可落地的信号。",
    ),
    AudienceProfile(
        audience_id="CON",
        name="消费者",
        decision_question="该方向是否改变真实体验、价格、可靠性、隐私或购买价值？",
        axes=("体验改善", "价格与性价比", "可靠性", "隐私", "购买价值"),
        forbidden="不要写成产业综述或供应链分析；不要编造未出现的评测分数、销量或口碑数据。",
        tone="购机决策口吻：先问值不值得买、会不会踩坑。",
    ),
    AudienceProfile(
        audience_id="OEM",
        name="终端企业",
        decision_question="该方向是否改变产品差异化、路线选择、竞争位置或商业机会？",
        axes=("差异化", "产品路线", "竞争位置", "生态入口", "商业机会"),
        forbidden="不要写成监管清单或个人开箱笔记；不要编造未出现的出货量、份额或内部规划。",
        tone="产品与竞争策略口吻：关注跟进、差异化和窗口期。",
    ),
    AudienceProfile(
        audience_id="SUP",
        name="上下游制造商",
        decision_question="该方向是否改变需求信号、技术规格、供应风险、产能或成本结构？",
        axes=("需求信号", "规格变化", "供应风险", "产能", "成本"),
        forbidden="不要写成消费者种草或宏观政策评论；不要编造未出现的 BOM、良率或订单数字。",
        tone="供应链与器件口吻：关注规格拉动和交付约束。",
    ),
)

_BY_ID = {p.audience_id: p for p in AUDIENCE_PROFILES}


def audience_for(audience_id: str) -> AudienceProfile:
    if audience_id not in _BY_ID:
        raise KeyError(f"未知受众: {audience_id}; 可选: {list(AUDIENCE_IDS)}")
    return _BY_ID[audience_id]

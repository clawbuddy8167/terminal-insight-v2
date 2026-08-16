"""Vote orchestration: six ballots + light direction clustering."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from terminal_insight_v2.providers.llm import LLMProvider

from .models import (
    ClusterAxis,
    ClusterDevice,
    ClusterPayload,
    DirectionCluster,
    HotspotVote,
    VoterBallot,
    VoterBallotPayload,
)
from .profiles import VOTER_PROFILES, VoterProfile, profile_for
from .project import VoteProjection
from .prompts import cluster_system, cluster_user, number_hotspots, voter_system, voter_user

_MAX_HOTSPOTS = 3

_KEYWORD_BUCKETS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("高端影像升级", ("影像", "长焦", "像素", "光学", "主摄", "哈苏", "潜望", "变焦")),
    ("超大容量电池与长续航", ("续航", "电池", "毫安", "mah", "充电", "硅碳")),
    ("终端形态与AI交互", ("折叠", "形态", "折痕", "ai", "智能体", "阔折")),
    ("电竞性能与性能下探", ("电竞", "性能", "散热", "芯片", "风冷", "独显")),
)


def collect_ballots(
    projection: VoteProjection,
    llm: LLMProvider,
    *,
    profiles: Sequence[VoterProfile] = VOTER_PROFILES,
) -> Tuple[List[VoterBallot], List[str]]:
    ballots: List[VoterBallot] = []
    errors: List[str] = []
    for profile in profiles:
        system = voter_system(profile, projection.category)
        user = voter_user(profile, projection)
        try:
            payload = llm.chat_json(
                system,
                user,
                VoterBallotPayload,
                temperature=0.35,
                max_tokens=4096,
            )
            hotspots = _clip_hotspots(payload.hotspots)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{profile.voter_id}: {exc}")
            hotspots = []
        ballots.append(
            VoterBallot(
                voter_id=profile.voter_id,
                frame_name=profile.name,
                reference_frame=profile.reference_frame,
                framing=profile.framing,
                hotspots=hotspots,
            )
        )
    return ballots, errors


def flatten_hotspots(ballots: Sequence[VoterBallot]) -> List[Tuple[str, HotspotVote]]:
    out: List[Tuple[str, HotspotVote]] = []
    for ballot in ballots:
        for hs in ballot.hotspots:
            out.append((ballot.voter_id, hs))
    return out


def cluster_hotspots(
    ballots: Sequence[VoterBallot],
    llm: Optional[LLMProvider],
) -> List[DirectionCluster]:
    entries = flatten_hotspots(ballots)
    if not entries:
        return []
    if llm is not None:
        try:
            payload = llm.chat_json(
                cluster_system(),
                cluster_user(number_hotspots(entries)),
                ClusterPayload,
                temperature=0.2,
                max_tokens=2048,
            )
            built = _clusters_from_ids(payload, entries)
            if built:
                return built
        except Exception:  # noqa: BLE001
            pass
    return _heuristic_clusters(entries)


def _clip_hotspots(hotspots: Sequence[HotspotVote]) -> List[HotspotVote]:
    kept: List[HotspotVote] = []
    for hs in hotspots:
        title = (hs.title or "").strip()
        if not title:
            continue
        kept.append(hs)
        if len(kept) >= _MAX_HOTSPOTS:
            break
    return kept


def _clusters_from_ids(
    payload: ClusterPayload,
    entries: Sequence[Tuple[str, HotspotVote]],
) -> List[DirectionCluster]:
    clusters: List[DirectionCluster] = []
    seen: set[int] = set()
    n = len(entries)
    for draft in payload.clusters:
        picked: List[Tuple[str, HotspotVote]] = []
        for hid in draft.hotspot_ids:
            idx = hid - 1
            if idx < 0 or idx >= n or idx in seen:
                continue
            seen.add(idx)
            picked.append(entries[idx])
        if picked:
            clusters.append(_build_cluster(draft.direction.strip() or "未命名方向", picked))
    leftover = [entries[i] for i in range(n) if i not in seen]
    if leftover:
        clusters.extend(_heuristic_clusters(leftover))
    return clusters


def _heuristic_clusters(
    entries: Sequence[Tuple[str, HotspotVote]],
) -> List[DirectionCluster]:
    buckets: Dict[str, List[Tuple[str, HotspotVote]]] = {}
    for item in entries:
        buckets.setdefault(_bucket_name(item[1]), []).append(item)
    return [_build_cluster(name, items) for name, items in buckets.items() if items]


def _bucket_name(hs: HotspotVote) -> str:
    blob = f"{hs.title} {hs.rationale.innovation} {hs.rationale.user}".lower()
    for name, keys in _KEYWORD_BUCKETS:
        if any(k in blob for k in keys):
            return name
    return "其他观察"


def _build_cluster(
    direction: str,
    items: Sequence[Tuple[str, HotspotVote]],
) -> DirectionCluster:
    voter_ids: List[str] = []
    axes: List[ClusterAxis] = []
    devices: List[ClusterDevice] = []
    seen_dev: set[tuple[str, str]] = set()
    for voter_id, hs in items:
        if voter_id not in voter_ids:
            voter_ids.append(voter_id)
            try:
                lens = profile_for(voter_id).lens
            except KeyError:
                lens = ""
            axes.append(ClusterAxis(voter_id=voter_id, lens=lens))
        key = (hs.brand.strip(), hs.model.strip())
        if key != ("", "") and key not in seen_dev:
            seen_dev.add(key)
            devices.append(ClusterDevice(brand=key[0], model=key[1]))
    return DirectionCluster(
        direction=direction,
        mention_count=len(items),
        voter_ids=voter_ids,
        devices=devices,
        axes_preserved=axes,
    )

"""Deterministic cross-run settlement of hypothesis mappings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from terminal_insight_v2.config import settings
from terminal_insight_v2.store.db import utc_now

from .models import (
    HypothesisSettlement,
    HypothesisSet,
    OemSliceItem,
    QuarterStance,
    RepresentativeHotspot,
    SettlementArtifact,
    StanceCounts,
    Verdict,
)


def settle_runs(
    hypo_set: HypothesisSet,
    run_ids: Sequence[str],
    *,
    runs_root: Optional[Path] = None,
) -> SettlementArtifact:
    """Load votes.json per run and produce deterministic verdicts.

    Missing votes.json → that quarter contributes nothing; verdict may be insufficient.
    """
    root = runs_root or settings.runs_root()
    errors: List[str] = []
    # hypothesis_id -> run_id -> list of review dicts
    by_hypo: Dict[str, Dict[str, List[dict]]] = {
        h.id: {} for h in hypo_set.hypotheses
    }
    oem_slice: List[OemSliceItem] = []
    resolved_runs: List[str] = []

    for run_id in run_ids:
        rid = (run_id or "").strip()
        if not rid:
            continue
        path = root / rid / "votes.json"
        if not path.is_file():
            errors.append(f"{rid}: missing votes.json")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{rid}: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{rid}: votes.json not an object")
            continue
        resolved_runs.append(rid)
        for rev in data.get("hypothesis_reviews") or []:
            if not isinstance(rev, dict):
                continue
            hid = str(rev.get("hypothesis_id") or "").strip()
            if hid not in by_hypo:
                continue
            by_hypo[hid].setdefault(rid, []).append(rev)
        oem_slice.extend(_oem_from_votes(rid, data))

    settlements: List[HypothesisSettlement] = []
    for hypo in hypo_set.hypotheses:
        quarters, reps = _quarter_stats(by_hypo.get(hypo.id, {}), resolved_runs)
        verdict, note = _verdict_for(quarters)
        settlements.append(
            HypothesisSettlement(
                hypothesis_id=hypo.id,
                statement=hypo.statement,
                verdict=verdict,
                by_quarter=quarters,
                representatives=reps[:5],
                note=note,
            )
        )

    return SettlementArtifact(
        schema_version=1,
        year=hypo_set.year,
        category=hypo_set.category,
        hypothesis_source=hypo_set.source,
        run_ids=list(run_ids),
        generated_at=utc_now(),
        settlements=settlements,
        oem_slice=oem_slice,
        errors=errors,
    )


def _oem_from_votes(run_id: str, data: dict) -> List[OemSliceItem]:
    out: List[OemSliceItem] = []
    for review in data.get("audience_reviews") or []:
        if not isinstance(review, dict):
            continue
        if str(review.get("audience_id") or "") != "OEM":
            continue
        for item in review.get("assessments") or []:
            if not isinstance(item, dict):
                continue
            relevance = int(item.get("relevance") or 0)
            if relevance < 2:
                continue
            out.append(
                OemSliceItem(
                    run_id=run_id,
                    title=str(item.get("title") or ""),
                    brand=str(item.get("brand") or ""),
                    model=str(item.get("model") or ""),
                    relevance=relevance,
                    action_implication=str(item.get("action_implication") or ""),
                    why_it_matters=str(item.get("why_it_matters") or ""),
                    caveat=str(item.get("caveat") or ""),
                )
            )
    return out


def _quarter_stats(
    reviews_by_run: Dict[str, List[dict]],
    run_order: Sequence[str],
) -> Tuple[List[QuarterStance], List[RepresentativeHotspot]]:
    quarters: List[QuarterStance] = []
    reps: List[RepresentativeHotspot] = []
    for rid in run_order:
        rows = reviews_by_run.get(rid) or []
        counts = StanceCounts()
        for rev in rows:
            stance = str(rev.get("stance") or "")
            if stance == "support":
                counts.support += 1
                if len(reps) < 8:
                    reps.append(
                        RepresentativeHotspot(
                            run_id=rid,
                            title=str(rev.get("title") or ""),
                            brand=str(rev.get("brand") or ""),
                            model=str(rev.get("model") or ""),
                            stance="support",
                            voter_id=str(rev.get("voter_id") or ""),
                        )
                    )
            elif stance == "weaken":
                counts.weaken += 1
                if len(reps) < 8:
                    reps.append(
                        RepresentativeHotspot(
                            run_id=rid,
                            title=str(rev.get("title") or ""),
                            brand=str(rev.get("brand") or ""),
                            model=str(rev.get("model") or ""),
                            stance="weaken",
                            voter_id=str(rev.get("voter_id") or ""),
                        )
                    )
            elif stance == "unrelated":
                counts.unrelated += 1
        quarters.append(QuarterStance(run_id=rid, counts=counts))
    return quarters, reps


def _verdict_for(quarters: Sequence[QuarterStance]) -> Tuple[Verdict, str]:
    """Deterministic rules from the plan.

    - Count only support/weaken; unrelated ignored
    - Quarters with net support (support > weaken)
    - Quarters with net weaken (weaken > support)
    - ≥2 net-support quarters and no consecutive net-weaken → confirmed
      (if only 1 quarter has any support/weaken signal → partial)
    - ≥2 net-weaken quarters → falsified
    - else insufficient
    """
    net_support_runs: List[str] = []
    net_weaken_runs: List[str] = []
    signaled = 0
    weaken_flags: List[bool] = []

    for q in quarters:
        s, w = q.counts.support, q.counts.weaken
        if s + w == 0:
            weaken_flags.append(False)
            continue
        signaled += 1
        if s > w:
            net_support_runs.append(q.run_id)
            weaken_flags.append(False)
        elif w > s:
            net_weaken_runs.append(q.run_id)
            weaken_flags.append(True)
        else:
            weaken_flags.append(False)

    consecutive_weaken = any(
        weaken_flags[i] and weaken_flags[i + 1] for i in range(len(weaken_flags) - 1)
    )

    if len(net_weaken_runs) >= 2:
        return "falsified", f"净削弱季度: {', '.join(net_weaken_runs)}"

    if len(net_support_runs) >= 2 and not consecutive_weaken:
        return "confirmed", f"净支持季度: {', '.join(net_support_runs)}"

    if len(net_support_runs) == 1 and signaled == 1 and not consecutive_weaken:
        return "partial", f"仅一季有支持信号: {net_support_runs[0]}"

    if len(net_support_runs) >= 1 and consecutive_weaken:
        return "insufficient", "存在连续净削弱季度，未达确认门槛"

    if len(net_support_runs) >= 2 and consecutive_weaken:
        return "insufficient", "支持季度≥2但存在连续净削弱"

    return "insufficient", "支持/削弱信号不足"

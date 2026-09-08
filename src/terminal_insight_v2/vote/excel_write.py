"""Patch the run workbook's 亮点投票 and 受众视角 sheets from a VotesArtifact."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .models import VotesArtifact, flatten_rationale

SHEET_NAME = "亮点投票"
HEADERS = ["参考系", "取景框", "热点", "品牌", "机型", "说明"]
_WIDTHS = (28, 32, 28, 14, 22, 48)

AUDIENCE_SHEET_NAME = "受众视角"
AUDIENCE_HEADERS = [
    "受众",
    "参考系",
    "热点",
    "品牌",
    "机型",
    "相关度",
    "为什么关注",
    "行动启示",
    "风险与证据边界",
]
_AUDIENCE_WIDTHS = (14, 18, 28, 12, 18, 8, 32, 32, 32)

HYPOTHESIS_SHEET_NAME = "假说对照"
HYPOTHESIS_HEADERS = [
    "假说ID",
    "命题摘要",
    "立场",
    "参考系",
    "热点",
    "品牌",
    "机型",
    "证据锚点",
    "强度",
    "说明",
]
_HYPOTHESIS_WIDTHS = (10, 36, 10, 12, 24, 12, 18, 28, 6, 32)


def find_workbook(run_dir: Path) -> Optional[Path]:
    files = sorted(p for p in run_dir.glob("*.xlsx") if not p.name.startswith("~$"))
    if not files:
        return None
    return files[0]


def write_vote_sheet(path: Path, artifact: VotesArtifact) -> Path:
    if path.exists():
        wb = load_workbook(path)
    else:
        wb = Workbook()
        default = wb.active
        if default is not None and default.title == "Sheet":
            wb.remove(default)
    _fill_hotspot_sheet(_ensure_sheet(wb, SHEET_NAME), artifact)
    _fill_audience_sheet(_ensure_sheet(wb, AUDIENCE_SHEET_NAME), artifact)
    _fill_hypothesis_sheet(_ensure_sheet(wb, HYPOTHESIS_SHEET_NAME), artifact)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def write_votes_excel(run_dir: Path, artifact: VotesArtifact, *, category: str = "") -> Path:
    existing = find_workbook(run_dir)
    if existing is not None:
        return write_vote_sheet(existing, artifact)
    name = f"{category or artifact.category or 'run'}_{artifact.run_id}.xlsx"
    return write_vote_sheet(run_dir / name, artifact)


def row_count(artifact: VotesArtifact) -> int:
    return sum(len(b.hotspots) for b in artifact.voters)


def _ensure_sheet(wb, name: str) -> Worksheet:
    if name in wb.sheetnames:
        return wb[name]
    return wb.create_sheet(name)


def _reset_sheet(ws: Worksheet, headers: Sequence[str]) -> None:
    if ws.max_row >= 1:
        ws.delete_rows(1, ws.max_row)
    ws.append(list(headers))
    for cell in ws[1]:
        cell.font = Font(bold=True)


def _apply_widths_and_wrap(ws: Worksheet, widths: Sequence[float]) -> None:
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")


def _fill_hotspot_sheet(ws: Worksheet, artifact: VotesArtifact) -> None:
    _reset_sheet(ws, HEADERS)
    for ballot in artifact.voters:
        for hs in ballot.hotspots:
            ws.append(
                [
                    ballot.reference_frame,
                    ballot.framing,
                    hs.title,
                    hs.brand,
                    hs.model,
                    flatten_rationale(hs.rationale),
                ]
            )
    _apply_widths_and_wrap(ws, _WIDTHS)


def _fill_audience_sheet(ws: Worksheet, artifact: VotesArtifact) -> None:
    _reset_sheet(ws, AUDIENCE_HEADERS)
    for review in artifact.audience_reviews:
        for item in review.assessments:
            ws.append(
                [
                    review.name,
                    item.frame_name,
                    item.title,
                    item.brand,
                    item.model,
                    item.relevance,
                    item.why_it_matters,
                    item.action_implication,
                    item.caveat,
                ]
            )
    _apply_widths_and_wrap(ws, _AUDIENCE_WIDTHS)


def _fill_hypothesis_sheet(ws: Worksheet, artifact: VotesArtifact) -> None:
    _reset_sheet(ws, HYPOTHESIS_HEADERS)
    by_voter = {b.voter_id: b for b in artifact.voters}
    for item in artifact.hypothesis_reviews:
        ballot = by_voter.get(item.voter_id)
        frame = ballot.frame_name if ballot else item.voter_id
        statement = (item.statement or "")[:80]
        ws.append(
            [
                item.hypothesis_id,
                statement,
                item.stance,
                frame,
                item.title,
                item.brand,
                item.model,
                item.evidence,
                item.strength,
                item.note,
            ]
        )
    _apply_widths_and_wrap(ws, _HYPOTHESIS_WIDTHS)

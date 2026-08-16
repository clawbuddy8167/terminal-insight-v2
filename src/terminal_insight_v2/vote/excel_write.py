"""Patch the run workbook's 亮点投票 sheet from a VotesArtifact."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .models import VotesArtifact, flatten_rationale

SHEET_NAME = "亮点投票"
HEADERS = ["参考系", "取景框", "热点", "品牌", "机型", "说明"]
_WIDTHS = (28, 32, 28, 14, 22, 48)


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
    ws = _sheet(wb)
    _reset_sheet(ws)
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
    for idx, width in enumerate(_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
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


def _sheet(wb) -> Worksheet:
    if SHEET_NAME in wb.sheetnames:
        return wb[SHEET_NAME]
    return wb.create_sheet(SHEET_NAME)


def _reset_sheet(ws: Worksheet) -> None:
    if ws.max_row >= 1:
        ws.delete_rows(1, ws.max_row)
    ws.append(list(HEADERS))
    for cell in ws[1]:
        cell.font = Font(bold=True)

#!/usr/bin/env python3
"""Import 手机/眼镜/手表 sheets into Vote-ready resolved.json runs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from terminal_insight_v2.importers.collected_xlsx import import_workbook

DEFAULT_XLSX = ROOT / "data" / "2026年1-8月智能终端基础与衍生字段采集(2).xlsx"


def main() -> int:
    p = argparse.ArgumentParser(description="Convert collected-fields xlsx → resolved.json")
    p.add_argument("--xlsx", default=str(DEFAULT_XLSX), help="source workbook")
    p.add_argument("--start", default="2026-01-01")
    p.add_argument("--end", default="2026-08-31")
    p.add_argument(
        "--include-candidates",
        action="store_true",
        help="keep 数据状态=candidate_only rows",
    )
    args = p.parse_args()
    summaries = import_workbook(
        Path(args.xlsx),
        date_start=args.start,
        date_end=args.end,
        include_candidates=args.include_candidates,
    )
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI entrypoint."""
from __future__ import annotations

import argparse
import json
import sys

from rich.console import Console

from terminal_insight_v2 import __version__
from terminal_insight_v2.config import STAGES, settings
from terminal_insight_v2.orchestrator import run_pipeline
from terminal_insight_v2.store import ensure_memory_dirs
from terminal_insight_v2.store.db import schema_version

console = Console()


def _cmd_init(_args: argparse.Namespace) -> int:
    root = ensure_memory_dirs()
    ver = schema_version()
    console.print(f"memory root: {root}")
    console.print(f"facts.db schema version: {ver}")
    console.print(f"runs root: {settings.runs_root()}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    stages = None
    if args.stages:
        stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    result = run_pipeline(
        category=args.category or settings.category,
        stages=stages,
        date_start=args.start or settings.date_start,
        date_end=args.end or settings.date_end,
        schema_fingerprint=args.schema_fingerprint or "pending",
        resume_run_id=args.resume,
    )
    console.print_json(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="terminal-insight-v2",
        description="Evidence-first terminal research pipeline",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create data dirs and apply DB migrations")
    init.set_defaults(func=_cmd_init)

    run = sub.add_parser("run", help="Run pipeline stages")
    run.add_argument("--category", default="", help="phone|watch|glasses|…")
    run.add_argument("--start", default="", help="DATE_START YYYY-MM-DD")
    run.add_argument("--end", default="", help="DATE_END YYYY-MM-DD")
    run.add_argument(
        "--stages",
        default="all",
        help=f"comma-separated or all; choices: {','.join(STAGES)}",
    )
    run.add_argument("--resume", default="", help="resume existing run_id")
    run.add_argument(
        "--schema-fingerprint",
        default="pending",
        help="category schema fingerprint (until compiler lands)",
    )
    run.set_defaults(func=_cmd_run)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()

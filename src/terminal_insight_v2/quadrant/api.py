"""Public quadrant API — research view, not a Stage."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from terminal_insight_v2.category.schema import CategorySchema

from .models import QuadrantArtifact
from .render import write_quadrant_html
from .service import build_from_run_dir


def write_for_run(
    run_dir: Path,
    *,
    schema: Optional[CategorySchema] = None,
) -> Tuple[QuadrantArtifact, Path, Path]:
    """Build and write quadrant.json + quadrant.html under run_dir.

    Returns (artifact, json_path, html_path).
    """
    run_dir = Path(run_dir)
    artifact = build_from_run_dir(run_dir, schema=schema)
    json_path = run_dir / "quadrant.json"
    html_path = run_dir / "quadrant.html"
    json_path.write_text(
        json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_quadrant_html(html_path, artifact)
    return artifact, json_path, html_path

"""PyWebView API bridge for the MVP GUI.

Contract (JS → ``pywebview.api.<method>``):
- get_config / save_config
- list_categories / list_runs / select_run
- run_pipeline / run_from_stage / get_progress
- get_coverage / open_artifact
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from terminal_insight_v2.category import list_category_ids
from terminal_insight_v2.config import PROJECT_ROOT, STAGES, settings
from terminal_insight_v2.gui.env_merge import merge_env_file
from terminal_insight_v2.orchestrator import normalize_stages, run_pipeline
from terminal_insight_v2.store.ledger import get_run, list_runs

STAGE_LABELS = {
    "collect": "采集",
    "extract": "抽取",
    "backfill": "补链",
    "verify": "校验",
    "excel": "Excel",
    "vote": "Vote",
}


def stages_from(stage: str) -> List[str]:
    """Return ``stage`` and all following stages in pipeline order."""
    if stage not in STAGES:
        raise ValueError(f"未知阶段: {stage}; 可选: {list(STAGES)}")
    idx = STAGES.index(stage)
    return list(STAGES[idx:])


class GuiApi:
    """Methods here are callable from JS as ``pywebview.api.<method>(...)``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._error: Optional[str] = None
        self._requested_stages: List[str] = []
        self._active_run_id: str = ""
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ config
    def get_config(self) -> Dict[str, Any]:
        cats = list_category_ids()
        return {
            "category": settings.category,
            "categories": [{"id": c, "label": c} for c in cats],
            "date_start": settings.date_start,
            "date_end": settings.date_end,
            "stages": list(STAGES),
            "stage_labels": dict(STAGE_LABELS),
            "openai_model": settings.openai_model,
            "openai_base_url": settings.openai_base_url,
            "openai_api_key": settings.openai_api_key,
            "doubao_api_key": settings.doubao_api_key,
            "tavily_api_key": settings.tavily_api_key,
            "discovery_backend": settings.discovery_backend,
            "collect_max_workers": settings.collect_max_workers,
            "extract_max_workers": settings.extract_max_workers,
            "backfill_max_rounds": settings.backfill_max_rounds,
            "report_mode": settings.report_mode,
            "data_root": str(settings.data_path()),
            "runs_root": str(settings.runs_root()),
            "active_run_id": self._active_run_id,
        }

    def save_config(self, cfg: Any = None, **kwargs: Any) -> Dict[str, Any]:
        """Persist editable knobs to ``.env`` and update live ``settings``."""
        if isinstance(cfg, dict):
            data = dict(cfg)
        elif cfg is None:
            data = dict(kwargs)
        else:
            return {"ok": False, "error": "无效的配置参数"}

        category = str(data.get("category", settings.category) or "phone").strip().lower()
        date_start = str(data.get("date_start", settings.date_start) or "").strip()
        date_end = str(data.get("date_end", settings.date_end) or "").strip()
        openai_model = str(data.get("openai_model", settings.openai_model) or "")
        openai_base_url = str(data.get("openai_base_url", settings.openai_base_url) or "")
        openai_api_key = str(data.get("openai_api_key", settings.openai_api_key) or "")
        doubao_api_key = str(data.get("doubao_api_key", settings.doubao_api_key) or "")
        tavily_api_key = str(data.get("tavily_api_key", settings.tavily_api_key) or "")
        discovery_backend = str(
            data.get("discovery_backend", settings.discovery_backend) or "auto"
        ).strip().lower()
        if discovery_backend not in ("auto", "doubao", "tavily"):
            return {"ok": False, "error": "DISCOVERY_BACKEND 须为 auto / doubao / tavily"}

        try:
            collect_max_workers = int(
                data.get("collect_max_workers", settings.collect_max_workers) or 4
            )
            extract_max_workers = int(
                data.get("extract_max_workers", settings.extract_max_workers) or 4
            )
            backfill_max_rounds = int(
                data.get("backfill_max_rounds", settings.backfill_max_rounds) or 3
            )
        except (TypeError, ValueError):
            return {"ok": False, "error": "worker / rounds 须为整数"}

        report_mode = str(data.get("report_mode", settings.report_mode) or "research").strip()
        if report_mode not in ("research", "gold"):
            return {"ok": False, "error": "REPORT_MODE 须为 research / gold"}

        merge_env_file(
            PROJECT_ROOT / ".env",
            {
                "CATEGORY": category,
                "DATE_START": date_start,
                "DATE_END": date_end,
                "OPENAI_MODEL": openai_model,
                "OPENAI_BASE_URL": openai_base_url,
                "OPENAI_API_KEY": openai_api_key,
                "DOUBAO_API_KEY": doubao_api_key,
                "TAVILY_API_KEY": tavily_api_key,
                "DISCOVERY_BACKEND": discovery_backend,
                "COLLECT_MAX_WORKERS": str(collect_max_workers),
                "EXTRACT_MAX_WORKERS": str(extract_max_workers),
                "BACKFILL_MAX_ROUNDS": str(backfill_max_rounds),
                "REPORT_MODE": report_mode,
            },
        )

        settings.category = category
        settings.date_start = date_start
        settings.date_end = date_end
        settings.openai_model = openai_model
        settings.openai_base_url = openai_base_url
        settings.openai_api_key = openai_api_key
        settings.doubao_api_key = doubao_api_key
        settings.tavily_api_key = tavily_api_key
        settings.discovery_backend = discovery_backend
        settings.collect_max_workers = collect_max_workers
        settings.extract_max_workers = extract_max_workers
        settings.backfill_max_rounds = backfill_max_rounds
        settings.report_mode = report_mode  # type: ignore[assignment]
        return {"ok": True}

    def list_categories(self) -> Dict[str, Any]:
        cats = list_category_ids()
        return {"ok": True, "categories": [{"id": c, "label": c} for c in cats]}

    # ------------------------------------------------------------------ runs
    def list_runs(self, limit: int = 40, category: str = "") -> Dict[str, Any]:
        rows = list_runs(limit=limit, category=category or "")
        items = []
        for r in rows:
            items.append(
                {
                    "run_id": r.get("run_id") or "",
                    "category": r.get("category") or "",
                    "date_start": r.get("date_start") or "",
                    "date_end": r.get("date_end") or "",
                    "status": r.get("status") or "",
                    "created_at": r.get("created_at") or "",
                    "finished_at": r.get("finished_at") or "",
                    "rel_path": r.get("rel_path") or "",
                }
            )
        return {"ok": True, "runs": items, "active_run_id": self._active_run_id}

    def select_run(self, run_id: str = "") -> Dict[str, Any]:
        rid = (run_id or "").strip()
        if not rid:
            return {"ok": False, "error": "缺少 run_id"}
        meta = get_run(rid)
        if not meta:
            # filesystem fallback via list_runs
            for r in list_runs(limit=200):
                if r.get("run_id") == rid:
                    meta = r
                    break
        if not meta:
            return {"ok": False, "error": f"run 不存在: {rid}"}
        with self._lock:
            if self._running:
                return {"ok": False, "error": "流水线运行中，暂不可切换 run"}
            self._active_run_id = rid
            self._error = None
        return {"ok": True, "run": dict(meta)}

    # ------------------------------------------------------------------ pipeline
    def run_pipeline(
        self,
        stages: Any = None,
        opts: Any = None,
    ) -> Dict[str, Any]:
        """Start pipeline in a background thread. Returns immediately.

        JS bridge passes at most two positionals; put overrides in ``opts`` dict:
        ``{category, date_start, date_end, resume, from_stage, collect_mode, targets}``.
        """
        if isinstance(stages, dict) and opts is None:
            opts = stages
            stages = None
        options: Dict[str, Any] = dict(opts) if isinstance(opts, dict) else {}

        with self._lock:
            if self._running:
                return {"ok": False, "error": "已有任务在运行"}
            self._running = True
            self._error = None

        from_stage = str(options.get("from_stage") or "").strip()
        try:
            if from_stage:
                requested = stages_from(from_stage)
            elif not stages or stages == "all" or (
                isinstance(stages, (list, tuple)) and "all" in stages
            ):
                requested = list(STAGES)
            else:
                requested = normalize_stages(list(stages))
        except ValueError as exc:
            with self._lock:
                self._running = False
            return {"ok": False, "error": str(exc)}

        cat = str(options.get("category") or settings.category or "phone").strip()
        ds = str(options.get("date_start") or settings.date_start or "").strip()
        de = str(options.get("date_end") or settings.date_end or "").strip()
        resume_id = str(options.get("resume") or "").strip() or None
        collect_mode = str(options.get("collect_mode") or "window").strip().lower()
        extras: Dict[str, Any] = {}
        if collect_mode == "targets" and "collect" in requested and not resume_id:
            from terminal_insight_v2.targets import coerce_targets

            rows = coerce_targets(options.get("targets"))
            if not rows:
                with self._lock:
                    self._running = False
                return {"ok": False, "error": "定向机型为空：请先解析并确认品牌+型号清单"}
            extras["targets"] = [t.model_dump() for t in rows]
        self._requested_stages = list(requested)
        if resume_id:
            with self._lock:
                self._active_run_id = resume_id

        fingerprint = "pending"
        try:
            from terminal_insight_v2.category import load_category_schema

            schema = load_category_schema(cat, persist=True)
            fingerprint = schema.fingerprint
        except Exception:
            # Allow stub stages without template; real stages fail later.
            fingerprint = "pending"

        def _on_run_ready(run_id: str, _run_dir: str) -> None:
            with self._lock:
                self._active_run_id = run_id

        def _worker() -> None:
            try:
                result = run_pipeline(
                    category=cat,
                    stages=requested,
                    date_start=ds,
                    date_end=de,
                    schema_fingerprint=fingerprint,
                    resume_run_id=resume_id,
                    extras=extras,
                    on_run_ready=_on_run_ready,
                )
                rid = str(result.get("run_id") or "")
                with self._lock:
                    if rid:
                        self._active_run_id = rid
                    if result.get("status") != "ok":
                        self._error = f"流水线结束: {result.get('status')}"
            except Exception as exc:
                with self._lock:
                    self._error = f"{type(exc).__name__}: {exc}"
            finally:
                with self._lock:
                    self._running = False

        self._thread = threading.Thread(target=_worker, daemon=True, name="pipeline")
        self._thread.start()
        return {"ok": True, "stages": requested, "resume": resume_id or ""}

    def run_from_stage(self, stage: str, opts: Any = None) -> Dict[str, Any]:
        options: Dict[str, Any] = dict(opts) if isinstance(opts, dict) else {}
        options["from_stage"] = stage
        return self.run_pipeline(None, options)

    def parse_targets(self, text: str = "") -> Dict[str, Any]:
        from terminal_insight_v2.targets import parse_targets

        result = parse_targets(text or "")
        return {
            "ok": True,
            "targets": [t.model_dump() for t in result.targets],
            "errors": [e.model_dump() for e in result.errors],
        }

    def get_progress(self) -> Dict[str, Any]:
        run_id = self._active_run_id
        run_dir = self._resolve_run_dir(run_id) if run_id else None
        steps: List[Dict[str, Any]] = []
        if run_dir and (run_dir / "steps.json").exists():
            try:
                raw = json.loads((run_dir / "steps.json").read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    steps = raw
            except Exception:
                steps = []

        stage_status = {s: "pending" for s in STAGES}
        metrics_by_stage: Dict[str, Any] = {}
        for st in steps:
            name = st.get("stage")
            if name not in stage_status:
                continue
            status = st.get("status") or "ok"
            if status in ("ok", "skipped", "partial"):
                stage_status[name] = "done"
            elif status == "failed":
                stage_status[name] = "failed"
            metrics_by_stage[name] = st.get("metrics") or {}

        if self._running:
            for s in self._requested_stages:
                if stage_status.get(s) not in ("done", "failed"):
                    stage_status[s] = "running"
                    break

        current = next((s for s in STAGES if stage_status.get(s) == "running"), None)
        meta = get_run(run_id) if run_id else None
        return {
            "running": self._running,
            "error": self._error,
            "run_id": run_id,
            "run_dir": str(run_dir) if run_dir else "",
            "run_status": (meta or {}).get("status") or "",
            "current_stage": current,
            "stage_status": stage_status,
            "metrics": metrics_by_stage,
            "steps": steps[-30:],
            "artifacts": self._artifact_map(run_dir) if run_dir else {},
        }

    def get_coverage(self, run_id: str = "") -> Dict[str, Any]:
        rid = (run_id or self._active_run_id or "").strip()
        run_dir = self._resolve_run_dir(rid) if rid else None
        if not run_dir:
            return {"ok": True, "items": [], "run_id": rid}
        path = run_dir / "coverage_report.json"
        if not path.exists():
            return {"ok": True, "items": [], "run_id": rid}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "error": str(exc), "items": []}
        items = data.get("items") if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = []
        return {"ok": True, "run_id": rid, "items": items}

    def open_artifact(self, kind: str = "run_dir", run_id: str = "") -> Dict[str, Any]:
        """Open excel / sources.html / run directory in the OS default app."""
        rid = (run_id or self._active_run_id or "").strip()
        run_dir = self._resolve_run_dir(rid) if rid else None
        if not run_dir or not run_dir.is_dir():
            return {"ok": False, "error": "没有可打开的 run 目录"}

        arts = self._artifact_map(run_dir)
        kind = (kind or "run_dir").strip().lower()
        if kind == "run_dir":
            target = run_dir
        elif kind == "excel":
            target = Path(arts["excel"]) if arts.get("excel") else None
        elif kind in ("sources", "sources.html"):
            target = Path(arts["sources"]) if arts.get("sources") else None
        else:
            return {"ok": False, "error": f"未知产物类型: {kind}"}

        if target is None or not Path(target).exists():
            return {"ok": False, "error": f"未找到产物: {kind}"}

        path = str(Path(target).resolve())
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": path}

    # ------------------------------------------------------------------ helpers
    def _resolve_run_dir(self, run_id: str) -> Optional[Path]:
        if not run_id:
            return None
        meta = get_run(run_id)
        if meta and meta.get("rel_path"):
            p = settings.data_path() / str(meta["rel_path"])
            if p.is_dir():
                return p
        direct = settings.runs_root() / run_id
        if direct.is_dir():
            return direct
        return None

    def _artifact_map(self, run_dir: Path) -> Dict[str, str]:
        out: Dict[str, str] = {"run_dir": str(run_dir)}
        sources = run_dir / "sources.html"
        if sources.exists():
            out["sources"] = str(sources)
        else:
            alts = sorted(run_dir.glob("sources_*.html"))
            if alts:
                out["sources"] = str(alts[0])
        xlsx = sorted(run_dir.glob("*.xlsx"))
        if xlsx:
            out["excel"] = str(xlsx[0])
        votes = run_dir / "votes.json"
        if votes.exists():
            out["votes"] = str(votes)
        # Prefer path recorded in steps.json
        steps_path = run_dir / "steps.json"
        if steps_path.exists():
            try:
                steps = json.loads(steps_path.read_text(encoding="utf-8"))
                for st in steps:
                    arts = st.get("artifacts") or {}
                    if arts.get("excel") and Path(arts["excel"]).exists():
                        out["excel"] = str(arts["excel"])
                    if arts.get("sources.html") and Path(arts["sources.html"]).exists():
                        out["sources"] = str(arts["sources.html"])
            except Exception:
                pass
        return out


__all__ = ["GuiApi", "STAGE_LABELS", "stages_from"]

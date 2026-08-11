"""Human-readable sources audit page after Collect."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List


def _esc(s: Any) -> str:
    return html.escape(str(s or ""))


def render_collect_sources_html(manifest: Dict[str, Any]) -> str:
    devices: List[Dict[str, Any]] = manifest.get("devices") or []
    run_id = manifest.get("run_id", "")
    category = manifest.get("category", "")
    date_start = manifest.get("date_start", "")
    date_end = manifest.get("date_end", "")

    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        f"<title>信源审核 — { _esc(category) } { _esc(date_start)}~{ _esc(date_end)}</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;margin:24px;line-height:1.5}",
        "h1{font-size:1.25rem} .dev{border:1px solid #ddd;border-radius:8px;margin:16px 0;padding:12px}",
        ".url{font-size:0.9rem;margin:6px 0;padding:6px;background:#f8f8f8;border-radius:4px}",
        ".ok{color:#0a0}.fail{color:#a00}.mdonly{color:#886600}",
        "a{color:#0366d6;word-break:break-all}",
        "</style></head><body>",
        f"<h1>Collect 信源审核</h1>",
        f"<p>run_id={_esc(run_id)} · 设备 {len(devices)} 台 · llm-wiki/raw 已镜像</p>",
    ]

    for dev in devices:
        brand = dev.get("brand", "")
        model = dev.get("model", "")
        did = dev.get("device_id", "")
        sources = dev.get("sources") or []
        ok = sum(1 for s in sources if s.get("raw_status") in ("ok", "markdown_only"))
        parts.append(
            f"<section class='dev'><h2>{_esc(brand)} {_esc(model)}"
            f" <small>({ok}/{len(sources)} 成功)</small></h2>"
            f"<p><code>{_esc(did)}</code></p>"
        )
        for s in sources:
            st = s.get("raw_status", "failed")
            cls = "ok" if st == "ok" else ("mdonly" if st == "markdown_only" else "fail")
            wiki = s.get("wiki_path", "")
            parts.append(
                f"<div class='url {cls}'>"
                f"<div><strong>{_esc(s.get('link_role',''))}</strong> · "
                f"{_esc(s.get('tier',''))} · { _esc(st)} · {_esc(s.get('fetch_method',''))}</div>"
                f"<div><a href='{_esc(s.get('url',''))}' target='_blank' rel='noopener'>"
                f"{_esc(s.get('url',''))}</a></div>"
            )
            if wiki:
                parts.append(f"<div><small>wiki: {_esc(wiki)}</small></div>")
            if s.get("error"):
                parts.append(f"<div><small>{_esc(s.get('error'))}</small></div>")
            parts.append("</div>")
        parts.append("</section>")

    parts.append("</body></html>")
    return "\n".join(parts)


def write_collect_sources_html(manifest: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_collect_sources_html(manifest), encoding="utf-8")

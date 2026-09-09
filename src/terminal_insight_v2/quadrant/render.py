"""Render quadrant.html as a self-contained research view."""
from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, List

from .models import QuadrantArtifact, QuadrantPoint


_BAND_COLORS = {
    "入门": "#6b7a8d",
    "中端": "#0f6b6b",
    "中高端": "#1d4ed8",
    "旗舰": "#9a3412",
    "": "#8a8176",
}


def _points_payload(points: List[QuadrantPoint]) -> List[Dict[str, Any]]:
    return [p.model_dump() for p in points]


def render_quadrant_html(artifact: QuadrantArtifact) -> str:
    payload = {
        "run_id": artifact.run_id,
        "category": artifact.category,
        "slice_note": artifact.slice_note,
        "axes": artifact.axes,
        "origin": artifact.origin.model_dump() if artifact.origin else None,
        "points": _points_payload(artifact.points),
        "points_watt": _points_payload(artifact.points_watt),
        "skipped": [s.model_dump() for s in artifact.skipped],
        "quadrant_labels": artifact.quadrant_labels,
        "band_colors": _BAND_COLORS,
    }
    data_json = json.dumps(payload, ensure_ascii=False)
    title = escape(f"机型四象限 · {artifact.run_id}")
    note = escape(artifact.slice_note)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
  :root {{
    --paper: #f6f1e8;
    --ink: #1c1916;
    --soft: #4a453e;
    --muted: #8a8176;
    --line: rgba(28,25,22,.12);
    --teal: #0e5854;
    --card: #fff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Noto Sans SC", "PingFang SC", sans-serif;
    background: #12141a;
    color: var(--ink);
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 20px;
  }}
  .board {{
    width: min(96vw, 1280px);
    aspect-ratio: 16 / 9;
    background: var(--paper);
    border-radius: 8px;
    box-shadow: 0 24px 80px rgba(0,0,0,.45);
    display: grid;
    grid-template-columns: 1fr 280px;
    overflow: hidden;
  }}
  .main {{ padding: 22px 24px 18px; display: flex; flex-direction: column; min-width: 0; }}
  .kicker {{ font-size: 11px; letter-spacing: .18em; color: var(--teal); font-weight: 700; }}
  h1 {{ font-size: 22px; margin: 6px 0 4px; font-family: "Noto Serif SC", serif; }}
  .lede {{ font-size: 13px; color: var(--soft); margin-bottom: 10px; }}
  .toolbar {{ display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }}
  .toolbar button {{
    border: 1px solid var(--line); background: #fff; border-radius: 999px;
    padding: 5px 12px; font: inherit; font-size: 12px; cursor: pointer; color: var(--soft);
  }}
  .toolbar button.on {{ background: var(--teal); color: #fff; border-color: var(--teal); }}
  .chart-wrap {{ flex: 1; min-height: 0; position: relative; background: #fff; border-radius: 6px; border: 1px solid var(--line); }}
  svg {{ width: 100%; height: 100%; display: block; }}
  .side {{
    background: #efe8dc; padding: 18px 16px; border-left: 1px solid var(--line);
    overflow: auto; font-size: 12px; color: var(--soft);
  }}
  .side h2 {{ font-size: 13px; color: var(--ink); margin: 12px 0 6px; }}
  .side h2:first-child {{ margin-top: 0; }}
  .legend-row {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .ring {{ width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--teal); background: transparent; }}
  .skip {{ margin: 3px 0; line-height: 1.4; }}
  .meta {{ font-size: 11px; color: var(--muted); margin-top: auto; padding-top: 10px; }}
  text.label {{ font-size: 11px; fill: var(--soft); }}
  text.axis {{ font-size: 12px; fill: var(--ink); font-weight: 600; }}
  text.q {{ font-size: 11px; fill: var(--muted); }}
</style>
</head>
<body>
  <div class="board">
    <div class="main">
      <div class="kicker">RESEARCH · QUADRANT</div>
      <h1>机型四象限</h1>
      <p class="lede">{note}</p>
      <div class="toolbar">
        <span style="font-size:12px;color:var(--muted)">纵轴</span>
        <button type="button" id="btnMah" class="on">电池 mAh</button>
        <button type="button" id="btnWatt">充电 W</button>
        <span id="stats" style="margin-left:auto;font-size:12px;color:var(--muted)"></span>
      </div>
      <div class="chart-wrap"><svg id="chart" viewBox="0 0 900 520" preserveAspectRatio="xMidYMid meet"></svg></div>
    </div>
    <aside class="side">
      <h2>价位带</h2>
      <div id="legendBands"></div>
      <h2>Vote 提名</h2>
      <div class="legend-row"><span class="ring"></span><span>被 AAA–FFF 提名（空心圈）</span></div>
      <h2>原点</h2>
      <p id="originText">本窗口落点中位数</p>
      <h2>未落点</h2>
      <div id="skipped"></div>
      <p class="meta" id="runMeta"></p>
    </aside>
  </div>
<script>
const DATA = {data_json};
const svg = document.getElementById('chart');
const NS = 'http://www.w3.org/2000/svg';
let mode = 'mah';

function el(name, attrs, text) {{
  const n = document.createElementNS(NS, name);
  for (const [k,v] of Object.entries(attrs || {{}})) n.setAttribute(k, v);
  if (text != null) n.textContent = text;
  return n;
}}

function activePoints() {{
  return mode === 'watt' ? (DATA.points_watt || []) : (DATA.points || []);
}}

function renderLegend() {{
  const box = document.getElementById('legendBands');
  box.innerHTML = '';
  const colors = DATA.band_colors || {{}};
  for (const [k,c] of Object.entries(colors)) {{
    if (!k) continue;
    const row = document.createElement('div');
    row.className = 'legend-row';
    row.innerHTML = `<span class="dot" style="background:${{c}}"></span><span>${{k}}</span>`;
    box.appendChild(row);
  }}
  const sk = document.getElementById('skipped');
  sk.innerHTML = '';
  const list = mode === 'watt'
    ? (DATA.points_watt || []).length === 0 && (DATA.skipped || [])
    : (DATA.skipped || []);
  // Always show mah skipped for default; for watt show devices missing watt among those with price
  let skipped = DATA.skipped || [];
  if (mode === 'watt') {{
    const have = new Set((DATA.points_watt || []).map(p => p.device_id));
    const priced = new Set((DATA.points || []).map(p => p.device_id));
    // rebuild: devices in mah points but not watt
    skipped = (DATA.points || []).filter(p => !have.has(p.device_id)).map(p => ({{
      device_id: p.device_id, brand: p.brand, model: p.model, reason: '缺充电功率'
    }}));
    skipped = skipped.concat((DATA.skipped || []).filter(s => s.reason === '缺价' || s.reason.includes('缺价')));
  }}
  if (!skipped.length) {{
    sk.innerHTML = '<div class="skip">无</div>';
  }} else {{
    for (const s of skipped.slice(0, 40)) {{
      const d = document.createElement('div');
      d.className = 'skip';
      d.textContent = `${{s.brand}} ${{s.model}} — ${{s.reason}}`;
      sk.appendChild(d);
    }}
  }}
  document.getElementById('runMeta').textContent = DATA.run_id || '';
}}

function draw() {{
  const pts = activePoints();
  svg.innerHTML = '';
  const W = 900, H = 520, pad = {{l:70, r:24, t:24, b:54}};
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
  document.getElementById('stats').textContent = `落点 ${{pts.length}} · 提名 ${{pts.filter(p=>p.nominated_by && p.nominated_by.length).length}}`;

  if (!pts.length) {{
    svg.appendChild(el('text', {{x: W/2, y: H/2, 'text-anchor':'middle', class:'axis'}}, '无可落点机型（缺价或缺纵轴指标）'));
    renderLegend();
    return;
  }}

  const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  let x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (x0 === x1) {{ x0 *= 0.9; x1 *= 1.1; if (x0 === 0) {{ x0 = -1; x1 = 1; }} }}
  if (y0 === y1) {{ y0 *= 0.9; y1 *= 1.1; if (y0 === 0) {{ y0 = -1; y1 = 1; }} }}
  const xpad = (x1 - x0) * 0.08, ypad = (y1 - y0) * 0.08;
  x0 -= xpad; x1 += xpad; y0 -= ypad; y1 += ypad;

  const ox = (DATA.origin && mode === 'mah') ? DATA.origin.x_median : median(xs);
  const oy = (DATA.origin && mode === 'mah') ? DATA.origin.y_median : median(ys);
  document.getElementById('originText').textContent =
    `中位数 · 价 ${{Math.round(ox)}} 元 × ${{mode === 'watt' ? '充电' : '电池'}} ${{Math.round(oy)}}`;

  const sx = v => pad.l + (v - x0) / (x1 - x0) * iw;
  const sy = v => pad.t + (1 - (v - y0) / (y1 - y0)) * ih;

  // quadrant labels
  const labels = DATA.quadrant_labels || {{}};
  const yName = mode === 'watt' ? '充电' : '电池';
  const ql = [
    [sx((ox+x1)/2), sy((oy+y1)/2), labels.high_x_high_y || ('高价高'+yName)],
    [sx((x0+ox)/2), sy((oy+y1)/2), labels.low_x_high_y || ('低价高'+yName)],
    [sx((x0+ox)/2), sy((y0+oy)/2), labels.low_x_low_y || ('低价低'+yName)],
    [sx((ox+x1)/2), sy((y0+oy)/2), labels.high_x_low_y || ('高价低'+yName)],
  ];
  for (const [x,y,t] of ql) {{
    svg.appendChild(el('text', {{x, y, 'text-anchor':'middle', class:'q'}}, t));
  }}

  // median cross
  svg.appendChild(el('line', {{x1:sx(ox), y1:pad.t, x2:sx(ox), y2:pad.t+ih, stroke:'#0e5854', 'stroke-width':1.2, 'stroke-dasharray':'4 4', opacity:.7}}));
  svg.appendChild(el('line', {{x1:pad.l, y1:sy(oy), x2:pad.l+iw, y2:sy(oy), stroke:'#0e5854', 'stroke-width':1.2, 'stroke-dasharray':'4 4', opacity:.7}}));

  // axes
  svg.appendChild(el('line', {{x1:pad.l, y1:pad.t+ih, x2:pad.l+iw, y2:pad.t+ih, stroke:'#1c1916', 'stroke-width':1.2}}));
  svg.appendChild(el('line', {{x1:pad.l, y1:pad.t, x2:pad.l, y2:pad.t+ih, stroke:'#1c1916', 'stroke-width':1.2}}));
  svg.appendChild(el('text', {{x: pad.l+iw/2, y: H-14, 'text-anchor':'middle', class:'axis'}}, '起售价（元）'));
  svg.appendChild(el('text', {{x: 18, y: pad.t+ih/2, 'text-anchor':'middle', class:'axis', transform:`rotate(-90 18 ${{pad.t+ih/2}})`}}, mode==='watt' ? '充电功率（W）' : '电池容量（mAh）'));

  const colors = DATA.band_colors || {{}};
  for (const p of pts) {{
    const cx = sx(p.x), cy = sy(p.y);
    const fill = colors[p.price_band || ''] || colors[''] || '#8a8176';
    svg.appendChild(el('circle', {{cx, cy, r: 5.5, fill, opacity: .9}}));
    if (p.nominated_by && p.nominated_by.length) {{
      svg.appendChild(el('circle', {{cx, cy, r: 10, fill: 'none', stroke: '#0e5854', 'stroke-width': 2}}));
    }}
    const label = (p.model || p.brand || '').slice(0, 14);
    svg.appendChild(el('text', {{x: cx+8, y: cy+3, class:'label'}}, label));
  }}
  renderLegend();
}}

function median(arr) {{
  const a = [...arr].sort((x,y)=>x-y);
  const m = Math.floor(a.length/2);
  return a.length % 2 ? a[m] : (a[m-1]+a[m])/2;
}}

document.getElementById('btnMah').onclick = () => {{
  mode = 'mah';
  document.getElementById('btnMah').classList.add('on');
  document.getElementById('btnWatt').classList.remove('on');
  draw();
}};
document.getElementById('btnWatt').onclick = () => {{
  mode = 'watt';
  document.getElementById('btnWatt').classList.add('on');
  document.getElementById('btnMah').classList.remove('on');
  draw();
}};
draw();
</script>
</body>
</html>
"""


def write_quadrant_html(path, artifact: QuadrantArtifact) -> None:
    path.write_text(render_quadrant_html(artifact), encoding="utf-8")

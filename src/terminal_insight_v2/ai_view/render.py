"""Render ai_quadrant.html — price × AI capability stage scatter."""
from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, List

from .models import AIQuadrantArtifact, AIQuadrantPoint

_BAND_COLORS = {
    "入门": "#6b7a8d",
    "中端": "#0f6b6b",
    "中高端": "#1d4ed8",
    "旗舰": "#9a3412",
    "": "#8a8176",
}

_STAGE_COLORS = {
    "单点AI辅助": "#94a3b8",
    "感知与理解": "#0ea5e9",
    "长期记忆": "#8b5cf6",
    "Agent执行": "#f59e0b",
    "安全与服务": "#10b981",
}


def _pts(points: List[AIQuadrantPoint]) -> List[Dict[str, Any]]:
    return [p.model_dump() for p in points]


def render_ai_quadrant_html(artifact: AIQuadrantArtifact) -> str:
    payload = {
        "run_id": artifact.run_id,
        "category": artifact.category,
        "stage_ladder": artifact.stage_ladder,
        "points": _pts(artifact.points),
        "unassessed": [c.model_dump() for c in artifact.unassessed],
        "skipped_no_price": [c.model_dump() for c in artifact.skipped_no_price],
        "stage_counts": artifact.stage_counts,
        "origin_x_median": artifact.origin_x_median,
        "band_colors": _BAND_COLORS,
        "stage_colors": _STAGE_COLORS,
    }
    data_json = json.dumps(payload, ensure_ascii=False)
    title = escape(f"AI 能力象限 · {artifact.run_id}")
    cat_label = {"phone": "手机", "watch": "手表", "glasses": "眼镜"}.get(
        artifact.category, artifact.category
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
  :root {{
    --paper: #f6f1e8; --ink: #1c1916; --soft: #4a453e; --muted: #8a8176;
    --line: rgba(28,25,22,.12); --teal: #0e5854; --card: #fff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Noto Sans SC", "PingFang SC", sans-serif;
    background: #12141a; color: var(--ink); min-height: 100vh;
    display: grid; place-items: center; padding: 20px;
  }}
  .board {{
    width: min(96vw, 1280px); aspect-ratio: 16/9; background: var(--paper);
    border-radius: 8px; box-shadow: 0 24px 80px rgba(0,0,0,.45);
    display: grid; grid-template-columns: 1fr 280px; overflow: hidden;
  }}
  .main {{ padding: 22px 24px 18px; display: flex; flex-direction: column; min-width: 0; }}
  .kicker {{ font-size: 11px; letter-spacing: .18em; color: var(--teal); font-weight: 700; }}
  h1 {{ font-size: 22px; margin: 6px 0 4px; font-family: "Noto Serif SC", serif; }}
  .lede {{ font-size: 13px; color: var(--soft); margin-bottom: 10px; }}
  .chart-wrap {{ flex: 1; min-height: 0; position: relative; background: #fff;
    border-radius: 6px; border: 1px solid var(--line); }}
  svg {{ width: 100%; height: 100%; display: block; }}
  .side {{ background: #efe8dc; padding: 18px 16px; border-left: 1px solid var(--line);
    overflow: auto; font-size: 12px; color: var(--soft); }}
  .side h2 {{ font-size: 13px; color: var(--ink); margin: 12px 0 6px; }}
  .side h2:first-child {{ margin-top: 0; }}
  .legend-row {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .ring {{ width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--teal);
    background: transparent; }}
  .skip {{ margin: 3px 0; line-height: 1.4; }}
  .meta {{ font-size: 11px; color: var(--muted); margin-top: auto; padding-top: 10px; }}
  text.label {{ font-size: 11px; fill: var(--soft); }}
  text.axis {{ font-size: 12px; fill: var(--ink); font-weight: 600; }}
  text.stage {{ font-size: 11px; fill: var(--muted); }}
  .count {{ font-size: 11px; color: var(--muted); margin-left: auto; }}
</style>
</head>
<body>
  <div class="board">
    <div class="main">
      <div class="kicker">RESEARCH · AI CAPABILITY</div>
      <h1>AI 能力象限 · {escape(cat_label)}</h1>
      <p class="lede">横轴 = 起售价（元），纵轴 = AI 最高能力阶段。颜色 = 价位带，空心圈 = Vote 提名。</p>
      <div class="chart-wrap"><svg id="chart" viewBox="0 0 900 520" preserveAspectRatio="xMidYMid meet"></svg></div>
    </div>
    <aside class="side">
      <h2>能力阶段分布</h2>
      <div id="stageCounts"></div>
      <h2>价位带</h2>
      <div id="legendBands"></div>
      <h2>Vote 提名</h2>
      <div class="legend-row"><span class="ring"></span><span>被 AAA–FFF 提名（空心圈）</span></div>
      <h2>未评估（待判断）</h2>
      <div id="unassessed"></div>
      <h2>缺价</h2>
      <div id="noPrice"></div>
      <p class="meta" id="runMeta"></p>
    </aside>
  </div>
<script>
const DATA = {data_json};
const svg = document.getElementById('chart');
const NS = 'http://www.w3.org/2000/svg';

function el(name, attrs, text) {{
  const n = document.createElementNS(NS, name);
  for (const [k,v] of Object.entries(attrs || {{}})) n.setAttribute(k, v);
  if (text != null) n.textContent = text;
  return n;
}}

function renderSide() {{
  const sc = document.getElementById('stageCounts');
  sc.innerHTML = '';
  const ladder = DATA.stage_ladder || [];
  const counts = DATA.stage_counts || {{}};
  const colors = DATA.stage_colors || {{}};
  for (const s of ladder) {{
    const row = document.createElement('div');
    row.className = 'legend-row';
    row.innerHTML = `<span class="dot" style="background:${{colors[s]||'#8a8176'}}"></span>` +
      `<span>${{s}}</span><span class="count">${{counts[s]||0}}</span>`;
    sc.appendChild(row);
  }}
  const lb = document.getElementById('legendBands');
  lb.innerHTML = '';
  for (const [k,c] of Object.entries(DATA.band_colors || {{}})) {{
    if (!k) continue;
    const row = document.createElement('div');
    row.className = 'legend-row';
    row.innerHTML = `<span class="dot" style="background:${{c}}"></span><span>${{k}}</span>`;
    lb.appendChild(row);
  }}
  const ua = document.getElementById('unassessed');
  ua.innerHTML = '';
  const uaList = DATA.unassessed || [];
  if (!uaList.length) {{
    ua.innerHTML = '<div class="skip">无</div>';
  }} else {{
    for (const c of uaList.slice(0, 30)) {{
      const d = document.createElement('div');
      d.className = 'skip';
      d.textContent = `${{c.brand}} ${{c.model}}`;
      ua.appendChild(d);
    }}
    if (uaList.length > 30) {{
      const d = document.createElement('div');
      d.className = 'skip';
      d.textContent = `…共 ${{uaList.length}} 台`;
      ua.appendChild(d);
    }}
  }}
  const np = document.getElementById('noPrice');
  np.innerHTML = '';
  const npList = DATA.skipped_no_price || [];
  if (!npList.length) {{
    np.innerHTML = '<div class="skip">无</div>';
  }} else {{
    for (const c of npList.slice(0, 20)) {{
      const d = document.createElement('div');
      d.className = 'skip';
      d.textContent = `${{c.brand}} ${{c.model}}`;
      np.appendChild(d);
    }}
  }}
  document.getElementById('runMeta').textContent = DATA.run_id || '';
}}

function draw() {{
  const pts = DATA.points || [];
  svg.innerHTML = '';
  const W = 900, H = 520, pad = {{l:70, r:24, t:24, b:54}};
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;

  if (!pts.length) {{
    svg.appendChild(el('text', {{x:W/2, y:H/2, 'text-anchor':'middle', class:'axis'}},
      '无可落点机型（全部待判断或缺价）'));
    renderSide();
    return;
  }}

  const ladder = DATA.stage_ladder || [];
  const nStages = ladder.length;
  const xs = pts.map(p => p.x);
  let x0 = Math.min(...xs), x1 = Math.max(...xs);
  if (x0 === x1) {{ x0 *= 0.9; x1 *= 1.1; if (x0===0) {{ x0=-1; x1=1; }} }}
  const xpad = (x1 - x0) * 0.08;
  x0 -= xpad; x1 += xpad;

  const sx = v => pad.l + (v - x0) / (x1 - x0) * iw;
  const sy = v => pad.t + (1 - (v - 0.5) / nStages) * ih;

  // horizontal band per stage
  const bandH = ih / nStages;
  for (let i = 0; i < nStages; i++) {{
    const y = pad.t + i * bandH;
    if (i % 2 === 0) {{
      svg.appendChild(el('rect', {{x:pad.l, y, width:iw, height:bandH,
        fill:'rgba(14,88,84,.04)'}}));
    }}
    svg.appendChild(el('line', {{x1:pad.l, y1:y, x2:pad.l+iw, y2:y,
      stroke:'rgba(28,25,22,.08)', 'stroke-width':1}}));
    const label = ladder[nStages - 1 - i];
    svg.appendChild(el('text', {{x:pad.l-8, y:y+bandH/2+4, 'text-anchor':'end',
      class:'stage'}}, label));
  }}

  // median price line
  const ox = DATA.origin_x_median;
  if (ox != null) {{
    svg.appendChild(el('line', {{x1:sx(ox), y1:pad.t, x2:sx(ox), y2:pad.t+ih,
      stroke:'#0e5854', 'stroke-width':1.2, 'stroke-dasharray':'4 4', opacity:.7}}));
  }}

  // axes
  svg.appendChild(el('line', {{x1:pad.l, y1:pad.t+ih, x2:pad.l+iw, y2:pad.t+ih,
    stroke:'#1c1916', 'stroke-width':1.2}}));
  svg.appendChild(el('line', {{x1:pad.l, y1:pad.t, x2:pad.l, y2:pad.t+ih,
    stroke:'#1c1916', 'stroke-width':1.2}}));
  svg.appendChild(el('text', {{x:pad.l+iw/2, y:H-14, 'text-anchor':'middle', class:'axis'}},
    '起售价（元）'));
  svg.appendChild(el('text', {{x:18, y:pad.t+ih/2, 'text-anchor':'middle', class:'axis',
    transform:`rotate(-90 18 ${{pad.t+ih/2}})`}}, 'AI 最高能力阶段'));

  // jitter within stage band to avoid overlap
  const byStage = {{}};
  for (const p of pts) {{
    const k = p.y;
    if (!byStage[k]) byStage[k] = [];
    byStage[k].push(p);
  }}
  const colors = DATA.band_colors || {{}};
  for (const [stageY, group] of Object.entries(byStage)) {{
    const yBase = sy(parseFloat(stageY));
    group.sort((a,b) => a.x - b.x);
    for (let i = 0; i < group.length; i++) {{
      const p = group[i];
      const jitter = (i - (group.length-1)/2) * Math.min(14, bandH*0.6/Math.max(group.length,1));
      const cx = sx(p.x), cy = yBase + jitter;
      const fill = colors[p.price_band || ''] || colors[''] || '#8a8176';
      svg.appendChild(el('circle', {{cx, cy, r:5.5, fill, opacity:.9}}));
      if (p.nominated_by && p.nominated_by.length) {{
        svg.appendChild(el('circle', {{cx, cy, r:10, fill:'none', stroke:'#0e5854',
          'stroke-width':2}}));
      }}
      const label = (p.model || p.brand || '').slice(0, 14);
      svg.appendChild(el('text', {{x:cx+8, y:cy+3, class:'label'}}, label));
    }}
  }}
  renderSide();
}}

draw();
</script>
</body>
</html>
"""


def write_ai_quadrant_html(path, artifact: AIQuadrantArtifact) -> None:
    path.write_text(render_ai_quadrant_html(artifact), encoding="utf-8")

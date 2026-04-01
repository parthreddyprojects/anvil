#!/usr/bin/env python3
"""
Generate standalone one-pager HTML + appendix slides for PSU problem statements.
Appendix uses Slot A/B/D (crisis brief). Slot C inactive.

Usage:
    python gen_onepager_appendix.py                    # PS3 + PS4
    python gen_onepager_appendix.py --ps iocl_hmel     # just one
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import html as h
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent
OUTPUTS = ROOT.parent / "outputs"
REPORT_DIR = OUTPUTS / "reports"
HYP_DIR = OUTPUTS / "hypothesis_trees"
WD_DIR = OUTPUTS / "working_docs"

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384

PS_MAP = {
    "iocl_hmel": {"name": "IOCL & HMEL", "source_ps": "ps2"},
    "lownci_psu": {"name": "Low-Complexity PSU Refiners", "source_ps": "ps3"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_client():
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        for p in [ROOT.parent / ".env", ROOT.parent.parent / "iran-crisis-v2" / ".env"]:
            if p.exists():
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            if api_key:
                break
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(msg):
    line = f"[{ts()}] {msg}"
    print(line, flush=True)


def llm_json(client, system, user):
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Step 1: LLM maps one-pager claims to appendix slides
# ---------------------------------------------------------------------------

CHART_TYPES = {
    "waterfall": "bar",       # stacked horizontal or vertical bar for waterfall
    "variance_table": "bar",  # grouped bar for variance
    "benchmark_table": "bar", # horizontal bar for comparison
    "timeline": "bar",        # horizontal Gantt-style
    "scenario_model": "bar",  # grouped bars for scenarios
    "causal_chain": "bar",    # stepped bar
    "containment_playbook": None,  # no chart — timeline list
}


def build_chart_js(slide, canvas_id):
    """Generate Chart.js code for a slide based on proof_type and proof_content."""
    proof = slide.get("proof_content", {})
    ptype = slide.get("proof_type", "")
    rows = proof.get("rows", proof.get("steps", []))

    if not rows or not isinstance(rows, list):
        return ""

    # Extract labels and values from rows
    labels = []
    values = []
    colors = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = row.get("label", row.get("item", row.get("step", row.get("event", ""))))
        val = row.get("value", row.get("amount", row.get("derivation", "")))

        # Try to extract a number from the value
        import re
        nums = re.findall(r'[\d,]+(?:\.\d+)?', str(val).replace(',', ''))
        num = float(nums[0]) if nums else 0

        # Truncate label
        if len(str(label)) > 40:
            label = str(label)[:37] + "..."

        labels.append(str(label))
        values.append(num)

        # Color based on confidence or positive/negative
        conf = str(row.get("confidence", row.get("note", ""))).lower()
        if "high" in conf:
            colors.append("#16a34a")
        elif "low" in conf or "data gap" in conf:
            colors.append("#dc2626")
        elif num < 0:
            colors.append("#dc2626")
        else:
            colors.append("#2563eb")

    if not any(v != 0 for v in values):
        return ""

    is_horizontal = ptype in ("benchmark_table", "timeline") or len(labels) > 4

    axis_config = """
        indexAxis: 'y',
        """ if is_horizontal else ""

    return f"""
(function(){{
  var ctx = document.getElementById('{canvas_id}');
  if(!ctx) return;
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {json.dumps(labels)},
      datasets: [{{
        data: {json.dumps(values)},
        backgroundColor: {json.dumps(colors)},
        borderRadius: 4,
        barThickness: {20 if is_horizontal else 28}
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      {axis_config}
      plugins: {{
        legend: {{ display: false }},
      }},
      scales: {{
        x: {{ ticks: {{ color: '#888', font: {{ family: 'Inter', size: 10 }} }}, grid: {{ color: 'rgba(0,0,0,.05)' }} }},
        y: {{ ticks: {{ color: '#555', font: {{ family: 'Inter', size: 10 }} }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}})();
"""


import json as json_mod


APPENDIX_MAP_SYSTEM = """You are a McKinsey senior partner mapping a one-pager's claims to appendix proof slides.

RULES:
1. This is a CRISIS brief. Active slots: A (prove numbers), B (prove claims/findings), D (prove asks are executable via containment playbook). Slot C is INACTIVE.
2. Every claim on the one-pager that needs defending gets exactly one appendix slide. Every slide maps back to exactly one claim. Both directions must hold.
3. Only pick the claims that ACTUALLY NEED PROVING. Skip self-evident facts. Target 4-6 slides total -- the most important ones only.
4. Sequence: all Slot A first (by materiality), then Slot B, then Slot D.
5. Number continuously: Appendix 1, Appendix 2, etc.

For each slide, specify:
- slot_type: A, B, or D
- claim: the exact sentence from the one-pager this proves
- claim_section: which one-pager section (performance_data / analysis / decisions)
- action_title: conclusion in 8-12 words (NOT a topic label -- an assertion)
- subtitle: units, time period, source
- proof_type: what format proves this best (waterfall / variance_table / benchmark_table / scenario_model / causal_chain / timeline / containment_playbook)
- proof_content: the actual data/evidence to put on the slide, pulled from the hypothesis tree and working document. Be specific -- actual numbers, sources, derivations.
- source_line: chain of custody for the data

Return JSON:
{
  "slides": [
    {
      "appendix_num": 1,
      "slot_type": "A",
      "claim": "exact sentence from one-pager",
      "claim_section": "performance_data",
      "action_title": "8-12 word conclusion",
      "subtitle": "units, period, source",
      "proof_type": "waterfall",
      "proof_content": {"rows": [...]},
      "source_line": "chain of custody"
    }
  ]
}
JSON only."""


def map_claims_to_slides(client, ps_key, one_pager, hyp_tree, working_doc):
    log(f"  [{ps_key}] Mapping claims to appendix slides...")

    user = f"""ONE-PAGER:
{json.dumps(one_pager, indent=2, ensure_ascii=False)}

HYPOTHESIS TREE:
{json.dumps(hyp_tree, indent=2, ensure_ascii=False)}

WORKING DOCUMENT (evidence base):
{working_doc[:40000]}

Map the most important claims to 4-6 appendix slides. Crisis brief -- slots A, B, D only. Pick only what needs proving."""

    return llm_json(client, APPENDIX_MAP_SYSTEM, user)


# ---------------------------------------------------------------------------
# Step 2: Render one-pager HTML
# ---------------------------------------------------------------------------

def render_onepager_html(ps_key, config, one_pager):
    e = h.escape
    name = e(config["name"])

    kpis = ""
    for k in one_pager.get("performance_data", []):
        kpis += f'''<tr>
<td class="kpi-name">{e(k.get("kpi",""))}</td>
<td class="kpi-val">{e(str(k.get("value","")))}</td>
<td class="kpi-var">{e(k.get("variance",""))}</td>
</tr>\n'''

    analysis = ""
    for i, a in enumerate(one_pager.get("analysis", []), 1):
        analysis += f'''<div class="finding">
<div class="f-num">{i}</div>
<div><strong>{e(a.get("finding",""))}</strong><br>
<span class="f-impact">{e(a.get("impact",""))}</span><br>
<em class="f-sowhat">{e(a.get("so_what",""))}</em></div>
</div>\n'''

    decisions = ""
    for d in one_pager.get("decisions", []):
        owner = d.get("owner", "")
        deadline = d.get("deadline", "")
        meta = ""
        if owner or deadline:
            parts = []
            if owner:
                parts.append(f"Owner: {e(owner)}")
            if deadline:
                parts.append(f"Deadline: {e(deadline)}")
            meta = f'<div class="d-meta">{" | ".join(parts)}</div>'
        decisions += f'''<div class="decision">
<div class="d-num">{d.get("number","")}</div>
<div><div class="d-ask">{e(d.get("ask",""))}</div>{meta}</div>
</div>\n'''

    data_gaps = ""
    for g in one_pager.get("data_required_before_signoff", []):
        data_gaps += f'<div class="dg"><strong>{e(g.get("item",""))}</strong> -- {e(g.get("owner","TBD"))} by {e(g.get("deadline","ASAP"))}. Blocks: {e(g.get("blocks",""))}</div>\n'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} -- One-Pager</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;max-width:800px;margin:0 auto;padding:40px 32px 60px;color:#1a1a1a;background:#fff}}
.tabs{{display:flex;gap:0;margin-bottom:28px;border-bottom:2px solid #e5e7eb}}
.tab{{font:600 13px/1 'Inter';padding:10px 20px;color:#888;text-decoration:none;border-bottom:2px solid transparent;margin-bottom:-2px}}
.tab:hover{{color:#1a1a1a}}
.tab.active{{color:#2563eb;border-bottom-color:#2563eb}}
.condensed-ps{{font:400 13px/1.6 'Inter';color:#555;margin-bottom:24px;padding:14px 18px;background:#f8fafc;border-radius:6px}}
.header{{font:900 24px/1.2 'Inter';margin-bottom:24px;padding-bottom:16px;border-bottom:3px solid #1a1a1a}}
.section-label{{font:700 10px/1 'JetBrains Mono';letter-spacing:2px;text-transform:uppercase;color:#888;margin:24px 0 10px}}
.situation{{font:400 14px/1.7 'Inter';color:#333;margin-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin:8px 0 16px}}
th{{font:600 10px/1 'JetBrains Mono';text-transform:uppercase;letter-spacing:1px;color:#888;text-align:left;padding:8px 10px;border-bottom:2px solid #1a1a1a}}
td{{font:400 13px/1.5 'Inter';padding:8px 10px;border-bottom:1px solid #eee}}
.kpi-name{{color:#555;width:35%}}
.kpi-val{{font:700 14px/1 'JetBrains Mono';color:#1a1a1a;width:25%}}
.kpi-var{{font:400 12px/1.4 'Inter';color:#888}}
.finding{{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid #f0f0f0}}
.f-num{{font:800 20px/1 'JetBrains Mono';color:#2563eb;min-width:24px}}
.f-impact{{font:500 12px/1.4 'JetBrains Mono';color:#dc2626}}
.f-sowhat{{font:400 12px/1.4 'Inter';color:#555}}
.decision{{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid #f0f0f0}}
.d-num{{font:800 24px/1 'JetBrains Mono';color:#dc2626;min-width:30px}}
.d-ask{{font:500 13px/1.5 'Inter'}}
.d-meta{{font:400 11px/1.4 'JetBrains Mono';color:#888;margin-top:4px}}
.dg{{font:400 12px/1.5 'Inter';color:#991b1b;padding:8px 12px;background:#fef2f2;border-left:3px solid #dc2626;border-radius:0 4px 4px 0;margin:4px 0}}
.foot{{font:400 11px/1.5 'Inter';color:#aaa;text-align:center;margin-top:40px;padding-top:16px;border-top:1px solid #eee}}
</style>
</head>
<body>

<div class="tabs">
<a class="tab active" href="onepager.html">One-Pager</a>
<a class="tab" href="appendix.html">Appendix</a>
<a class="tab" href="report.html">Full Report</a>
</div>

<div class="condensed-ps">{e(one_pager.get("condensed_ps",""))}</div>

<div class="header">{e(one_pager.get("header",""))}</div>

<div class="section-label">Situation</div>
<p class="situation">{e(one_pager.get("situation",""))}</p>

<div class="section-label">Performance Data</div>
<table>
<tr><th>KPI</th><th>Value</th><th>Variance</th></tr>
{kpis}
</table>

<div class="section-label">Analysis</div>
{analysis}

<div class="section-label">Decision Required</div>
{decisions}

{f'<div class="section-label">Data Required Before Sign-Off</div>{data_gaps}' if data_gaps else ''}

<div class="foot">Developed by Parth Reddy</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# Step 3: Render appendix HTML
# ---------------------------------------------------------------------------

def render_proof_table(proof, e):
    """Render proof_content dict into clean HTML table rows."""
    if not isinstance(proof, dict):
        if isinstance(proof, list):
            return '<ul class="proof-list">' + "".join(f"<li>{e(str(item))}</li>" for item in proof) + "</ul>"
        return f'<p>{e(str(proof))}</p>'

    rows = proof.get("rows", proof.get("steps", []))
    conclusion = proof.get("conclusion", proof.get("key_finding", proof.get("governing_conclusion", "")))

    if not rows and not conclusion:
        # Generic key-value, skip internal dicts/lists
        html_out = '<table><tbody>'
        for k, v in proof.items():
            if isinstance(v, (dict, list)):
                continue
            html_out += f'<tr><td style="font:500 12px/1.4 \'Inter\';color:#555;padding:8px 12px;width:40%;border-bottom:1px solid #eee">{e(str(k))}</td><td style="font:400 12px/1.4 \'Inter\';padding:8px 12px;border-bottom:1px solid #eee">{e(str(v))}</td></tr>'
        html_out += '</tbody></table>'
        if conclusion:
            html_out += f'<div class="slide-conclusion">{e(str(conclusion))}</div>'
        return html_out

    html_out = '<table><tbody>'
    for row in rows:
        if isinstance(row, dict):
            # Pick the most useful keys
            label = row.get("label", row.get("item", row.get("step", row.get("event", ""))))
            value = row.get("value", row.get("amount", row.get("derivation", "")))
            note = row.get("note", row.get("confidence", ""))

            # Truncate long values
            if isinstance(value, str) and len(value) > 120:
                value = value[:117] + "..."
            if isinstance(note, str) and len(note) > 100:
                note = note[:97] + "..."

            html_out += f'<tr><td class="pt-label">{e(str(label))}</td><td class="pt-value">{e(str(value))}</td>'
            if note:
                html_out += f'<td class="pt-note">{e(str(note))}</td>'
            html_out += '</tr>'
        elif isinstance(row, str):
            html_out += f'<tr><td colspan="3" style="padding:8px 12px;border-bottom:1px solid #eee">{e(row)}</td></tr>'
    html_out += '</tbody></table>'

    if conclusion:
        html_out += f'<div class="slide-conclusion">{e(str(conclusion))}</div>'

    return html_out


def render_appendix_html(ps_key, config, slides_data, one_pager):
    e = h.escape
    name = e(config["name"])
    slides = slides_data.get("slides", [])
    total = len(slides)

    slot_labels = {"A": "Prove a Number", "B": "Prove a Claim", "D": "Prove Executable"}

    slides_html = ""
    charts_js = ""
    for s in slides:
        num = s.get("appendix_num", "?")
        slot = s.get("slot_type", "?")
        slot_label = slot_labels.get(slot, slot)
        action_title = e(s.get("action_title", ""))
        subtitle = e(s.get("subtitle", ""))
        source_line = e(s.get("source_line", ""))
        claim = e(s.get("claim", "")[:200])

        proof = s.get("proof_content", {})
        proof_html = render_proof_table(proof, e)
        canvas_id = f"ch-a{num}"

        # Try to generate chart JS
        chart_code = build_chart_js(s, canvas_id)
        if chart_code:
            charts_js += chart_code
            chart_html = f'<div class="chart-wrap"><canvas id="{canvas_id}"></canvas></div>'
        else:
            chart_html = ""

        # Conclusion from proof
        conclusion = ""
        if isinstance(proof, dict):
            c = proof.get("conclusion", proof.get("key_finding", proof.get("governing_conclusion", "")))
            if c:
                conclusion = f'<div class="slide-conclusion">{e(str(c))}</div>'

        slides_html += f'''<div class="slide" id="s{num}">
<div class="slide-inner">
<div class="slide-top">
  <span class="slide-num">Appendix {num}</span>
  <span class="slide-slot">Slot {slot} | {e(slot_label)}</span>
</div>
<h2 class="slide-title">{action_title}</h2>
<p class="slide-subtitle">{subtitle}</p>
<div class="slide-body">
  {chart_html}
  {proof_html if not chart_code else ""}
  {conclusion}
</div>
<div class="slide-bottom">
  <div class="slide-claim">Proves: {claim}</div>
  <div class="slide-source">{source_line}</div>
</div>
</div>
</div>\n'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} -- Appendix</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-snap-type:y mandatory;scroll-behavior:smooth}}
body{{font-family:'Inter',sans-serif;background:#fff;color:#1a1a1a;overflow-x:hidden}}

/* Full-screen slide system */
.slide{{min-height:100vh;min-height:100dvh;scroll-snap-align:start;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:60px 40px;position:relative;border-bottom:1px solid #e5e7eb}}
.slide-inner{{width:100%;max-width:800px}}

/* Top bar */
.slide-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}
.slide-num{{font:800 16px/1 'JetBrains Mono';color:#2563eb}}
.slide-slot{{font:500 11px/1 'JetBrains Mono';color:#888;letter-spacing:1px;text-transform:uppercase}}

/* Title = action title = conclusion, not topic */
.slide-title{{font:800 26px/1.2 'Inter';color:#1a1a1a;margin-bottom:8px}}
.slide-subtitle{{font:400 13px/1.4 'Inter';color:#888;margin-bottom:24px}}

/* Proof body */
.slide-body{{margin:0 0 24px}}
.slide-body table{{width:100%;border-collapse:collapse}}
.slide-body .pt-label{{font:600 13px/1.4 'Inter';color:#1a1a1a;padding:10px 14px;border-bottom:1px solid #eee;width:35%;vertical-align:top}}
.slide-body .pt-value{{font:500 13px/1.4 'JetBrains Mono';color:#333;padding:10px 14px;border-bottom:1px solid #eee;vertical-align:top}}
.slide-body .pt-note{{font:400 11px/1.4 'Inter';color:#888;padding:10px 14px;border-bottom:1px solid #eee;vertical-align:top}}
.slide-conclusion{{font:600 14px/1.5 'Inter';color:#1a1a1a;margin-top:16px;padding:14px 16px;background:#f0f4ff;border-left:4px solid #2563eb;border-radius:0 6px 6px 0}}
.chart-wrap{{width:100%;height:280px;position:relative;margin:16px 0}}
.chart-wrap canvas{{width:100%!important;height:100%!important}}

/* Bottom */
.slide-bottom{{margin-top:auto;padding-top:16px;border-top:1px solid #eee}}
.slide-claim{{font:400 11px/1.4 'Inter';color:#aaa;margin-bottom:4px}}
.slide-source{{font:400 10px/1.3 'Inter';color:#bbb}}

/* Proof list */
.proof-list{{padding-left:20px;margin:8px 0}}
.proof-list li{{font:400 13px/1.6 'Inter';margin-bottom:6px}}

/* Fixed nav */
.nav{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:1000;background:rgba(255,255,255,.9);padding:8px 16px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.1);backdrop-filter:blur(8px)}}
.nav-btn{{font:600 12px/1 'Inter';padding:8px 16px;border:1px solid #ddd;border-radius:6px;background:#fff;color:#333;cursor:pointer}}
.nav-btn:hover{{background:#f0f4ff;border-color:#2563eb}}
.nav-counter{{font:500 12px/1 'JetBrains Mono';color:#888;padding:8px 12px;display:flex;align-items:center}}

/* Progress */
.progress{{position:fixed;top:0;left:0;height:3px;background:#2563eb;z-index:1000;transition:width .3s}}

.foot{{font:400 11px/1.5 'Inter';color:#aaa;text-align:center;padding:20px}}

@media(max-width:600px){{
  .slide{{padding:40px 20px}}
  .slide-title{{font-size:20px}}
  .slide-body .pt-note{{display:none}}
}}
@media print{{
  .slide{{min-height:auto;page-break-after:always;border:none;padding:30px}}
  .nav,.progress{{display:none}}
}}
</style>
</head>
<body>

<div class="progress" id="prog"></div>

{slides_html}

<div class="slide" style="min-height:30vh">
<div class="foot">Developed by Parth Reddy</div>
</div>

<div class="nav">
<button class="nav-btn" onclick="go(-1)">&larr; Prev</button>
<span class="nav-counter" id="ctr">1 / {total}</span>
<button class="nav-btn" onclick="go(1)">Next &rarr;</button>
</div>

<script>
// Charts
{charts_js}
</script>
<script>
const slides=document.querySelectorAll('.slide');
const total={total};
const prog=document.getElementById('prog');
const ctr=document.getElementById('ctr');
let cur=0;

function go(d){{
  cur=Math.max(0,Math.min(total,cur+d));
  slides[cur].scrollIntoView({{behavior:'smooth'}});
}}

function update(){{
  let best=0;
  slides.forEach((s,i)=>{{
    const r=s.getBoundingClientRect();
    if(r.top<window.innerHeight*.5) best=i;
  }});
  cur=best;
  prog.style.width=((best+1)/(total+1)*100)+'%';
  ctr.textContent=(best+1)+' / '+total;
}}

window.addEventListener('scroll',update);
document.addEventListener('keydown',e=>{{
  if(e.key==='ArrowDown'||e.key==='ArrowRight') go(1);
  if(e.key==='ArrowUp'||e.key==='ArrowLeft') go(-1);
}});
update();
</script>
</body>
</html>'''


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_ps(client, ps_key):
    config = PS_MAP[ps_key]
    source_ps = config["source_ps"]
    ps_dir = REPORT_DIR / ps_key

    log(f"{'='*50}")
    log(f"{config['name']}")
    log(f"{'='*50}")

    # Load existing outputs
    one_pager = json.load(open(ps_dir / "one_pager.json", encoding="utf-8"))
    hyp_tree = json.load(open(HYP_DIR / ps_key / "hypotheses_final.json", encoding="utf-8"))
    wd = (WD_DIR / source_ps / "working_document.md").read_text(encoding="utf-8")

    # 1. Render one-pager HTML
    log(f"  Rendering one-pager HTML...")
    op_html = render_onepager_html(ps_key, config, one_pager)
    (ps_dir / "onepager.html").write_text(op_html, encoding="utf-8")
    log(f"  One-pager: {len(op_html):,} chars")

    # 2. Map claims to appendix slides (LLM call)
    slides_data = map_claims_to_slides(client, ps_key, one_pager, hyp_tree, wd)
    (ps_dir / "appendix_map.json").write_text(
        json.dumps(slides_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"  Appendix: {len(slides_data.get('slides',[]))} slides mapped")

    # 3. Render appendix HTML
    log(f"  Rendering appendix HTML...")
    app_html = render_appendix_html(ps_key, config, slides_data, one_pager)
    (ps_dir / "appendix.html").write_text(app_html, encoding="utf-8")
    log(f"  Appendix: {len(app_html):,} chars")

    log(f"  DONE: onepager.html + appendix.html")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ps", type=str, help="Run single PS key (iocl_hmel or lownci_psu)")
    args = parser.parse_args()

    client = get_client()

    if args.ps:
        keys = [args.ps]
    else:
        keys = ["iocl_hmel", "lownci_psu"]

    for key in keys:
        if key not in PS_MAP:
            log(f"ERROR: {key} not configured")
            continue
        run_ps(client, key)

    log("ALL DONE")


if __name__ == "__main__":
    main()

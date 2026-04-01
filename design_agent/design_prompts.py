"""
Design Agent — Prompt templates for HTML card generation.

Each card is sent to Claude with:
1. The full dna.css (so it knows all available classes)
2. 2-3 reference card examples from the working v6 briefing
3. The card's content spec from the story engine
4. Instructions to output a complete <div class="card"> HTML block
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Load CSS once at import time
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_CSS_PATH = _HERE.parent / "presentation_engine" / "styles" / "dna.css"

def load_css() -> str:
    """Read dna.css content."""
    return _CSS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Reference examples extracted from the working v6 briefing
# ---------------------------------------------------------------------------

EXAMPLE_HERO = r'''<!-- EXAMPLE: Hero card (c1) — pulsing background, gradient title, hero numbers, stat row, badge -->
<div class="card" id="c1" style="background:radial-gradient(ellipse at 50% 60%,#1a0000,#0a0a0a)">
<div class="card-inner">
<p class="label" style="color:var(--red);margin-bottom:16px"><span class="countdown">STRATEGIC INTELLIGENCE BRIEFING · INDIA PERSPECTIVE</span></p>
<h1 style="font:900 44px/1 'Inter';background:linear-gradient(135deg,var(--red),var(--amber));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:24px">India's Energy War</h1>
<div class="hero-num" style="color:var(--red)">DAY 20</div>
<p class="card-sub" style="margin-top:8px;margin-bottom:28px">No ceasefire. No playbook. No precedent.</p>
<div class="stat-row">
<div class="stat"><div class="val" style="color:var(--red)">8M</div><div class="lbl">bbl/d offline</div></div>
<div class="stat"><div class="val" style="color:var(--amber)">$146</div><div class="lbl">Indian basket</div></div>
<div class="stat"><div class="val" style="color:var(--red)">74d</div><div class="lbl">reserve cover</div></div>
</div>
<div style="margin-top:20px;padding:6px 16px;background:var(--red);border-radius:4px;display:inline-block"><span class="mono" style="font-size:11px;font-weight:700;color:#fff;letter-spacing:1px">ZERO NEGOTIATIONS ACTIVE</span></div>
<div class="swipe-hint">scroll</div>
</div>
</div>'''

EXAMPLE_VERDICT = r'''<!-- EXAMPLE: Verdict panel (c7) — source panels with verdict banners, before/after, terminal grid, voyage bars -->
<div class="card" id="c7">
<div class="card-inner">
<p class="label" style="margin-bottom:12px">Supply Alternatives</p>
<h3 class="card-title">Your Crude Diet Just Changed.</h3>
<p class="card-sub" style="margin-bottom:16px">Three sources. Three problems. No clean answer.</p>

<div class="source-panel" style="margin-bottom:10px">
<div class="verdict" style="background:linear-gradient(90deg,#dc2626,#991b1b)"><div class="v-source">Russia</div><div class="v-msg">MORE EXPENSIVE · <span class="countdown">EXPIRING IN 15 DAYS</span></div></div>
<div class="panel-body">
<div class="compare-row" style="border-bottom:none;padding:8px 0"><div class="cr-label">Urals vs Brent</div><div class="cr-before">−$13</div><div class="cr-arrow">→</div><div class="cr-after">+$5</div><div style="font:700 12px JetBrains Mono;color:var(--red);margin-left:8px">$18 swing</div></div>
<div style="font:400 10px Inter;color:#888">30M bbl bought · RIL ~10M, IOCL ~10M · Delivered: <span class="mono" style="color:#dc2626;font-weight:700">$98.93/bbl</span></div>
</div></div>

<div class="source-panel" style="margin-bottom:10px">
<div class="verdict" style="background:linear-gradient(90deg,#7f1d1d,#450a0a)"><div class="v-source">Gulf States</div><div class="v-msg">PHYSICALLY DESTROYED</div></div>
<div class="panel-body">
<div style="font:400 10px Inter;color:#888;margin-bottom:10px">Every major loading terminal serving India — offline or damaged.</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">
<div style="text-align:center;padding:10px 6px;background:#f5f5f5;border-radius:6px">
<div style="font:800 22px Inter;color:#cc2020">✕</div>
<div style="font:600 10px Inter;color:#1a1a1a;margin-top:4px">Ras Tanura</div>
<div style="font:400 9px Inter;color:#888">Saudi · Shut down</div>
</div>
<div style="text-align:center;padding:10px 6px;background:#f5f5f5;border-radius:6px">
<div style="font:800 22px Inter;color:#cc2020">✕</div>
<div style="font:600 10px Inter;color:#1a1a1a;margin-top:4px">Fujairah</div>
<div style="font:400 9px Inter;color:#888">UAE · Suspended</div>
</div>
<div style="text-align:center;padding:10px 6px;background:#f5f5f5;border-radius:6px">
<div style="font:800 22px Inter;color:#cc2020">✕</div>
<div style="font:600 10px Inter;color:#1a1a1a;margin-top:4px">Ras Laffan</div>
<div style="font:400 9px Inter;color:#888">Qatar · Damaged</div>
</div>
</div>
</div></div>

<div class="source-panel">
<div class="verdict" style="background:linear-gradient(90deg,#92400e,#78350f)"><div class="v-source">Alternatives</div><div class="v-msg">SLOW & WRONG GRADE</div></div>
<div class="panel-body">
<div class="v-row"><div class="v-label" style="text-decoration:line-through;color:#cc2020">Gulf → India</div><div class="v-track"><div class="v-fill" style="width:12%;background:#dc2626;opacity:.5"></div></div><div class="v-days" style="color:#cc2020;text-decoration:line-through">5-7d</div></div>
<div class="v-row"><div class="v-label">W. Africa</div><div class="v-track"><div class="v-fill" style="width:50%;background:linear-gradient(90deg,#d97706,#fbbf24)">20-25d</div></div><div class="v-days" style="color:#b45309;font-weight:800">4×</div></div>
<div class="v-row"><div class="v-label">Brazil</div><div class="v-track"><div class="v-fill" style="width:85%;background:linear-gradient(90deg,#d97706,#fbbf24)">30-45d</div></div><div class="v-days" style="color:#b45309;font-weight:800">7×</div></div>
<div style="margin-top:8px;padding:8px 12px;background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.25);border-radius:6px;font:600 10px/1.3 Inter;color:#b45309">⚠ Grade mismatch: light/sweet available — your refinery wants heavy/sour.</div>
</div></div>

<div class="insight">No clean barrel left. Russia is expensive and expiring. Gulf is offline. Alternatives are slow and wrong grade.</div>
</div></div>'''

EXAMPLE_SCENARIO = r'''<!-- EXAMPLE: Scenario card (c12) — full-bleed scenario cards with probability labels -->
<div class="card" id="c12">
<div class="card-inner">
<p class="label" style="margin-bottom:12px">Scenario Planning</p>
<h3 class="card-title">Three Scenarios. Three Price Worlds.</h3>

<div class="scenario-card" style="background:linear-gradient(135deg,rgba(255,176,32,.2),rgba(255,176,32,.05));border:1px solid rgba(255,176,32,.3)">
<div style="font:600 9px Inter;text-transform:uppercase;letter-spacing:1.5px;color:rgba(255,176,32,.6);margin-bottom:4px">Probability</div>
<div class="sc-prob" style="color:var(--amber)">35-40%</div>
<div class="sc-title" style="color:var(--amber)">Prolonged Standoff — BASE CASE</div>
<div class="sc-stats">
<div class="sc-stat"><div class="ss-v" style="color:var(--amber)">$100-130</div><div class="ss-l">Brent range</div></div>
<div class="sc-stat"><div class="ss-v" style="color:var(--amber)">Q2-Q3</div><div class="ss-l">Hormuz closed</div></div>
<div class="sc-stat"><div class="ss-v" style="color:var(--amber)">$220-266B</div><div class="ss-l">Import bill/yr</div></div>
</div>
<div class="sc-insight">Both sides dug in. Mine clearance 51+ days after any ceasefire. No off-ramp visible.</div>
</div>

<div class="scenario-card" style="background:linear-gradient(135deg,rgba(255,59,59,.2),rgba(255,59,59,.05));border:1px solid rgba(255,59,59,.3)">
<div style="font:600 9px Inter;text-transform:uppercase;letter-spacing:1.5px;color:rgba(255,59,59,.5);margin-bottom:4px">Probability</div>
<div class="sc-prob" style="color:var(--red)">30-35%</div>
<div class="sc-title" style="color:var(--red)">Conflagration — Energy War ↑</div>
<div class="sc-stats">
<div class="sc-stat"><div class="ss-v" style="color:var(--red)">$130-200</div><div class="ss-l">Brent range</div></div>
<div class="sc-stat"><div class="ss-v" style="color:var(--red)">2026+</div><div class="ss-l">Hormuz closed</div></div>
<div class="sc-stat"><div class="ss-v" style="color:var(--red)">$266-400B+</div><div class="ss-l">Import bill/yr</div></div>
</div>
<div class="sc-insight">South Pars + Ras Laffan crossed a threshold. Gulf infrastructure under sustained attack. Probability rising.</div>
</div>

<div class="scenario-card" style="background:linear-gradient(135deg,rgba(52,211,153,.15),rgba(52,211,153,.03));border:1px solid rgba(52,211,153,.3)">
<div style="font:600 9px Inter;text-transform:uppercase;letter-spacing:1.5px;color:rgba(52,211,153,.5);margin-bottom:4px">Probability</div>
<div class="sc-prob" style="color:var(--green)">15-20%</div>
<div class="sc-title" style="color:var(--green)">Resolution / De-escalation</div>
<div class="sc-stats">
<div class="sc-stat"><div class="ss-v" style="color:var(--green)">$75-85</div><div class="ss-l">Brent range</div></div>
<div class="sc-stat"><div class="ss-v" style="color:var(--green)">60-90d</div><div class="ss-l">To reopen</div></div>
<div class="sc-stat"><div class="ss-v" style="color:var(--green)">~$165B</div><div class="ss-l">Import bill/yr</div></div>
</div>
<div class="sc-insight">Still 51 days of mine clearance. The optimistic scenario nobody privately believes.</div>
</div>
</div></div>'''

EXAMPLE_CHART = r'''<!-- EXAMPLE: Chart card (c8) — NCI bubble scatter in light panel, with KPIs and insight -->
<div class="card" id="c8">
<div class="card-inner">
<p class="label green" style="margin-bottom:12px">The Divide</p>
<h3 class="card-title">Configuration Is Destiny.</h3>
<p class="card-sub" style="margin-bottom:16px">Nelson Complexity determines who profits and who bleeds at $146.</p>

<div class="panel-light" style="padding:16px;margin-bottom:16px">
<div style="font:600 9px Inter;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;text-align:center">NCI vs GRM Impact — Bubble = Capacity</div>
<div class="chart-c" style="height:260px"><canvas id="ch-c8"></canvas></div>
</div>

<div class="kpi-grid" style="grid-template-columns:1fr 1fr 1fr">
<div class="kpi" style="border-color:var(--green)"><div class="kl">Jamnagar</div><div class="kv" style="color:var(--green);font-size:22px">21.1</div><div class="kd" style="color:var(--green)">Profitable at $200</div></div>
<div class="kpi" style="border-color:var(--amber)"><div class="kl">OMC Avg</div><div class="kv" style="color:var(--amber);font-size:22px">~10</div><div class="kd" style="color:var(--amber)">Break even $110</div></div>
<div class="kpi" style="border-color:var(--red)"><div class="kl">HPCL Mum</div><div class="kv" style="color:var(--red);font-size:22px">5.6</div><div class="kd" style="color:var(--red)">Break even $95</div></div>
</div>

<div class="insight g">One refinery — Jamnagar — has processed 216 crude grades. The other 22 are a bet on Gulf crude arriving. That bet just lost.</div>
<script>
(function(){new Chart(document.getElementById('ch-c8'),{type:'bubble',data:{datasets:[
{label:'Jamnagar',data:[{x:21.1,y:3.2,r:22}],backgroundColor:'rgba(52,211,153,.4)',borderColor:'#34d399',borderWidth:2},
{label:'Nayara',data:[{x:12.8,y:1.5,r:10}],backgroundColor:'rgba(52,211,153,.25)',borderColor:'#34d399',borderWidth:1},
{label:'Paradip',data:[{x:12.2,y:0.5,r:8}],backgroundColor:'rgba(255,176,32,.25)',borderColor:'#ffb020',borderWidth:1},
{label:'Panipat',data:[{x:13.7,y:0.8,r:8}],backgroundColor:'rgba(255,176,32,.25)',borderColor:'#ffb020',borderWidth:1},
{label:'Kochi',data:[{x:10.8,y:-0.5,r:7}],backgroundColor:'rgba(255,176,32,.2)',borderColor:'#ffb020',borderWidth:1},
{label:'MRPL',data:[{x:10.6,y:-2,r:7}],backgroundColor:'rgba(255,176,32,.2)',borderColor:'#ffb020',borderWidth:1},
{label:'BPCL Mum',data:[{x:6,y:-5,r:6}],backgroundColor:'rgba(255,59,59,.35)',borderColor:'#ff3b3b',borderWidth:2},
{label:'HPCL Mum',data:[{x:5.6,y:-6,r:5}],backgroundColor:'rgba(255,59,59,.45)',borderColor:'#ff3b3b',borderWidth:2}
]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#888',font:{family:'Inter',size:8}}}},scales:{x:{title:{display:true,text:'Nelson Complexity Index →',color:'#888',font:{family:'Inter',size:10}},grid:{color:'rgba(0,0,0,.06)'},ticks:{color:'#888',font:{family:'JetBrains Mono',size:9}},min:4,max:23},y:{title:{display:true,text:'GRM Change $/bbl →',color:'#888',font:{family:'Inter',size:10}},grid:{color:'rgba(0,0,0,.06)'},ticks:{color:'#888',font:{family:'JetBrains Mono',size:9}},min:-8,max:5}}}})})();
</script>
</div></div>'''

EXAMPLE_MAP = r'''<!-- EXAMPLE: Map card (c20) — Leaflet map with markers, KPIs, insight -->
<div class="card" id="c20">
<div class="card-inner">
<p class="label" style="margin-bottom:12px">Lever 3: Non-Alignment</p>
<h3 class="card-title">Who's Getting Through Hormuz?</h3>
<p class="card-sub" style="margin-bottom:16px">India's non-alignment got 3 ships through. China got 11. Japan got zero.</p>
<div id="map-c20" class="map-c" style="height:280px"></div>
<div class="kpi-grid" style="grid-template-columns:1fr 1fr 1fr;margin-top:12px">
<div class="kpi" style="border-color:var(--green)"><div class="kl">China</div><div class="kv" style="color:var(--green)">11</div><div class="kd" style="color:var(--green)">Blanket deal</div></div>
<div class="kpi" style="border-color:var(--amber)"><div class="kl">India</div><div class="kv" style="color:var(--amber)">3</div><div class="kd" style="color:var(--amber)">Case-by-case</div></div>
<div class="kpi" style="border-color:var(--red)"><div class="kl">Japan/Korea/EU</div><div class="kv" style="color:var(--red)">0</div><div class="kd" style="color:var(--red)">Nothing through</div></div>
</div>
<div class="insight">China is the real winner. India's 70% non-Hormuz diversification — not diplomacy — is the real insurance.</div>
<script>
(function(){var m=L.map('map-c20',{zoomControl:false,attributionControl:false,dragging:false,scrollWheelZoom:false}).setView([25,56],6);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(m);
for(var i=0;i<11;i++){L.circleMarker([25+Math.random()*2,55+Math.random()*3],{radius:5,color:'#16a34a',fillColor:'#16a34a',fillOpacity:.6,weight:1}).addTo(m)}
for(var i=0;i<3;i++){L.circleMarker([23+Math.random(),62+Math.random()*5],{radius:5,color:'#d97706',fillColor:'#d97706',fillOpacity:.6,weight:1}).addTo(m)}
for(var i=0;i<19;i++){L.circleMarker([25.5+Math.random()*1.5,52+Math.random()*3],{radius:3,color:'#dc2626',fillColor:'#dc2626',fillOpacity:.5,weight:0}).addTo(m)}
L.marker([26.4,56.4],{icon:L.divIcon({className:'',html:'<div class="pulse-marker"></div>',iconSize:[12,12],iconAnchor:[6,6]})}).addTo(m);
L.marker([26.5,57.5],{icon:L.divIcon({className:'map-label map-label-green',html:'<b style="color:#16a34a">China: 11</b>',iconSize:[80,20]})}).addTo(m);
L.marker([23.5,65],{icon:L.divIcon({className:'map-label',html:'<b style="color:#b45309">India: 3 through</b>',iconSize:[110,20]})}).addTo(m);
L.marker([25,51.5],{icon:L.divIcon({className:'map-label map-label-red',html:'<b style="color:#cc2020">India: 19 stuck</b>',iconSize:[100,20]})}).addTo(m);
L.polyline([[25.5,56.5],[24,62],[23,69]],{color:'#d97706',weight:2,dashArray:'5,5',opacity:.5}).addTo(m)})();
</script>
</div></div>'''


# ---------------------------------------------------------------------------
# Example selection by card type
# ---------------------------------------------------------------------------

# Map card types to the most relevant examples (2-3 per type)
EXAMPLE_MAP_BY_TYPE = {
    "hero":          [EXAMPLE_HERO, EXAMPLE_SCENARIO],
    "timeline":      [EXAMPLE_HERO, EXAMPLE_VERDICT],
    "kpi_card":      [EXAMPLE_CHART, EXAMPLE_HERO],
    "verdict_panel": [EXAMPLE_VERDICT, EXAMPLE_HERO],
    "scenario_card": [EXAMPLE_SCENARIO, EXAMPLE_HERO],
    "chart_card":    [EXAMPLE_CHART, EXAMPLE_SCENARIO],
    "map_card":      [EXAMPLE_MAP, EXAMPLE_CHART],
    "checklist":     [EXAMPLE_HERO, EXAMPLE_VERDICT],
    "closing":       [EXAMPLE_HERO, EXAMPLE_SCENARIO],
    "domino_row":    [EXAMPLE_HERO, EXAMPLE_CHART],
    "act_break":     [EXAMPLE_HERO, EXAMPLE_SCENARIO],
    "quote_pair":    [EXAMPLE_VERDICT, EXAMPLE_HERO],
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior data visualization designer building HTML cards for a strategic intelligence briefing. You output ONLY the HTML for a single card — a complete <div class="card"> block. Use the CSS classes from the provided stylesheet. Match the quality of the reference examples exactly.

RULES:
1. Output ONLY the <div class="card" id="{card_id}">...</div> HTML block.
2. Include ALL content, numbers, labels, insight boxes — nothing placeholder.
3. For Chart.js charts: include a <canvas id="ch-{card_id}"> and output the Chart.js init code in a <script> tag INSIDE the card div. Use an IIFE wrapper: (function(){ ... })();
4. For Leaflet maps: include a <div id="map-{card_id}" class="map-c"> and output the Leaflet init code in a <script> tag INSIDE the card div. Use an IIFE wrapper. Use tile URL: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
5. Use the EXACT CSS classes from dna.css — do not invent new classes.
6. Inline styles are fine for one-off colors, gradients, and sizing.
7. Every data card MUST have a <p class="src"> attribution line.
8. No markdown, no explanation, no commentary — ONLY the HTML.
9. Preserve all data values exactly from the card spec — do not invent new numbers.
10. Use JetBrains Mono for all numbers/data. Use Inter for all text/labels.
11. Always wrap card content in <div class="card-inner"> for proper centering.

CRITICAL — ALL LIGHT BACKGROUNDS (ONE EXCEPTION):
ALL cards use a light/white background EXCEPT the hero card (card_id c1 or first card).

The HERO CARD is the one exception:
- Dark background with radial gradient: background:radial-gradient(ellipse at 50% 60%,#1a0000,#0a0a0a)
- Pulsing subtle animation on the background
- Title in gradient text (red→amber): -webkit-background-clip:text
- Hero number LARGE (80px+), pulsing red glow: text-shadow: 0 0 40px rgba(255,59,59,.3)
- Stats below in a row — red/amber colors
- Badge at bottom — solid red background, white text
- The hero must feel like walking into a war room. Urgent, dramatic, premium.
- Swipe hint at bottom

EVERY OTHER CARD: light/white background. Clean, premium, magazine-like.

- Card background: #fafafa or #f5f5f5 with color:#1a1a1a
- Use style="background:#fafafa;color:#1a1a1a" on every non-hero card div
- Data panels: white (#fff) with subtle box-shadow (0 2px 8px rgba(0,0,0,.06)) or thin borders (1px solid #eee)
- Charts: dark gridlines, dark labels, colored data
- Insight box: dark background (#1a1a1a or #222) with light text — this creates contrast against the white card
- KPI panels: white with colored left borders and subtle shadow
- Verdict banners: keep the gradient headers — they pop against white
- Act breaks: white background, large faded text or symbol in light gray (#e5e5e5)
- Hero/opening card: white background but with a subtle warm gradient accent strip or colored top border
- Scenario cards: use colored borders and subtle tinted backgrounds (rgba tints), NOT full dark backgrounds

VISUAL VARIETY ON WHITE:
Since all cards are white, create variety through:
- Colored accent borders (top or left) on panels
- Gradient verdict banners (these POP on white)
- Colored KPI numbers
- Chart colors
- Tinted scenario card backgrounds (very subtle, like rgba(255,176,32,.05))
- Bold typography hierarchy — large numbers, small labels

ALIGNMENT RULES (MANDATORY):
- All card titles: centered, max-width 500px, margin 0 auto
- All subtitles (.card-sub): centered, max-width 440px, margin 0 auto
- Insight boxes: full width of card-inner, left-aligned text
- KPI grids: centered within card-inner
- No element should overflow card-inner's max-width

ANIMATION RULES:
- Timeline items: use opacity:0 by default, add class for fade-in on scroll
- Checklist items: stagger appearance with animation-delay (0.1s per item)
- Domino items: use the dominoFall animation with staggered delays
- Hero numbers: use the countdown pulse animation for urgent numbers
- Include this scroll observer in cards that need animation:
  Use IntersectionObserver to add 'in-view' class when card enters viewport

MAP RULES (HARD — NEVER VIOLATE):
- Zoom level: if markers are within 5 degrees of each other, zoom OUT until there is clear visual separation
- NEVER put text labels directly on the map — use numbered circle markers ONLY
- Always include a numbered legend below the map
- Map container height: 240-280px, never taller
- If a map has overlapping labels on screenshot review, the zoom level is WRONG — go wider

HEADER RULES:
- Card title MUST BE the EXACT key_message from the card spec. Do NOT rewrite, rephrase, shorten, or summarize it. Use it VERBATIM as the card's h3 title. This is non-negotiable — the story arc was approved by the user and must not be altered.
- Card title: LEFT-ALIGNED, font-size that fits ONE LINE (max 28px, reduce to 24px, 22px, or 20px if needed to fit)
- If the key_message is too long for one line at 20px, split across two lines but keep the EXACT words
- Sub-header: LEFT-ALIGNED, muted color, 13-14px — this can be a brief context line you write
- Both must be inside card-inner with text-align:left
- Never center-align titles — left alignment creates a professional, editorial feel

GRAPH BOX RULES (MANDATORY — every chart must follow this):
- Line 1: KEY TAKEAWAY in bold (what should the reader conclude?) — e.g., "Largest oil supply disruption in recorded history"
- Line 2: Graph description + units in muted text — e.g., "Brent crude price, $/bbl, Feb 28 – Mar 19, 2026"
- Line 3: The chart/visual itself
- This 3-line pattern applies to EVERY chart, map, bar chart, scatter plot, timeline

CHART ANNOTATIONS (MANDATORY — every chart must have at least one):
- Every Chart.js chart MUST have at least one annotation pointing to the key insight
- Use the chartjs-plugin-annotation: type:'label' for callout text, type:'line' for reference lines
- Examples of good annotations:
  - Futures curve: "LOCK $69-75" label at Dec 2026 point
  - Cash burn: "INSOLVENCY" dashed line at y=0
  - Butterfly chart: "BASELINE" vertical line at x=0
  - Price chart: "TODAY $146" arrow pointing to current price
  - Scenario bars: "NOW" dashed line at current Brent price
- The annotation IS the insight — without it, the chart is just data

CHART SCALE RULES:
- If the max value is >5x the min value, consider a non-linear scale or truncated axis
- If values cluster tightly with one outlier, use a broken axis or call out the outlier separately
- Never let extreme values compress the readable data into a flat line
- If a waterfall has steps of $500B and $10B, the $10B bar will be invisible — use percentage or log scale instead
- Always set explicit min/max on axes — never let Chart.js auto-scale if it produces unreadable results

VISUAL VARIETY ENFORCEMENT:
- Count the visual types in your card sequence. If you see >2 horizontal_bar charts in any 5-card window, you MUST switch one to:
  waterfall, gauge, bubble_scatter, before_after_bars, dot_grid, sankey, or 2x2_matrix
- Adjacent cards MUST use different visual types — no two bar charts in a row
- The reader should feel visual surprise on every scroll — variety creates engagement

ABBREVIATION RULES:
- NEVER use an abbreviation without defining it on first use or in a footnote
- First use format: "Current Account Deficit (CAD)" — subsequent uses can say "CAD"
- Common abbreviations that MUST be defined: CAD, GRM, NCI, ESMA, SPR, OMC, IOCL, BPCL, HPCL, ATF, FCC, bbl/d, MMT, LPG, LNG
- If space is tight, add a small footnote line: e.g., "GRM = Gross Refining Margin; NCI = Nelson Complexity Index"

VIEWPORT HEIGHT — ABSOLUTE LIMIT (NEVER VIOLATE):
- Every card MUST fit in exactly one viewport (100vh / ~1920px on mobile).
- If content doesn't fit in one screen, you have too much content. REMOVE data until it fits.
- NEVER let a card scroll. NEVER produce a card taller than 100vh.
- If you have a chart + KPI strip + insight box and they don't fit, drop the KPI strip.
- Less content that fits > more content that overflows.

CARD ORDERING:
- Card 1 (first card) MUST be card_type="hero" with background="dark"
- It MUST have the dramatic dark radial gradient opener
- Act breaks NEVER come first — they separate sections, they don't open the briefing

DARK/LIGHT ISOLATION:
- Dark cards: use inline style="background:#0a0a0a;color:#e5e5e5" directly on the card div
- Light cards: use inline style="background:#fafafa;color:#1a1a1a" directly on the card div
- NEVER rely on inherited backgrounds — always set explicitly on each card
- This prevents dark cards from bleeding into adjacent light cards

FONT OVERFLOW PREVENTION:
- Title text must NEVER exceed the card-inner max-width (600px)
- If a title is longer than ~30 characters, reduce font-size to 26px or 24px
- Hero card title: test that the gradient text fits — if "India's Energy War" is too wide at 44px, drop to 38px
- All text must have overflow-wrap:break-word as a safety net
- KPI values: if the number is 6+ characters (e.g., "$266B"), use font-size 24px not 28px
- NEVER let text clip or overflow horizontally

COMPACT CARDS:
- Each card must fit in a single mobile viewport (100vh) without scrolling
- Scenario cards: use probability number at 36px (not 52px), tighter padding (16px not 24px)
- If a card has 3+ data sections, reduce padding and font sizes to fit
- Act breaks: minimal — title + subtitle + symbol, nothing else

TONE — MBB PARTNER STYLE:
Write like a McKinsey/BCG senior partner, not a news anchor or a politician.
- State facts and implications. Do NOT use dramatic language, exclamation marks, or alarmist phrasing.
- BAD: "No clean barrel left!" → GOOD: "No crude source remains without significant compromise."
- BAD: "The board that waits loses!" → GOOD: "Delay in board action increases exposure by $14-16B per $10/bbl per quarter."
- BAD: "PHYSICALLY DESTROYED" → GOOD: "All three loading terminals offline or under repair."
- Insight boxes should read like partner recommendations, not headlines. Lead with the implication, not the emotion.
- Numbers speak for themselves. Let the data create urgency — don't add adjectives.
- The overall tone should be: calm authority under pressure. Informed, decisive, measured."""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _load_vault_examples(card_type: str, visual_type: str = None) -> str:
    """Load 2-3 relevant vault examples based on card type and visual type."""
    vault_path = _HERE.parent / "vault"
    index_path = vault_path / "_index.json"

    if not index_path.exists():
        # Fallback to hardcoded examples
        examples = EXAMPLE_MAP_BY_TYPE.get(card_type, [EXAMPLE_HERO, EXAMPLE_CHART])
        return "\n\n".join(examples)

    import json
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    # Map card_type to FT Visual Vocabulary categories
    TYPE_TO_CATEGORIES = {
        "hero": ["magnitude", "structure"],
        "timeline": ["change_over_time"],
        "kpi_card": ["magnitude", "part_to_whole"],
        "verdict_panel": ["deviation", "ranking", "structure"],
        "scenario_card": ["structure"],
        "chart_card": ["deviation", "correlation", "ranking", "change_over_time", "magnitude", "part_to_whole"],
        "map_card": ["spatial"],
        "quote_pair": ["structure"],
        "checklist": ["structure"],
        "act_break": ["structure"],
        "closing": ["structure", "change_over_time"],
    }

    # Also map visual_type hints to categories
    VISUAL_TO_CATEGORY = {
        "waterfall": "magnitude",
        "waterfall_chart": "magnitude",
        "sankey": "flow",
        "gauge": "magnitude",
        "line_chart": "change_over_time",
        "before_after_bars": "deviation",
        "bubble_scatter": "correlation",
        "horizontal_bar": "ranking",
        "map": "spatial",
        "scenario_cards": "structure",
        "2x2_matrix": "structure",
        "decision_tree": "structure",
        "quote_pair": "structure",
        "timeline": "change_over_time",
        "dot_grid": "part_to_whole",
        "checklist": "structure",
        "big_number": "magnitude",
    }

    # Determine which categories to pull from
    categories = TYPE_TO_CATEGORIES.get(card_type, ["structure"])
    if visual_type and visual_type in VISUAL_TO_CATEGORY:
        categories = [VISUAL_TO_CATEGORY[visual_type]] + categories

    # Collect matching examples (max 3)
    examples = []
    seen_files = set()
    for cat_name in categories:
        cat = index.get("categories", {}).get(cat_name, {})
        for ex in cat.get("examples", []):
            if ex["file"] not in seen_files:
                filepath = vault_path / ex["file"]
                if filepath.exists():
                    html = filepath.read_text(encoding="utf-8")
                    examples.append(f"<!-- VAULT EXAMPLE: {ex['description']} -->\n{html}")
                    seen_files.add(ex["file"])
                    if len(examples) >= 3:
                        break
        if len(examples) >= 3:
            break

    if not examples:
        # Fallback
        examples_list = EXAMPLE_MAP_BY_TYPE.get(card_type, [EXAMPLE_HERO, EXAMPLE_CHART])
        return "\n\n".join(examples_list)

    return "\n\n".join(examples)


def build_design_prompt(card: dict, card_type: str) -> tuple[str, str]:
    """
    Build the system prompt and user prompt for a single card.
    Pulls relevant examples from the vault based on card type and visual type.

    Returns
    -------
    tuple[str, str]
        (system_prompt, user_prompt)
    """
    import json

    css = load_css()

    # Get visual type hint from sub_messages if available
    visual_type = None
    for sm in card.get("sub_messages", []):
        vt = sm.get("visual_type")
        if vt and vt != "text":
            visual_type = vt
            break

    examples_text = _load_vault_examples(card_type, visual_type)

    card_id = card.get("card_id", "c0")

    user_prompt = f"""CSS CLASSES AVAILABLE:
{css}

REFERENCE EXAMPLES (match this quality):
{examples_text}

CARD TO BUILD:
{json.dumps(card, indent=2)}

Output ONLY the <div class="card" id="{card_id}">...</div> HTML block.
- Include ALL content, numbers, labels, insight boxes
- For Chart.js charts: include a <canvas id="ch-{card_id}"> and output the Chart.js init code in a <script> tag INSIDE the card div
- For Leaflet maps: include a <div id="map-{card_id}"> and output the Leaflet init code in a <script> tag INSIDE the card div
- Use the EXACT CSS classes from dna.css
- No markdown, no explanation, ONLY the HTML"""

    return SYSTEM_PROMPT, user_prompt

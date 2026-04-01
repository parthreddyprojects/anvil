"""
Chart card — Card with Chart.js visualization inside a light panel.

Expected data keys:
  card_id:      str
  title:        str
  subtitle:     str (optional)
  label:        str
  label_color:  str
  chart_id:     str  — unique DOM id for the canvas
  chart_config: dict — full Chart.js config (type, data, options)
  chart_height: str  — CSS height for chart container (default "220px")
  chart_label:  str  — small label above the chart (optional)
  kpis:         list of KPI dicts (optional — shown below chart)
  kpi_columns:  int  (2 or 3, default 2)
  dominoes:     list of {value, label, color} (optional — below chart)
  insight:      str  (optional)
  insight_color: str (optional)
  source:       str  (optional)
  extra_html:   str  (optional — injected between chart and KPIs)
"""

import json
from html import escape


def render_chart_card(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = data.get("subtitle", "")
    label = escape(data.get("label", ""))
    label_color = data.get("label_color", "")
    chart_id = data.get("chart_id", f"ch-{card_id}")
    chart_config = data.get("chart_config", {})
    chart_height = data.get("chart_height", "220px")
    chart_label = data.get("chart_label", "")
    kpis = data.get("kpis", [])
    kpi_columns = data.get("kpi_columns", 2)
    dominoes = data.get("dominoes", [])
    insight = data.get("insight", "")
    insight_color = data.get("insight_color", "")
    source = data.get("source", "")
    extra_html = data.get("extra_html", "")

    sub_html = ""
    if subtitle:
        sub_html = f'<p class="card-sub" style="margin-bottom:16px">{escape(subtitle)}</p>'

    chart_label_html = ""
    if chart_label:
        chart_label_html = (
            f'<div style="font:600 9px Inter;color:#888;text-transform:uppercase;'
            f'letter-spacing:1px;margin-bottom:8px;text-align:center">{escape(chart_label)}</div>'
        )

    # KPI grid
    kpi_html = ""
    if kpis:
        kpi_items = []
        for k in kpis:
            bc = k.get("border_color", k.get("color", "var(--dim)"))
            kl = escape(str(k.get("label", "")))
            kv = escape(str(k.get("value", "")))
            kv_color = k.get("color", "var(--text)")
            kv_style = f'color:{kv_color}'
            if len(str(k.get("value", ""))) > 5:
                kv_style += ";font-size:18px"
            delta = k.get("delta", "")
            delta_html = ""
            if delta:
                dc = k.get("delta_color", "var(--muted)")
                delta_html = f'<div class="kd" style="color:{dc}">{escape(str(delta))}</div>'
            kpi_items.append(
                f'<div class="kpi" style="border-color:{bc}">'
                f'<div class="kl">{kl}</div>'
                f'<div class="kv" style="{kv_style}">{kv}</div>'
                f'{delta_html}'
                f'</div>'
            )
        cols = f"repeat({kpi_columns},1fr)"
        kpi_html = f'<div class="kpi-grid" style="grid-template-columns:{cols}">{"".join(kpi_items)}</div>'

    # Dominoes
    domino_html = ""
    if dominoes:
        items = []
        for d in dominoes:
            color = d.get("color", "var(--text)")
            val = escape(str(d.get("value", "")))
            lbl = d.get("label", "")  # allow HTML
            items.append(
                f'<div class="domino" style="border-color:{color}">'
                f'<div class="d-val" style="color:{color}">{val}</div>'
                f'<div class="d-name">{lbl}</div>'
                f'</div>'
            )
        domino_html = f'<div class="dominoes">{"".join(items)}</div>'

    insight_html = ""
    if insight:
        ic = f" {insight_color}" if insight_color else ""
        insight_html = f'<div class="insight{ic}">{escape(insight)}</div>'

    source_html = ""
    if source:
        source_html = f'<p class="src">{escape(source)}</p>'

    return f'''<div class="card" id="{card_id}">
<div class="card-inner">
<p class="label {label_color}" style="margin-bottom:12px">{label}</p>
<h3 class="card-title">{title}</h3>
{sub_html}
<div class="panel-light" style="padding:16px;margin-bottom:16px">
{chart_label_html}
<div class="chart-c" style="height:{chart_height}"><canvas id="{chart_id}"></canvas></div>
</div>
{extra_html}
{kpi_html}
{domino_html}
{insight_html}
{source_html}
</div>
</div>'''


def chart_init_script(chart_id: str, chart_config: dict) -> str:
    """Return a JS IIFE that initializes a Chart.js chart for this card."""
    config_json = json.dumps(chart_config, ensure_ascii=False)
    return f"(function(){{new Chart(document.getElementById('{chart_id}'),{config_json})}})();"

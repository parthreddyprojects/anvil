"""
KPI card — hero number + KPI grid + optional dot-grid visualization.

Expected data keys:
  card_id:    str
  title:      str
  subtitle:   str (optional)
  label:      str
  label_color: str (red, green, blue, amber)
  hero:       {value, label, color} (optional — big number at top)
  kpis:       list of {label, value, delta, color, border_color}
  kpi_columns: int (2 or 3, default 2)
  dot_grid:   {green_count, red_count, legend} (optional)
  insight:    str (optional)
  insight_color: str (optional — g, a, b for green/amber/blue)
  source:     str (optional)
  extra_html: str (optional — raw HTML injected before KPI grid)
"""

from html import escape


def render_kpi_card(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = data.get("subtitle", "")
    label = escape(data.get("label", ""))
    label_color = data.get("label_color", "red")
    hero = data.get("hero", None)
    kpis = data.get("kpis", [])
    kpi_columns = data.get("kpi_columns", 2)
    dot_grid = data.get("dot_grid", None)
    insight = data.get("insight", "")
    insight_color = data.get("insight_color", "")
    source = data.get("source", "")
    extra_html = data.get("extra_html", "")

    # Subtitle
    sub_html = ""
    if subtitle:
        sub_html = f'<p class="card-sub" style="margin-bottom:24px">{escape(subtitle)}</p>'

    # Hero number
    hero_html = ""
    if hero:
        h_color = hero.get("color", "var(--red)")
        h_val = escape(str(hero.get("value", "")))
        h_label = escape(str(hero.get("label", "")))
        hero_html = (
            f'<div class="hero-num" style="color:{h_color};margin:16px 0">{h_val}</div>'
            f'<p style="font:500 11px Inter;text-transform:uppercase;letter-spacing:1.5px;'
            f'color:var(--muted);margin-bottom:20px">{h_label}</p>'
        )

    # Dot grid
    dot_html = ""
    if dot_grid:
        green_n = dot_grid.get("green_count", 0)
        red_n = dot_grid.get("red_count", 0)
        dots = []
        for _ in range(green_n):
            dots.append('<div class="dot" style="background:var(--green);width:20px;height:20px;border-radius:50%"></div>')
        for _ in range(red_n):
            dots.append('<div class="dot" style="background:var(--red);width:20px;height:20px;border-radius:50%;opacity:.7"></div>')
        legend = dot_grid.get("legend", "")
        dot_html = (
            f'<div style="margin:0 auto;max-width:360px">'
            f'<div class="dot-grid" style="grid-template-columns:repeat(11,1fr);gap:6px">'
            f'{"".join(dots)}'
            f'</div>'
            f'<div style="display:flex;justify-content:center;gap:20px;margin-top:10px;font:600 11px Inter">{legend}</div>'
            f'</div>'
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
            # Smaller font if value is long
            if len(str(k.get("value", ""))) > 5:
                kv_style += ";font-size:18px"
            delta = k.get("delta", "")
            delta_html = ""
            if delta:
                delta_color = k.get("delta_color", "var(--muted)")
                delta_html = f'<div class="kd" style="color:{delta_color}">{escape(str(delta))}</div>'
            kpi_items.append(
                f'<div class="kpi" style="border-color:{bc}">'
                f'<div class="kl">{kl}</div>'
                f'<div class="kv" style="{kv_style}">{kv}</div>'
                f'{delta_html}'
                f'</div>'
            )
        cols = f"repeat({kpi_columns},1fr)"
        kpi_html = (
            f'<div class="kpi-grid" style="grid-template-columns:{cols}">'
            f'{"".join(kpi_items)}'
            f'</div>'
        )

    # Insight
    insight_html = ""
    if insight:
        ic = f" {insight_color}" if insight_color else ""
        insight_html = f'<div class="insight{ic}">{escape(insight)}</div>'

    # Source
    source_html = ""
    if source:
        source_html = f'<p class="src">{escape(source)}</p>'

    return f'''<div class="card" id="{card_id}">
<div class="card-inner">
<p class="label {label_color}" style="margin-bottom:12px">{label}</p>
<h3 class="card-title">{title}</h3>
{sub_html}
{hero_html}
{dot_html}
{extra_html}
{kpi_html}
{insight_html}
{source_html}
</div>
</div>'''

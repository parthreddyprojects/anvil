"""
Checklist card — numbered action items with deadlines.

Expected data keys:
  card_id:      str
  title:        str
  subtitle:     str (optional)
  label:        str
  label_color:  str
  items:        list of {action, deadline}
  urgency_kpis: list of {label, value, delta, color, border_color} (optional — shown above checklist)
  insight:      str (optional)
  source:       str (optional)
"""

from html import escape


def render_checklist(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = data.get("subtitle", "")
    label = escape(data.get("label", "Action Required"))
    label_color = data.get("label_color", "red")
    items = data.get("items", [])
    urgency_kpis = data.get("urgency_kpis", [])
    insight = data.get("insight", "")
    source = data.get("source", "")

    sub_html = ""
    if subtitle:
        sub_html = f'<p class="card-sub" style="margin-bottom:20px">{escape(subtitle)}</p>'

    # Urgency KPIs above checklist
    kpi_html = ""
    if urgency_kpis:
        kpi_items = []
        for k in urgency_kpis:
            bc = k.get("border_color", k.get("color", "var(--dim)"))
            kl = escape(str(k.get("label", "")))
            kv = escape(str(k.get("value", "")))
            kv_color = k.get("color", "var(--text)")
            countdown_class = " countdown" if k.get("countdown") else ""
            delta = k.get("delta", "")
            delta_html = ""
            if delta:
                delta_html = f'<div class="kd" style="color:var(--muted)">{escape(str(delta))}</div>'
            kpi_items.append(
                f'<div class="kpi" style="border-color:{bc}">'
                f'<div class="kl">{kl}</div>'
                f'<div class="kv{countdown_class}" style="color:{kv_color}">{kv}</div>'
                f'{delta_html}'
                f'</div>'
            )
        kpi_html = (
            f'<div class="kpi-grid" style="grid-template-columns:1fr 1fr;margin-bottom:20px">'
            f'{"".join(kpi_items)}'
            f'</div>'
        )

    # Checklist items
    cl_items = []
    for i, item in enumerate(items, 1):
        action = escape(item.get("action", ""))
        deadline = escape(item.get("deadline", ""))
        cl_items.append(
            f'<div class="cl-item">'
            f'<div class="cl-num">{i}</div>'
            f'<div class="cl-content">'
            f'<div class="cl-action">{action}</div>'
            f'<div class="cl-deadline">{deadline}</div>'
            f'</div>'
            f'</div>'
        )

    insight_html = ""
    if insight:
        insight_html = f'<div class="insight">{escape(insight)}</div>'

    source_html = ""
    if source:
        source_html = f'<p class="src">{escape(source)}</p>'

    return f'''<div class="card" id="{card_id}">
<div class="card-inner">
<p class="label {label_color}" style="margin-bottom:12px">{label}</p>
<h3 class="card-title">{title}</h3>
{sub_html}
{kpi_html}
<div class="checklist">
{"".join(cl_items)}
</div>
{insight_html}
{source_html}
</div>
</div>'''

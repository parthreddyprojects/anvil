"""
Domino row — falling domino stats card.

Expected data keys:
  card_id:      str
  title:        str
  subtitle:     str (optional)
  label:        str
  label_color:  str
  items:        list of {value, label, color, highlight}
    highlight: bool — if True, uses darker background (#1a0000)
  insight:      str (optional)
  insight_color: str (optional)
  source:       str (optional)
  extra_html:   str (optional — content above the dominoes, e.g. a chart panel)
"""

from html import escape


def render_domino_row(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = data.get("subtitle", "")
    label = escape(data.get("label", ""))
    label_color = data.get("label_color", "")
    items = data.get("items", [])
    insight = data.get("insight", "")
    insight_color = data.get("insight_color", "")
    source = data.get("source", "")
    extra_html = data.get("extra_html", "")

    sub_html = ""
    if subtitle:
        sub_html = f'<p class="card-sub" style="margin-bottom:20px">{escape(subtitle)}</p>'

    domino_items = []
    for d in items:
        color = d.get("color", "var(--text)")
        val = escape(str(d.get("value", "")))
        lbl = d.get("label", "")  # allow HTML in label
        highlight = d.get("highlight", False)
        bg = ";background:#1a0000" if highlight else ""
        domino_items.append(
            f'<div class="domino" style="border-color:{color}{bg}">'
            f'<div class="d-val" style="color:{color}">{val}</div>'
            f'<div class="d-name">{lbl}</div>'
            f'</div>'
        )

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
{extra_html}
<div class="dominoes">
{"".join(domino_items)}
</div>
{insight_html}
{source_html}
</div>
</div>'''

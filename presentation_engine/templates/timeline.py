"""
Timeline card — animated timeline with pulsing dots.

Expected data keys:
  card_id:  str
  title:    str
  label:    str  — small label text above title
  items:    list of {date, text, phase}  — phase 1 = amber, phase 2 = red
  insight:  str (optional)
  source:   str (optional)
"""

from html import escape


def render_timeline(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    label = escape(data.get("label", "Timeline"))
    label_color = data.get("label_color", "red")
    items = data.get("items", [])
    insight = data.get("insight", "")
    source = data.get("source", "")

    tl_items = []
    for item in items:
        phase = item.get("phase", 2)
        css_class = "tl-item amber" if phase == 1 else "tl-item"
        date_text = escape(str(item.get("date", "")))
        text = item.get("text", "")  # Allow HTML in text (bold etc.)
        tl_items.append(
            f'<div class="{css_class}">'
            f'<div class="tl-time">{date_text}</div>'
            f'<div class="tl-text">{text}</div>'
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
<div class="timeline">
{"".join(tl_items)}
</div>
{insight_html}
{source_html}
</div>
</div>'''

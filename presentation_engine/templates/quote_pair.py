"""
Quote pair — two opposing quotes side by side.

Expected data keys:
  card_id:    str
  title:      str (optional — headline above quotes)
  subtitle:   str (optional)
  label:      str
  label_color: str
  quote1:     {text, attr, color}
  quote2:     {text, attr, color}
  extra_html: str (optional — content below quotes, e.g. a chart or dominoes)
  insight:    str (optional)
  insight_color: str (optional)
  source:     str (optional)
"""

from html import escape


def _quote_box(q: dict) -> str:
    text = escape(q.get("text", ""))
    attr = escape(q.get("attr", ""))
    color = q.get("color", "var(--red)")
    # Map CSS var to rgba for background
    bg_map = {
        "var(--red)": "rgba(255,59,59,.08)",
        "var(--blue)": "rgba(59,130,246,.08)",
        "var(--green)": "rgba(52,211,153,.08)",
        "var(--amber)": "rgba(255,176,32,.08)",
    }
    bg = bg_map.get(color, "rgba(255,59,59,.08)")
    return (
        f'<div class="quote-box" style="background:{bg};border-left:3px solid {color}">'
        f'<div class="q-text" style="color:var(--text)">"{text}"</div>'
        f'<div class="q-attr" style="color:{color}">{attr}</div>'
        f'</div>'
    )


def render_quote_pair(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = data.get("title", "")
    subtitle = data.get("subtitle", "")
    label = escape(data.get("label", ""))
    label_color = data.get("label_color", "")
    quote1 = data.get("quote1", {})
    quote2 = data.get("quote2", {})
    extra_html = data.get("extra_html", "")
    insight = data.get("insight", "")
    insight_color = data.get("insight_color", "")
    source = data.get("source", "")

    title_html = ""
    if title:
        title_html = f'<h3 class="card-title">{escape(title)}</h3>'

    sub_html = ""
    if subtitle:
        sub_html = f'<p class="card-sub" style="margin-bottom:20px">{escape(subtitle)}</p>'

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
{title_html}
{sub_html}
<div class="grid-2" style="margin-bottom:20px">
{_quote_box(quote1)}
{_quote_box(quote2)}
</div>
{extra_html}
{insight_html}
{source_html}
</div>
</div>'''

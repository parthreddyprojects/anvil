"""
Verdict panel — the approved Card 7 pattern.
Gradient verdict banner + proof content below, per section.

Expected data keys:
  card_id:    str
  title:      str
  subtitle:   str (optional)
  label:      str
  label_color: str
  sections:   list of {
    source:       str — name in banner left
    verdict_text: str — message in banner right
    verdict_bg:   str — CSS gradient for banner
    content_html: str — raw HTML for proof body
  }
  insight:    str (optional)
  insight_color: str (optional)
  source:     str (optional)
"""

from html import escape


def render_verdict_panel(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = data.get("subtitle", "")
    label = escape(data.get("label", ""))
    label_color = data.get("label_color", "")
    sections = data.get("sections", [])
    insight = data.get("insight", "")
    insight_color = data.get("insight_color", "")
    source = data.get("source", "")

    sub_html = ""
    if subtitle:
        sub_html = f'<p class="card-sub" style="margin-bottom:16px">{escape(subtitle)}</p>'

    panels = []
    for sec in sections:
        src = escape(sec.get("source", ""))
        msg = escape(sec.get("verdict_text", ""))
        bg = sec.get("verdict_bg", "linear-gradient(90deg,#dc2626,#991b1b)")
        content = sec.get("content_html", "")
        panels.append(
            f'<div class="source-panel" style="margin-bottom:10px">'
            f'<div class="verdict" style="background:{bg}">'
            f'<div class="v-source">{src}</div>'
            f'<div class="v-msg">{msg}</div>'
            f'</div>'
            f'<div class="panel-body">{content}</div>'
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
{"".join(panels)}
{insight_html}
{source_html}
</div>
</div>'''

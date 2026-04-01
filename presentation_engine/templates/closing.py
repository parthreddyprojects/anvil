"""
Closing card — deadline timeline + closing line.

Expected data keys:
  card_id:      str
  title:        str  (headline)
  label:        str  (small label above title)
  label_color:  str
  deadlines:    list of {date, text, color}
  closing_line: str  — bold final sentence
  closing_sub:  str  — muted line below closing
  source:       str  (optional — bottom attribution)
"""

from html import escape


def render_closing(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    label = escape(data.get("label", "Closing Brief"))
    label_color = data.get("label_color", "red")
    deadlines = data.get("deadlines", [])
    closing_line = escape(data.get("closing_line", ""))
    closing_sub = escape(data.get("closing_sub", ""))
    source = data.get("source", "")

    # Deadline rows
    dl_items = []
    for i, dl in enumerate(deadlines):
        date_text = escape(str(dl.get("date", "")))
        text = escape(dl.get("text", ""))
        color = dl.get("color", "var(--red)")
        border = "" if i == len(deadlines) - 1 else "border-bottom:1px solid rgba(255,255,255,.08);"
        dl_items.append(
            f'<div style="display:flex;gap:12px;align-items:baseline;padding:12px 0;{border}">'
            f'<div class="mono" style="font:800 20px JetBrains Mono;color:{color};min-width:50px">{date_text}</div>'
            f'<div style="font:400 13px/1.4 Inter;color:var(--text)">{text}</div>'
            f'</div>'
        )

    closing_html = ""
    if closing_line:
        closing_html = (
            f'<div style="max-width:460px;margin:28px auto 0;text-align:center">'
            f'<p style="font:600 15px/1.5 Inter;color:var(--text)">{closing_line}</p>'
        )
        if closing_sub:
            closing_html += (
                f'<p style="font:400 13px/1.5 Inter;color:var(--muted);margin-top:8px">{closing_sub}</p>'
            )
        closing_html += "</div>"

    source_html = ""
    if source:
        source_html = f'<p class="src" style="margin-top:28px">{escape(source)}</p>'

    return f'''<div class="card" id="{card_id}" style="background:radial-gradient(ellipse at 50% 50%,#1a0000,#0a0a0a)">
<div class="card-inner">
<p class="label {label_color}" style="margin-bottom:20px">{label}</p>
<h3 class="card-title" style="font-size:26px;max-width:480px;margin:0 auto 28px">{title}</h3>
<div style="max-width:460px;margin:0 auto;text-align:left">
{"".join(dl_items)}
</div>
{closing_html}
{source_html}
</div>
</div>'''

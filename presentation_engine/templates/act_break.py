"""
Act break — section transition card.

Expected data keys:
  card_id:  str
  title:    str  — large centered headline
  subtitle: str  — supporting text below
  symbol:   str  — large background character (e.g. "II", "III", a symbol)
  label:    str  — small red label above title (default: section title)
"""

from html import escape


def render_act_break(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = escape(data.get("subtitle", ""))
    symbol = escape(data.get("symbol", ""))
    label_text = escape(data.get("label", ""))

    label_html = ""
    if label_text:
        label_html = f'<p class="act-title">{label_text}</p>'

    sub_html = ""
    if subtitle:
        sub_html = (
            f'<p class="card-sub" style="text-align:center;max-width:400px;margin:0 auto">'
            f'{subtitle}</p>'
        )

    # Use smaller font for emoji/special symbols (they render wider)
    symbol_style = ""
    if symbol and not symbol[0].isalnum():
        symbol_style = ' style="font-size:80px"'

    return f'''<div class="card act-card" id="{card_id}">
<div class="card-inner">
{label_html}
<h3 class="card-title" style="font-size:36px">{title}</h3>
{sub_html}
</div>
<div class="act-num"{symbol_style}>{symbol}</div>
</div>'''

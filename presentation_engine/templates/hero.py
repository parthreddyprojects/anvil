"""
Hero card — opening card with big numbers, pulsing background, stat row.

Expected data keys:
  card_id:    str  — e.g. "c1"
  title:      str  — large gradient headline
  subtitle:   str  — one-liner below the hero number
  stats:      list of {value, label, color}
  badge_text: str  — e.g. "ZERO NEGOTIATIONS ACTIVE"
  hero_value: str  — big number in center (optional, e.g. "DAY 20")
  hero_color: str  — CSS color for hero number (default: var(--red))
  label_text: str  — small uppercase label at top
"""

from html import escape


def render_hero(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = escape(data.get("subtitle", ""))
    stats = data.get("stats", [])
    badge_text = data.get("badge_text", "")
    hero_value = data.get("hero_value", "")
    hero_color = data.get("hero_color", "var(--red)")
    label_text = escape(data.get("label_text", "STRATEGIC INTELLIGENCE BRIEFING"))

    # Stats row
    stats_html = ""
    if stats:
        stat_items = []
        for s in stats:
            color = s.get("color", "var(--red)")
            val = escape(str(s.get("value", "")))
            lbl = escape(str(s.get("label", "")))
            stat_items.append(
                f'<div class="stat">'
                f'<div class="val" style="color:{color}">{val}</div>'
                f'<div class="lbl">{lbl}</div>'
                f'</div>'
            )
        stats_html = f'<div class="stat-row">{"".join(stat_items)}</div>'

    # Badge
    badge_html = ""
    if badge_text:
        badge_html = (
            f'<div style="margin-top:20px;padding:6px 16px;background:var(--red);'
            f'border-radius:4px;display:inline-block">'
            f'<span class="mono" style="font-size:11px;font-weight:700;color:#fff;'
            f'letter-spacing:1px">{escape(badge_text)}</span></div>'
        )

    # Hero number
    hero_html = ""
    if hero_value:
        hero_html = (
            f'<div class="hero-num" style="color:{hero_color}">'
            f'{escape(hero_value)}</div>'
        )

    return f'''<div class="card" id="{card_id}" style="background:radial-gradient(ellipse at 50% 60%,#1a0000,#0a0a0a)">
<div class="card-inner">
<p class="label" style="color:var(--red);margin-bottom:16px"><span class="countdown">{label_text}</span></p>
<h1 style="font:900 44px/1 'Inter';background:linear-gradient(135deg,var(--red),var(--amber));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:24px">{title}</h1>
{hero_html}
<p class="card-sub" style="margin-top:8px;margin-bottom:28px">{subtitle}</p>
{stats_html}
{badge_html}
<div class="swipe-hint">scroll</div>
</div>
</div>'''

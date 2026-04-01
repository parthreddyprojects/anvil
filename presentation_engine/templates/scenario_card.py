"""
Scenario card — full-bleed scenario cards with gradient borders.

Expected data keys:
  card_id:    str
  title:      str
  label:      str
  label_color: str
  scenarios:  list of {
    probability: str  — e.g. "35-40%"
    title:       str
    color:       str  — CSS color (var(--amber), var(--red), var(--green))
    stats:       list of {value, label}
    insight:     str
  }
  insight:    str (optional — card-level insight below all scenarios)
  source:     str (optional)
"""

from html import escape


# Map CSS var names to RGBA for gradients
_COLOR_RGBA = {
    "var(--amber)": ("rgba(255,176,32,", "#ffb020"),
    "var(--red)": ("rgba(255,59,59,", "#ff3b3b"),
    "var(--green)": ("rgba(52,211,153,", "#34d399"),
    "var(--blue)": ("rgba(59,130,246,", "#3b82f6"),
    "var(--purple)": ("rgba(167,139,250,", "#a78bfa"),
}


def _scenario_bg(color: str) -> str:
    """Generate the gradient background + border for a scenario card."""
    rgba_base, _ = _COLOR_RGBA.get(color, ("rgba(255,59,59,", "#ff3b3b"))
    return (
        f"background:linear-gradient(135deg,{rgba_base}.2),{rgba_base}.05));"
        f"border:1px solid {rgba_base}.3)"
    )


def _scenario_label_color(color: str) -> str:
    rgba_base, _ = _COLOR_RGBA.get(color, ("rgba(255,59,59,", "#ff3b3b"))
    return f"{rgba_base}.6)"


def render_scenario_card(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    label = escape(data.get("label", "Scenario Planning"))
    label_color = data.get("label_color", "")
    scenarios = data.get("scenarios", [])
    insight = data.get("insight", "")
    source = data.get("source", "")

    scenario_items = []
    for sc in scenarios:
        color = sc.get("color", "var(--red)")
        prob = escape(str(sc.get("probability", "")))
        sc_title = escape(sc.get("title", ""))
        sc_insight = escape(sc.get("insight", ""))
        label_c = _scenario_label_color(color)

        # Stats
        stats_html = ""
        if sc.get("stats"):
            stat_items = []
            for st in sc["stats"]:
                sv = escape(str(st.get("value", "")))
                sl = escape(str(st.get("label", "")))
                stat_items.append(
                    f'<div class="sc-stat">'
                    f'<div class="ss-v" style="color:{color}">{sv}</div>'
                    f'<div class="ss-l">{sl}</div>'
                    f'</div>'
                )
            stats_html = f'<div class="sc-stats">{"".join(stat_items)}</div>'

        insight_line = ""
        if sc_insight:
            insight_line = f'<div class="sc-insight">{sc_insight}</div>'

        bg_style = _scenario_bg(color)
        scenario_items.append(
            f'<div class="scenario-card" style="{bg_style}">'
            f'<div style="font:600 9px Inter;text-transform:uppercase;letter-spacing:1.5px;color:{label_c};margin-bottom:4px">Probability</div>'
            f'<div class="sc-prob" style="color:{color}">{prob}</div>'
            f'<div class="sc-title" style="color:{color}">{sc_title}</div>'
            f'{stats_html}'
            f'{insight_line}'
            f'</div>'
        )

    card_insight = ""
    if insight:
        card_insight = f'<div class="insight">{escape(insight)}</div>'

    source_html = ""
    if source:
        source_html = f'<p class="src">{escape(source)}</p>'

    return f'''<div class="card" id="{card_id}">
<div class="card-inner">
<p class="label {label_color}" style="margin-bottom:12px">{label}</p>
<h3 class="card-title">{title}</h3>
{"".join(scenario_items)}
{card_insight}
{source_html}
</div>
</div>'''

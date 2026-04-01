"""
Map card — Leaflet map with numbered circle markers + legend.

Expected data keys:
  card_id:    str
  title:      str
  subtitle:   str (optional)
  label:      str
  label_color: str
  map_id:     str  — unique DOM id for the map div
  center:     [lat, lng]
  zoom:       int
  markers:    list of {lat, lng, number, label, color}
    color should be a hex like #dc2626, #d97706, #16a34a
  circles:    list of {lat, lng, radius, color, fill_opacity, dash} (optional)
  polylines:  list of {points: [[lat,lng],...], color, dash} (optional)
  text_labels: list of {lat, lng, text, css_class} (optional)
  kpis:       list of KPI dicts (optional)
  kpi_columns: int (default 3)
  dominoes:   list of domino dicts (optional)
  insight:    str (optional)
  insight_color: str (optional)
  source:     str (optional)
"""

import json
from html import escape


def render_map_card(data: dict) -> str:
    card_id = data.get("card_id", "c0")
    title = escape(data.get("title", ""))
    subtitle = data.get("subtitle", "")
    label = escape(data.get("label", ""))
    label_color = data.get("label_color", "")
    map_id = data.get("map_id", f"map-{card_id}")
    insight = data.get("insight", "")
    insight_color = data.get("insight_color", "")
    source = data.get("source", "")
    kpis = data.get("kpis", [])
    kpi_columns = data.get("kpi_columns", 3)
    dominoes = data.get("dominoes", [])

    sub_html = ""
    if subtitle:
        sub_html = f'<p class="card-sub" style="margin-bottom:16px">{escape(subtitle)}</p>'

    # KPI grid
    kpi_html = ""
    if kpis:
        kpi_items = []
        for k in kpis:
            bc = k.get("border_color", k.get("color", "var(--dim)"))
            kl = escape(str(k.get("label", "")))
            kv = escape(str(k.get("value", "")))
            kv_color = k.get("color", "var(--text)")
            delta = k.get("delta", "")
            delta_html = ""
            if delta:
                dc = k.get("delta_color", k.get("color", "var(--muted)"))
                delta_html = f'<div class="kd" style="color:{dc}">{escape(str(delta))}</div>'
            kpi_items.append(
                f'<div class="kpi" style="border-color:{bc}">'
                f'<div class="kl">{kl}</div>'
                f'<div class="kv" style="color:{kv_color}">{kv}</div>'
                f'{delta_html}'
                f'</div>'
            )
        cols = f"repeat({kpi_columns},1fr)"
        kpi_html = f'<div class="kpi-grid" style="grid-template-columns:{cols};margin-top:12px">{"".join(kpi_items)}</div>'

    # Dominoes
    domino_html = ""
    if dominoes:
        items = []
        for d in dominoes:
            color = d.get("color", "var(--text)")
            val = escape(str(d.get("value", "")))
            lbl = d.get("label", "")
            items.append(
                f'<div class="domino" style="border-color:{color}">'
                f'<div class="d-val" style="color:{color}">{val}</div>'
                f'<div class="d-name">{lbl}</div>'
                f'</div>'
            )
        domino_html = f'<div class="dominoes">{"".join(items)}</div>'

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
<div id="{map_id}" class="map-c" style="height:280px;margin-bottom:12px"></div>
{kpi_html}
{domino_html}
{insight_html}
{source_html}
</div>
</div>'''


def map_init_script(data: dict) -> str:
    """Return a JS IIFE that initializes the Leaflet map for this card."""
    map_id = data.get("map_id", f"map-{data.get('card_id', 'c0')}")
    center = data.get("center", [25, 56])
    zoom = data.get("zoom", 5)
    markers = data.get("markers", [])
    circles = data.get("circles", [])
    polylines = data.get("polylines", [])
    text_labels = data.get("text_labels", [])

    lines = [
        f"(function(){{",
        f"var m=L.map('{map_id}',{{zoomControl:false,attributionControl:false,dragging:false,scrollWheelZoom:false}}).setView([{center[0]},{center[1]}],{zoom});",
        f"L.tileLayer(TILE).addTo(m);",
    ]

    # Numbered circle markers (HARD RULE: only numbered circles on map)
    for mk in markers:
        lat = mk["lat"]
        lng = mk["lng"]
        num = mk.get("number", "")
        color = mk.get("color", "#dc2626")
        lines.append(
            f"L.marker([{lat},{lng}],{{icon:L.divIcon({{className:'',"
            f"html:'<div style=\"width:24px;height:24px;background:{color};border-radius:50%;display:flex;align-items:center;justify-content:center;font:800 12px JetBrains Mono;color:#fff\">{num}</div>',"
            f"iconSize:[24,24],iconAnchor:[12,12]}})}})"
            f".addTo(m);"
        )

    # Circles (zones)
    for c in circles:
        dash = f",dashArray:'{c['dash']}'" if c.get("dash") else ""
        lines.append(
            f"L.circle([{c['lat']},{c['lng']}],{{radius:{c['radius']},"
            f"color:'{c['color']}',fillColor:'{c['color']}',"
            f"fillOpacity:{c.get('fill_opacity', 0.15)},weight:{c.get('weight', 2)}{dash}}}).addTo(m);"
        )

    # Polylines
    for pl in polylines:
        pts = json.dumps(pl["points"])
        dash = f",dashArray:'{pl['dash']}'" if pl.get("dash") else ""
        lines.append(
            f"L.polyline({pts},{{color:'{pl['color']}',weight:{pl.get('weight', 2)}{dash},"
            f"opacity:{pl.get('opacity', 0.5)}}}).addTo(m);"
        )

    # Text labels
    for tl in text_labels:
        css = tl.get("css_class", "")
        label_cls = f"map-label {css}".strip()
        txt = tl.get("text", "")
        w = tl.get("width", 100)
        lines.append(
            f"L.marker([{tl['lat']},{tl['lng']}],{{icon:ml('{txt}','{css}',{w})}}).addTo(m);"
        )

    lines.append("})();")
    return "\n".join(lines)

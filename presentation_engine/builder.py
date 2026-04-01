"""
Builder — assembles HTML briefing from card_html.json.

Reads a card_html.json (complete HTML per card from the Design Agent),
concatenates all cards, wraps in a standard HTML shell with CDN links
and inline dna.css, adds progress bar + card counter + scroll script.

This is intentionally simple: ~50 lines of core logic. The Design Agent
does all the visual work. The builder just wraps it.
"""

import json
import os
from pathlib import Path


# ── Paths ─────────────────────────────────────────────────

_HERE = Path(__file__).parent
CSS_PATH = _HERE / "styles" / "dna.css"


# ── HTML Shell ────────────────────────────────────────────

def _read_css() -> str:
    """Read the dna.css file contents."""
    return CSS_PATH.read_text(encoding="utf-8")


def build_head(title: str = "Strategic Intelligence Briefing") -> str:
    """Return the <html><head> with fonts, Chart.js, Leaflet, and inline CSS."""
    css = _read_css()
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
{css}
</style>
</head>
<body>'''


def build_scroll_script(total_cards: int) -> str:
    """Return the closing <script> block with scroll handler + global defaults."""
    return f'''<script>
// Scroll: progress + counter + in-view animations
(function(){{
var cards=document.querySelectorAll('.card'),
    prog=document.getElementById('prog'),
    ctr=document.getElementById('ctr'),
    t=cards.length;
function u(){{
  var s=window.scrollY||document.documentElement.scrollTop,
      h=document.documentElement.scrollHeight-window.innerHeight,
      p=h>0?(s/h)*100:0;
  prog.style.width=p+'%';
  var c=1;
  cards.forEach(function(x,i){{
    var r=x.getBoundingClientRect();
    if(r.top<window.innerHeight/2) c=i+1;
    if(r.top<window.innerHeight*.8&&r.bottom>0) x.classList.add('in-view');
    else x.classList.remove('in-view');
  }});
  ctr.textContent=c+'/'+t;
}}
window.addEventListener('scroll',u);
u();
}})();

// Global Chart.js defaults
Chart.defaults.font.family='Inter';
Chart.defaults.color='#888';
</script>'''


# ── Main Build ────────────────────────────────────────────

def load_card_html(spec_path: str) -> list[dict]:
    """Load card_html.json and return the list of card dicts with HTML."""
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    # Support both a raw list and a wrapper object with "cards" key
    if isinstance(spec, list):
        return spec
    if isinstance(spec, dict) and "cards" in spec:
        return spec["cards"]

    raise ValueError(
        "card_html.json must be a JSON array of card objects, "
        "or an object with a 'cards' key containing that array."
    )


def build_briefing(card_html_path: str, output_path: str, title: str = None):
    """
    Main entry point: reads card_html.json, concatenates all card HTML,
    wraps in shell, writes to output_path.
    """
    cards = load_card_html(card_html_path)

    if not cards:
        raise ValueError("card_html.json contains no cards.")

    total = len(cards)

    # Determine title from first hero card or use default
    if title is None:
        for card in cards:
            if card.get("card_type") == "hero":
                # Try to extract title from the HTML itself
                html = card.get("html", "")
                # Simple extraction: look for card-title content
                import re
                m = re.search(r'class="card-title"[^>]*>([^<]+)', html)
                if m:
                    title = m.group(1).strip()
                    break
        if title is None:
            title = "Strategic Intelligence Briefing"

    # Build HTML
    html_parts = []
    html_parts.append(build_head(title))
    html_parts.append(f'<div class="progress" id="prog"></div>')
    html_parts.append(f'<div class="card-counter" id="ctr">1/{total}</div>')

    # Concatenate all card HTML blocks
    for i, card in enumerate(cards):
        card_html = card.get("html", "")
        if not card_html:
            card_id = card.get("card_id", f"c{i+1}")
            print(f"  WARNING: Card {card_id} has empty HTML, skipping.")
            continue
        html_parts.append(f"\n<!-- ===== CARD {i+1}: {card.get('card_id', '?')} ({card.get('card_type', '?')}) ===== -->")
        html_parts.append(card_html)

    html_parts.append(build_scroll_script(total))
    html_parts.append("</body>\n</html>")

    # Write output
    output = "\n".join(html_parts)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"  Built {total} cards -> {output_path} ({len(output):,} chars)")
    return output_path

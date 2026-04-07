#!/usr/bin/env python3
"""
ANVIL Carousel Generator
=========================
Takes a completed Anvil run and generates a LinkedIn carousel (PDF-ready HTML).

Usage:
    python carousel.py <run_dir>
    python carousel.py <run_dir> --no-review   (skip LLM reviews)

Structure:
    1. Problem Statement (hook slide)
    2. Governing Hypothesis (the answer)
    3-N. Sub-hypotheses (one per primary, with verdict)
    N+1. What data is still needed
    N+2. Built by Anvil / developed by Parth Reddy
"""

import json
import sys
import io
import os
import webbrowser
from pathlib import Path
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent
TODAY_STR = date.today().strftime("%B %d, %Y")

# Anvil palette
AMBER = "#F5A623"
AMBER_DIM = "#9B6A14"
AMBER_BRIGHT = "#FFD080"
BG = "#0C0C0C"
WHITE = "#EFEFEF"
DARK = "#1A1A1A"
RED = "#EF4444"
GREEN = "#22C55E"

VERDICT_COLORS = {
    "GREEN": GREEN,
    "CONFIRMED": GREEN,
    "RED": RED,
    "KILLED": RED,
    "AMBER": AMBER,
    "UNCERTAIN": AMBER,
}

# ── Anvil logo SVG (inline) ──
ANVIL_LOGO_SVG = f'''<svg viewBox="0 0 120 100" xmlns="http://www.w3.org/2000/svg" width="120" height="100">
  <!-- Anvil body -->
  <path d="M20 55 L100 55 L95 70 L85 70 L85 80 L35 80 L35 70 L25 70 Z" fill="{AMBER}" opacity="0.9"/>
  <!-- Anvil horn -->
  <path d="M55 55 L55 40 L75 40 L100 35 L100 45 L75 45 L75 55 Z" fill="{AMBER_BRIGHT}" opacity="0.8"/>
  <!-- Anvil base -->
  <rect x="30" y="80" width="60" height="8" rx="2" fill="{AMBER_DIM}"/>
  <!-- Hammer -->
  <rect x="48" y="10" width="4" height="30" rx="1" fill="{AMBER_DIM}" transform="rotate(-15 50 25)"/>
  <rect x="38" y="5" width="24" height="12" rx="3" fill="{AMBER}" transform="rotate(-15 50 11)"/>
  <!-- Spark -->
  <circle cx="42" cy="42" r="2" fill="{AMBER_BRIGHT}" opacity="0.8"/>
  <circle cx="36" cy="38" r="1.5" fill="{AMBER_BRIGHT}" opacity="0.6"/>
  <circle cx="45" cy="36" r="1" fill="{AMBER_BRIGHT}" opacity="0.5"/>
</svg>'''


def _load_run(run_dir):
    """Load all data from a completed run."""
    run = Path(run_dir)
    data = {}

    # State
    state_path = run / "state.json"
    if state_path.exists():
        data["state"] = json.load(open(state_path, encoding="utf-8"))

    # MECE (for PS and break point)
    mece_path = data.get("state", {}).get("mece_path", "")
    if mece_path and Path(mece_path).exists():
        data["mece"] = json.load(open(mece_path, encoding="utf-8"))
    else:
        # Try default location
        default_mece = run / "mece" / "decomposition.json"
        if default_mece.exists():
            data["mece"] = json.load(open(default_mece, encoding="utf-8"))

    # Hypotheses
    hyp_path = data.get("state", {}).get("hyp_path", "")
    if hyp_path and Path(hyp_path).exists():
        data["hypotheses"] = json.load(open(hyp_path, encoding="utf-8"))
    else:
        default_hyp = run / "hypotheses" / "hypotheses.json"
        if default_hyp.exists():
            data["hypotheses"] = json.load(open(default_hyp, encoding="utf-8"))

    return data


def _build_slides(data):
    """Build carousel slide content from run data."""
    mece = data.get("mece", {})
    hyp = data.get("hypotheses", {})
    state = data.get("state", {})

    ps = mece.get("smart_statement", state.get("topic", ""))
    sens = mece.get("decision_sensitivity", "")
    governing = hyp.get("governing_hypothesis", "")
    hypotheses = hyp.get("hypotheses", [])
    graveyard = hyp.get("graveyard", [])

    slides = []

    # Slide 1: Problem Statement (hook)
    slides.append({
        "type": "problem",
        "headline": "THE QUESTION",
        "body": ps,
        "footer": sens[:120] if sens else "",
    })

    # Slide 2: Governing Hypothesis (the answer)
    slides.append({
        "type": "answer",
        "headline": "THE ANSWER",
        "body": governing,
        "footer": f"{len([h for h in hypotheses if h.get('status') != 'killed'])} conditions confirmed  ·  {len(graveyard)} killed",
    })

    # Slides 3-N: Sub-hypotheses (active ones)
    active = [h for h in hypotheses if h.get("status") != "killed"]
    for h in active:
        status = h.get("status", "uncertain").upper()
        leaves = h.get("sub_hypotheses", [])
        leaf_summary = []
        for sh in leaves:
            v = sh.get("verdict", "?")
            leaf_summary.append(f"{v}  {sh.get('statement', '')[:60]}")

        slides.append({
            "type": "hypothesis",
            "headline": h.get("statement", ""),
            "status": status,
            "leaves": leaf_summary,
            "id": h.get("id", ""),
        })

    # Data needed slide
    gaps = []
    for h in hypotheses:
        for sh in h.get("sub_hypotheses", []):
            if sh.get("verdict", "").upper() == "AMBER":
                missing = sh.get("what_is_missing", "")
                if missing:
                    gaps.append(missing[:80])
    if gaps:
        slides.append({
            "type": "gaps",
            "headline": "TO COMPLETE THIS ANALYSIS",
            "items": gaps[:6],
        })

    # Closing slide
    slides.append({
        "type": "closing",
        "headline": "ANVIL",
        "body": "strategic problem engine",
    })

    return slides


def _llm_review(slides, review_type="partner"):
    """Run LLM review on carousel content."""
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        print("  [skip] Anthropic not available — skipping review")
        return slides

    slides_text = json.dumps(slides, indent=2, ensure_ascii=False)

    if review_type == "partner":
        prompt = f"""You are a senior strategy partner reviewing a LinkedIn carousel before it goes live.

The carousel summarizes a strategic analysis. Review it for:

1. **Story flow** — Does slide 1 hook? Does the answer follow logically? Do the sub-hypotheses build the case?
2. **Redundancy** — Any slide that repeats another should be cut or merged.
3. **Rigor** — Any claim without a specific number, date, or source? Flag it.
4. **So what** — Would a CEO stop scrolling? Is the insight non-obvious?
5. **Headlines** — Each headline must be a CLAIM, not a topic. "Oil prices will rise" not "Oil market analysis".

For each slide, suggest a REVISED headline and body if needed. Keep it punchy — max 15 words per headline, max 40 words per body.

CAROUSEL SLIDES:
{slides_text}

Return JSON: {{"reviewed_slides": [...same structure with improved headlines/bodies...], "cuts": ["slide indices to remove"], "notes": "overall feedback"}}"""
    else:
        prompt = f"""You are a LinkedIn content manager reviewing a carousel for maximum engagement.

Review for:
1. **Hook** — Slide 1 must make someone stop scrolling. Is it a question? A bold claim? A surprising number?
2. **Readability** — Each slide should be readable in 3 seconds. Too many words = skip.
3. **Flow** — Does each slide make you want to see the next one? Build tension.
4. **CTA** — Does the last slide drive action (follow, comment, save)?
5. **Visual weight** — Headlines should be 5-10 words. Body should be 20-30 words max.

IMPORTANT: This is a PROFESSIONAL strategy carousel, not clickbait. The audience is senior executives and strategists. Tone: confident, direct, no fluff.

CAROUSEL SLIDES:
{slides_text}

Return JSON: {{"reviewed_slides": [...same structure with engagement-optimized text...], "notes": "overall feedback"}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        # Extract JSON
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            result = json.loads(match.group())
            reviewed = result.get("reviewed_slides", slides)
            notes = result.get("notes", "")
            if notes:
                print(f"  Review: {notes[:200]}")
            return reviewed
    except Exception as e:
        print(f"  [skip] Review failed: {e}")

    return slides


def _render_html(slides):
    """Render slides as PDF-ready HTML (1080x1080 per slide)."""

    def _verdict_dot(status):
        color = VERDICT_COLORS.get(status.upper(), AMBER)
        return f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:8px;vertical-align:middle"></span>'

    slide_html = []

    for i, s in enumerate(slides):
        stype = s.get("type", "")

        if stype == "problem":
            content = f'''
            <div class="slide-number">{i+1}/{len(slides)}</div>
            <div class="label">THE QUESTION</div>
            <div class="ps">{s["body"]}</div>
            <div class="break-point">{s.get("footer", "")}</div>
            '''

        elif stype == "answer":
            content = f'''
            <div class="slide-number">{i+1}/{len(slides)}</div>
            <div class="label answer-label">THE ANSWER</div>
            <div class="governing">{s["body"]}</div>
            <div class="stats">{s.get("footer", "")}</div>
            '''

        elif stype == "hypothesis":
            status = s.get("status", "UNCERTAIN")
            status_color = VERDICT_COLORS.get(status, AMBER)
            leaves_html = ""
            for leaf in s.get("leaves", []):
                parts = leaf.split("  ", 1)
                verdict = parts[0] if len(parts) > 1 else "?"
                text = parts[1] if len(parts) > 1 else leaf
                v_color = VERDICT_COLORS.get(verdict.upper(), AMBER)
                leaves_html += f'<div class="leaf"><span class="verdict-dot" style="background:{v_color}"></span>{text}</div>'

            content = f'''
            <div class="slide-number">{i+1}/{len(slides)}</div>
            <div class="hyp-id" style="color:{status_color}">{s.get("id", "")}  ·  {status}</div>
            <div class="hyp-statement">{s["headline"]}</div>
            <div class="leaves">{leaves_html}</div>
            '''

        elif stype == "gaps":
            items_html = "".join(f'<div class="gap-item">▸ {item}</div>' for item in s.get("items", []))
            content = f'''
            <div class="slide-number">{i+1}/{len(slides)}</div>
            <div class="label">TO COMPLETE THIS ANALYSIS</div>
            <div class="gaps">{items_html}</div>
            '''

        elif stype == "closing":
            content = f'''
            <div class="closing-logo">{ANVIL_LOGO_SVG}</div>
            <div class="closing-name">A N V I L</div>
            <div class="closing-tagline">strategic problem engine</div>
            <div class="closing-credit">developed by parth reddy</div>
            '''

        else:
            content = f'<div class="label">{s.get("headline", "")}</div><div class="ps">{s.get("body", "")}</div>'

        slide_html.append(f'<div class="slide">{content}</div>')

    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Anvil Carousel</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    background: #111;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 40px;
    padding: 40px;
    font-family: 'Inter', -apple-system, sans-serif;
}}

.slide {{
    width: 1080px;
    height: 1080px;
    background: {BG};
    border: 1px solid {AMBER_DIM}22;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 100px 90px;
    position: relative;
    overflow: hidden;
    page-break-after: always;
}}

/* Corner accents */
.slide::before {{
    content: '';
    position: absolute;
    top: 40px; left: 40px;
    width: 60px; height: 60px;
    border-top: 2px solid {AMBER_DIM};
    border-left: 2px solid {AMBER_DIM};
}}
.slide::after {{
    content: '';
    position: absolute;
    bottom: 40px; right: 40px;
    width: 60px; height: 60px;
    border-bottom: 2px solid {AMBER_DIM};
    border-right: 2px solid {AMBER_DIM};
}}

.slide-number {{
    position: absolute;
    top: 48px; right: 70px;
    font-size: 14px;
    color: {AMBER_DIM};
    letter-spacing: 2px;
    font-weight: 300;
}}

/* Problem slide */
.label {{
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 6px;
    color: {AMBER};
    margin-bottom: 40px;
    text-align: center;
}}

.ps {{
    font-size: 36px;
    font-weight: 300;
    line-height: 1.4;
    color: {WHITE};
    text-align: center;
    max-width: 800px;
}}

.break-point {{
    margin-top: 50px;
    font-size: 16px;
    color: {AMBER_DIM};
    text-align: center;
    font-style: italic;
    max-width: 700px;
    line-height: 1.5;
}}

/* Answer slide */
.answer-label {{
    color: {AMBER_BRIGHT};
    font-size: 16px;
    letter-spacing: 8px;
}}

.governing {{
    font-size: 42px;
    font-weight: 600;
    line-height: 1.3;
    color: {WHITE};
    text-align: center;
    max-width: 820px;
}}

.stats {{
    margin-top: 50px;
    font-size: 16px;
    color: {AMBER_DIM};
    letter-spacing: 1px;
}}

/* Hypothesis slide */
.hyp-id {{
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 4px;
    margin-bottom: 30px;
    align-self: flex-start;
}}

.hyp-statement {{
    font-size: 32px;
    font-weight: 500;
    line-height: 1.35;
    color: {WHITE};
    align-self: flex-start;
    margin-bottom: 40px;
    max-width: 800px;
}}

.leaves {{
    align-self: flex-start;
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 100%;
}}

.leaf {{
    font-size: 18px;
    color: {WHITE}cc;
    line-height: 1.4;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    background: {WHITE}08;
    border-radius: 6px;
}}

.verdict-dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-top: 6px;
    flex-shrink: 0;
}}

/* Gaps slide */
.gaps {{
    display: flex;
    flex-direction: column;
    gap: 20px;
    align-self: flex-start;
    width: 100%;
}}

.gap-item {{
    font-size: 22px;
    color: {AMBER_BRIGHT};
    line-height: 1.4;
    padding: 14px 0;
    border-bottom: 1px solid {AMBER_DIM}33;
}}

/* Closing slide */
.closing-logo {{
    margin-bottom: 30px;
    opacity: 0.9;
}}
.closing-logo svg {{
    width: 160px;
    height: 130px;
}}
.closing-name {{
    font-size: 48px;
    font-weight: 300;
    letter-spacing: 16px;
    color: {AMBER};
    margin-bottom: 12px;
}}
.closing-tagline {{
    font-size: 18px;
    font-weight: 300;
    letter-spacing: 4px;
    color: {AMBER_DIM};
    margin-bottom: 80px;
}}
.closing-credit {{
    position: absolute;
    bottom: 60px;
    font-size: 12px;
    font-weight: 300;
    letter-spacing: 3px;
    color: {AMBER_DIM}88;
    text-transform: lowercase;
}}

/* Print */
@media print {{
    body {{ background: none; padding: 0; gap: 0; }}
    .slide {{ border: none; }}
}}
</style>
</head>
<body>
{"".join(slide_html)}
</body>
</html>'''

    return html


def generate_carousel(run_dir, skip_review=False):
    """Main entry: load run → build slides → review → render → open."""
    print(f"\n  \033[38;2;245;166;35m▸ Loading run: {run_dir}\033[0m")
    data = _load_run(run_dir)

    if not data.get("hypotheses"):
        print("  \033[91m⚠ No hypotheses found — run must be complete through step 5\033[0m")
        return None

    print(f"  \033[38;2;245;166;35m▸ Building slides...\033[0m")
    slides = _build_slides(data)
    print(f"  \033[38;2;245;166;35m  {len(slides)} slides generated\033[0m")

    if not skip_review:
        # Review 1: MBB Partner
        print(f"  \033[38;2;245;166;35m▸ Review 1: Strategy partner...\033[0m")
        slides = _llm_review(slides, "partner")

        # Review 2: LinkedIn content manager
        print(f"  \033[38;2;245;166;35m▸ Review 2: LinkedIn content manager...\033[0m")
        slides = _llm_review(slides, "linkedin")

    print(f"  \033[38;2;245;166;35m▸ Rendering HTML...\033[0m")
    html = _render_html(slides)

    # Save
    out_dir = Path(run_dir)
    out_path = out_dir / "carousel.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"  \033[38;2;34;197;94m✓ Carousel saved: {out_path}\033[0m")
    print(f"  \033[38;2;155;106;20m  Open in browser → Print → Save as PDF → Upload to LinkedIn\033[0m")

    webbrowser.open(f"file:///{out_path.resolve()}")
    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python carousel.py <run_dir> [--no-review]")
        sys.exit(1)

    run_dir = sys.argv[1]
    skip = "--no-review" in sys.argv
    generate_carousel(run_dir, skip_review=skip)

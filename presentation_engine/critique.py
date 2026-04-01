"""
Critique Pipeline — Gate 1 (MBB content) + Gate 2 (Visual QA) + auto-apply fixes.

Loops until average score >= 7 or max rounds exhausted.
Every card with a data claim must have a .src line (source enforcement).

Usage (standalone):
  python critique.py --file briefing.html
  python critique.py --file briefing.html --gate 1 --rounds 3
  python critique.py --file briefing.html --all --auto-fix

Requires:
  pip install anthropic playwright beautifulsoup4
  playwright install chromium
"""

import argparse
import json
import re
import os
import sys
import time
import base64
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    import anthropic
except ImportError:
    print("pip install anthropic")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("pip install beautifulsoup4")
    sys.exit(1)


# ── Config ──────────────────────────────────────────────

CRITIQUE_MODEL = "claude-opus-4-6"       # Gate 1: expensive, strategic
REWRITE_MODEL = "claude-sonnet-4-6"      # Rewrite: fast, capable
VISUAL_MODEL = "claude-opus-4-6"         # Gate 2: multimodal, expensive
MAX_TOKENS = 16384

GATE1_ROUNDS = 3
SCORE_THRESHOLD = 7   # out of 10 — cards below this get rewritten
KILL_THRESHOLD = 4    # cards below this get flagged for removal
AVG_TARGET = 7        # auto-fix loops until avg >= this


# ── Data Structures ─────────────────────────────────────

@dataclass
class CardContent:
    card_id: str
    index: int
    card_type: str
    headline: str
    subtext: str
    visual_type: str
    stats: list = field(default_factory=list)
    insight: str = ""
    has_source: bool = False
    raw_html: str = ""


@dataclass
class CardCritique:
    card_id: str
    round_num: int
    intended_message: str
    delivers: bool
    message_clarity: int
    visual_alignment: int
    so_what_strength: int
    redundant_with: Optional[str]
    problem: str
    fix: str
    kill: bool
    score: int
    source_missing: bool = False


@dataclass
class VisualCritique:
    card_id: str
    labels_readable: bool
    chart_clear: bool
    mobile_ready: bool
    color_contrast: bool
    hierarchy_clear: bool
    ft_quality: int
    issues: list = field(default_factory=list)
    fixes: list = field(default_factory=list)


# ── HTML Parser ─────────────────────────────────────────

def extract_cards(html_path: str) -> list[CardContent]:
    """Parse HTML briefing into individual card objects."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    card_divs = soup.find_all("div", class_="card")
    cards = []

    for i, div in enumerate(card_divs):
        card_id = div.get("id", f"unknown_{i}")

        # Detect card type
        card_type = "data"
        if "act-card" in div.get("class", []):
            card_type = "act"
        elif div.find("div", class_="sc"):
            card_type = "scenario"
        elif div.find("div", class_="map-c"):
            card_type = "map"
        elif div.find("div", class_="source-panel"):
            card_type = "verdict"
        elif div.find("div", class_="checklist"):
            card_type = "checklist"

        # Extract headline
        headline = ""
        for tag in ["h1", "h2", "h3"]:
            el = div.find(tag)
            if el:
                headline = el.get_text(strip=True)
                break

        # Extract subtext
        subtext = ""
        sub_el = div.find("p", class_="card-sub")
        if sub_el:
            subtext = sub_el.get_text(strip=True)

        # Extract insight
        insight = ""
        ins_el = div.find("div", class_=lambda c: c and "insight" in c)
        if ins_el:
            insight = ins_el.get_text(strip=True)

        # Check for source
        has_source = bool(div.find("p", class_="src"))

        # Detect visual type
        visual_type = "none"
        if div.find("div", class_="map-c"):
            visual_type = "leaflet_map"
        elif div.find("canvas"):
            visual_type = "chartjs"
        elif div.find("svg"):
            visual_type = "svg"
        elif div.find("div", class_="kpi-grid"):
            visual_type = "kpi_grid"
        elif div.find("div", class_="dominoes"):
            visual_type = "dominoes"
        elif div.find("div", class_="timeline"):
            visual_type = "timeline"

        # Extract stats
        stats = []
        for stat_div in div.find_all("div", class_="stat"):
            val_el = stat_div.find("div", class_="val")
            lbl_el = stat_div.find("div", class_="lbl")
            if val_el and lbl_el:
                stats.append({
                    "value": val_el.get_text(strip=True),
                    "label": lbl_el.get_text(strip=True)
                })

        raw_html = str(div)

        cards.append(CardContent(
            card_id=card_id,
            index=i,
            card_type=card_type,
            headline=headline,
            subtext=subtext,
            visual_type=visual_type,
            stats=stats,
            insight=insight,
            has_source=has_source,
            raw_html=raw_html
        ))

    return cards


# ── Source Enforcement ──────────────────────────────────

DATA_CLAIM_INDICATORS = [
    "$", "%", "million", "billion", "bbl", "tonnes", "crore",
    "days", "weeks", "months", "GDP", "target", "forecast"
]


def check_source_enforcement(cards: list[CardContent]) -> list[str]:
    """Return list of card_ids that have data claims but no .src line."""
    missing = []
    for c in cards:
        if c.card_type == "act":
            continue  # Act breaks don't need sources
        text = (c.headline + " " + c.subtext + " " + c.insight).lower()
        has_data_claim = any(ind.lower() in text for ind in DATA_CLAIM_INDICATORS)
        if has_data_claim and not c.has_source:
            missing.append(c.card_id)
    return missing


# ── Gate 1: MBB Partner Critique ────────────────────────

GATE1_SYSTEM = """You are a senior partner at McKinsey's Energy & Materials Practice.
You are reviewing a strategic intelligence briefing about geopolitical events
and their impact on Indian refineries. Your audience is C-suite executives
at Indian energy companies.

You evaluate briefing cards with surgical precision. Every card must:
1. Have ONE clear intended message
2. Deliver that message in under 5 seconds of viewing
3. Use its visual to PROVE the message, not decorate
4. Have an insight that changes a decision
5. Not repeat what another card already said

You are harsh but constructive. If a card fails, you say exactly why and
exactly how to fix it."""

ROUND_LENSES = {
    1: """ROUND 1: STRUCTURE
Focus on whether each card is saying the RIGHT THING.
- Is this the right message for this position in the deck?
- Does the message follow logically from the previous card?
- Is the visual type appropriate for this message?
- Would a different framing be more powerful?""",

    2: """ROUND 2: PRECISION
Focus on whether each card is saying it SIMPLY ENOUGH.
- Could you explain this card in one sentence?
- Is there any text that could be cut?
- Is the visual immediately legible or does it require study?
- Could a simpler visual deliver the same message?""",

    3: """ROUND 3: KILL
Focus on what can be CUT ENTIRELY.
- Is this card redundant with another card?
- Does this card earn its place in the deck?
- Would the briefing be stronger without this card?
- Can two weak cards be merged into one strong card?
Be aggressive. A 30-card deck that's tight beats a 35-card deck with filler."""
}


def run_gate1_critique(
    client: anthropic.Anthropic,
    cards: list[CardContent],
    round_num: int,
    previous_critiques: list[dict] = None,
    full_html: str = None
) -> list[CardCritique]:
    """Run one round of MBB partner critique on all cards."""

    card_summaries = []
    for c in cards:
        summary = {
            "card_id": c.card_id,
            "index": c.index,
            "type": c.card_type,
            "headline": c.headline,
            "subtext": c.subtext,
            "visual_type": c.visual_type,
            "stats": c.stats,
            "insight": c.insight,
            "has_source": c.has_source
        }
        card_summaries.append(summary)

    html_context = ""
    if full_html:
        html_context = (
            "\n\nHere is the COMPLETE HTML source of the briefing. Read every card, "
            "every visual, every line of JavaScript that generates maps and charts. "
            "Your critique must account for what the user ACTUALLY SEES when the page "
            "renders, not just the text content.\n\n"
            f"```html\n{full_html}\n```\n\n"
        )

    prompt = f"""{ROUND_LENSES[round_num]}

{html_context if html_context else f"Here are all {len(cards)} cards in the briefing:" + chr(10) + json.dumps(card_summaries, indent=2)}

{"Previous round critiques for context:" + json.dumps(previous_critiques, indent=2) if previous_critiques else ""}

For EACH card, respond with a JSON array. Each element:
{{
  "card_id": "c0",
  "intended_message": "One sentence: what should this card communicate?",
  "delivers": true/false,
  "message_clarity": 1-10,
  "visual_alignment": 1-10,
  "so_what_strength": 1-10,
  "redundant_with": null or "c8",
  "problem": "What's wrong (or 'none')",
  "fix": "Specific action to take (or 'none')",
  "kill": false,
  "score": 7
}}

Return ONLY the JSON array. No markdown, no explanation."""

    response = client.messages.create(
        model=CRITIQUE_MODEL,
        max_tokens=MAX_TOKENS,
        system=GATE1_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    try:
        critiques_raw = json.loads(text)
    except json.JSONDecodeError:
        print(f"  WARNING: Failed to parse critique JSON. Attempting repair...")
        for suffix in ["]", '"}]', '"}]']:
            try:
                critiques_raw = json.loads(text + suffix)
                print(f"  Repaired with suffix: {suffix}")
                break
            except json.JSONDecodeError:
                continue
        else:
            print(f"  WARNING: Could not repair. Skipping round.")
            return []

    # Source enforcement
    source_missing = check_source_enforcement(cards)

    critiques = []
    for cr in critiques_raw:
        cid = cr.get("card_id", "unknown")
        critiques.append(CardCritique(
            card_id=cid,
            round_num=round_num,
            intended_message=cr.get("intended_message", ""),
            delivers=cr.get("delivers", False),
            message_clarity=cr.get("message_clarity", 5),
            visual_alignment=cr.get("visual_alignment", 5),
            so_what_strength=cr.get("so_what_strength", 5),
            redundant_with=cr.get("redundant_with"),
            problem=cr.get("problem", ""),
            fix=cr.get("fix", ""),
            kill=cr.get("kill", False),
            score=cr.get("score", 5),
            source_missing=cid in source_missing
        ))

    return critiques


# ── Auto-Apply Fixes ────────────────────────────────────

def auto_apply_fixes(
    client: anthropic.Anthropic,
    html_path: str,
    critiques: list[CardCritique]
) -> bool:
    """Call Claude Sonnet to rewrite cards that scored below threshold.
    Returns True if any changes were applied."""

    cards_to_fix = [c for c in critiques if c.score < SCORE_THRESHOLD]
    cards_to_kill = [c for c in critiques if c.kill]
    source_missing = [c for c in critiques if c.source_missing]

    if not cards_to_fix and not cards_to_kill and not source_missing:
        return False

    with open(html_path, "r", encoding="utf-8") as f:
        current_html = f.read()

    fixes_text = ""
    for cr in cards_to_fix:
        fixes_text += f"""
Card {cr.card_id} (score: {cr.score}/10):
  Message: {cr.intended_message}
  Problem: {cr.problem}
  Fix: {cr.fix}
"""

    kills_text = ""
    for cr in cards_to_kill:
        kills_text += f"  - {cr.card_id}: {cr.problem}\n"

    source_text = ""
    if source_missing:
        ids = ", ".join(c.card_id for c in source_missing)
        source_text = f"\nSOURCE ENFORCEMENT: Cards missing .src line: {ids}\nAdd <p class=\"src\">Source name</p> to each.\n"

    prompt = f"""You are rewriting cards in the following HTML briefing.

CARDS TO FIX (score below {SCORE_THRESHOLD}/10):
{fixes_text}

{"CARDS TO KILL:" + chr(10) + kills_text if kills_text else ""}
{source_text}

RULES:
- Edit ONLY the cards listed above
- For each fix, the INTENDED MESSAGE must drive the redesign
- Visual must PROVE the message, not decorate
- Keep text minimal: headline (<8 words), one subtext sentence, one insight
- If killing a card, remove its entire <div class="card"> block
- Do NOT touch cards that scored {SCORE_THRESHOLD}+
- Return the COMPLETE modified HTML

Here is the current HTML:

```html
{current_html}
```

Return ONLY the full modified HTML. No markdown wrapper, no explanation."""

    response = client.messages.create(
        model=REWRITE_MODEL,
        max_tokens=MAX_TOKENS * 4,
        messages=[{"role": "user", "content": prompt}]
    )

    new_html = response.content[0].text.strip()
    if new_html.startswith("```"):
        new_html = re.sub(r"^```(?:html)?\n?", "", new_html)
        new_html = re.sub(r"\n?```$", "", new_html)

    # Validate we got something reasonable
    if len(new_html) < len(current_html) * 0.5:
        print("  WARNING: Rewrite output too short — likely truncated. Skipping.")
        return False

    if "<html" not in new_html[:200]:
        print("  WARNING: Rewrite output doesn't look like HTML. Skipping.")
        return False

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"  Applied fixes to {html_path} ({len(new_html):,} chars)")
    return True


# ── Gate 2: Visual Critique ─────────────────────────────

def take_screenshots(html_path: str, output_dir: str = "screenshots") -> list[str]:
    """Use Playwright to screenshot each card."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium")
        return []

    os.makedirs(output_dir, exist_ok=True)
    abs_path = os.path.abspath(html_path)
    file_url = f"file:///{abs_path.replace(os.sep, '/')}"

    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(file_url)
        page.wait_for_timeout(3000)

        cards = page.query_selector_all(".card")
        for i, card in enumerate(cards):
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            path = os.path.join(output_dir, f"card_{i:02d}.png")
            card.screenshot(path=path)
            paths.append(path)
            print(f"  Screenshot: Card {i} -> {path}")

        # Mobile screenshots
        page_m = browser.new_page(viewport={"width": 375, "height": 812})
        page_m.goto(file_url)
        page_m.wait_for_timeout(3000)
        cards_m = page_m.query_selector_all(".card")
        for i, card in enumerate(cards_m):
            card.scroll_into_view_if_needed()
            page_m.wait_for_timeout(500)
            path = os.path.join(output_dir, f"card_{i:02d}_mobile.png")
            card.screenshot(path=path)

        browser.close()

    return paths


def run_gate2_critique(
    client: anthropic.Anthropic,
    screenshot_paths: list[str],
    batch_size: int = 5
) -> list[VisualCritique]:
    """Send screenshots to multimodal LLM for visual critique."""

    all_critiques = []

    for batch_start in range(0, len(screenshot_paths), batch_size):
        batch = screenshot_paths[batch_start:batch_start + batch_size]

        content = []
        for path in batch:
            with open(path, "rb") as f:
                img_data = base64.standard_b64encode(f.read()).decode("utf-8")
            card_idx = os.path.basename(path).replace("card_", "").replace(".png", "")
            content.append({"type": "text", "text": f"Card {card_idx}:"})
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_data}
            })

        content.append({
            "type": "text",
            "text": """For each card screenshot, evaluate:

1. Are all labels/text readable? (no overlaps, no cutoffs)
2. Is the chart/map/visual immediately clear?
3. Would this work on mobile (375px)?
4. Is color contrast sufficient?
5. Is visual hierarchy clear (what do you look at first)?
6. Does this meet Financial Times / McKinsey visual quality bar?

Return a JSON array:
[{
  "card_id": "card_00",
  "labels_readable": true,
  "chart_clear": true,
  "mobile_ready": true,
  "color_contrast": true,
  "hierarchy_clear": true,
  "ft_quality": 8,
  "issues": ["label X overlaps with Y"],
  "fixes": ["move label X 10px left"]
}]

JSON only. No markdown."""
        })

        response = client.messages.create(
            model=VISUAL_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": content}]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        try:
            batch_critiques = json.loads(text)
            for vc in batch_critiques:
                all_critiques.append(VisualCritique(
                    card_id=vc.get("card_id", ""),
                    labels_readable=vc.get("labels_readable", True),
                    chart_clear=vc.get("chart_clear", True),
                    mobile_ready=vc.get("mobile_ready", True),
                    color_contrast=vc.get("color_contrast", True),
                    hierarchy_clear=vc.get("hierarchy_clear", True),
                    ft_quality=vc.get("ft_quality", 5),
                    issues=vc.get("issues", []),
                    fixes=vc.get("fixes", [])
                ))
        except json.JSONDecodeError:
            print(f"  WARNING: Failed to parse visual critique batch")

    return all_critiques


# ── Reports ─────────────────────────────────────────────

def print_gate1_report(critiques: list[CardCritique], round_num: int):
    print(f"\n{'='*60}")
    print(f"  GATE 1 -- ROUND {round_num} RESULTS")
    print(f"{'='*60}")

    avg = sum(c.score for c in critiques) / len(critiques) if critiques else 0
    below = [c for c in critiques if c.score < SCORE_THRESHOLD]
    kills = [c for c in critiques if c.kill]
    src_missing = [c for c in critiques if c.source_missing]

    print(f"\n  Average score: {avg:.1f}/10")
    print(f"  Cards below {SCORE_THRESHOLD}: {len(below)}/{len(critiques)}")
    print(f"  Cards to kill: {len(kills)}")
    print(f"  Missing sources: {len(src_missing)}")

    print(f"\n  {'CARD':<8} {'SCORE':>5} {'CLR':>4} {'VIS':>4} {'WHY':>4} {'SRC':<4} {'STATUS':<12} PROBLEM")
    print(f"  {'_'*80}")

    for c in sorted(critiques, key=lambda x: x.score):
        status = "OK" if c.score >= SCORE_THRESHOLD else "FIX"
        if c.kill:
            status = "KILL"
        elif c.redundant_with:
            status = f"DUP->{c.redundant_with}"

        src_flag = "!" if c.source_missing else ""
        problem_short = c.problem[:40] + "..." if len(c.problem) > 40 else c.problem
        print(
            f"  {c.card_id:<8} {c.score:>5} {c.message_clarity:>4} "
            f"{c.visual_alignment:>4} {c.so_what_strength:>4} {src_flag:<4} "
            f"{status:<12} {problem_short}"
        )


def print_gate2_report(critiques: list[VisualCritique]):
    print(f"\n{'='*60}")
    print(f"  GATE 2 -- VISUAL CRITIQUE RESULTS")
    print(f"{'='*60}")

    avg = sum(c.ft_quality for c in critiques) / len(critiques) if critiques else 0
    print(f"\n  Average FT quality: {avg:.1f}/10")

    for c in sorted(critiques, key=lambda x: x.ft_quality):
        indicator = "OK" if c.ft_quality >= 7 else "WARN" if c.ft_quality >= 5 else "FAIL"
        print(f"  [{indicator}] {c.card_id}: {c.ft_quality}/10", end="")
        if c.issues:
            print(f" -- {', '.join(c.issues[:2])}", end="")
        print()


def save_report(critiques: list, output_path: str):
    data = [asdict(c) for c in critiques]
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  Saved to {output_path}")


# ── Main Pipeline ───────────────────────────────────────

def run_pipeline(
    html_path: str,
    gate: str = "all",
    rounds: int = GATE1_ROUNDS,
    auto_fix: bool = False
):
    """Run the full critique pipeline."""
    client = anthropic.Anthropic()

    print(f"\n  Briefing Critique Pipeline")
    print(f"   File: {html_path}")
    print(f"   Gate: {gate}")
    print(f"   Rounds: {rounds}")
    print(f"   Auto-fix: {auto_fix}")

    # Read full HTML
    print(f"\n  Reading full HTML...")
    with open(html_path, "r", encoding="utf-8") as f:
        full_html = f.read()
    print(f"   File size: {len(full_html):,} chars (~{len(full_html)//4:,} tokens)")

    # Extract cards
    print(f"\n  Parsing cards...")
    cards = extract_cards(html_path)
    print(f"   Found {len(cards)} cards")
    for c in cards:
        src_flag = "" if c.has_source else " [!src]"
        print(f"   {c.card_id}: {c.headline[:50] or '(act card)'} [{c.visual_type}]{src_flag}")

    # Gate 1: MBB Critique
    if gate in ("1", "all"):
        print(f"\n  GATE 1: MBB Partner Critique")

        all_round_critiques = []
        for round_num in range(1, rounds + 1):
            lens_name = {1: "Structure", 2: "Precision", 3: "Kill"}.get(round_num, "")
            print(f"\n  -- Round {round_num}/{rounds}: {lens_name} --")

            prev = [asdict(c) for c in all_round_critiques] if all_round_critiques else None
            critiques = run_gate1_critique(client, cards, round_num, prev, full_html=full_html)

            if not critiques:
                print("  WARNING: No critiques returned, skipping round")
                continue

            print_gate1_report(critiques, round_num)
            save_report(critiques, f"critique_gate1_round{round_num}.json")
            all_round_critiques = critiques

            # Auto-apply if requested
            if auto_fix:
                avg = sum(c.score for c in critiques) / len(critiques)
                if avg >= AVG_TARGET:
                    below = [c for c in critiques if c.score < SCORE_THRESHOLD]
                    src_miss = [c for c in critiques if c.source_missing]
                    if not below and not src_miss:
                        print(f"\n  All cards score {SCORE_THRESHOLD}+ and have sources. Done.")
                        break

                applied = auto_apply_fixes(client, html_path, critiques)
                if applied:
                    print(f"  Re-parsing after fixes...")
                    with open(html_path, "r", encoding="utf-8") as f:
                        full_html = f.read()
                    cards = extract_cards(html_path)
                    print(f"   Now {len(cards)} cards")
                else:
                    print(f"  No fixes to apply.")

            time.sleep(2)

    # Gate 2: Visual Critique
    if gate in ("2", "all"):
        print(f"\n  GATE 2: Visual Critique")
        print(f"   Taking screenshots...")

        screenshots = take_screenshots(html_path)
        if screenshots:
            desktop = [s for s in screenshots if "mobile" not in s]
            print(f"   {len(desktop)} desktop screenshots taken")

            critiques = run_gate2_critique(client, desktop)
            print_gate2_report(critiques)
            save_report(critiques, "critique_gate2.json")
        else:
            print("   WARNING: No screenshots taken (Playwright issue?)")

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")


# ── CLI ─────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Briefing Critique Pipeline -- MBB + Visual + Auto-fix"
    )
    parser.add_argument("--file", "-f", required=True, help="Path to the HTML briefing file")
    parser.add_argument("--gate", "-g", choices=["1", "2", "all"], default="all",
                        help="Which gate to run")
    parser.add_argument("--rounds", "-r", type=int, default=GATE1_ROUNDS,
                        help=f"Number of Gate 1 rounds (default: {GATE1_ROUNDS})")
    parser.add_argument("--auto-fix", action="store_true",
                        help="Auto-apply fixes via Claude Sonnet API")
    parser.add_argument("--threshold", "-t", type=int, default=SCORE_THRESHOLD,
                        help=f"Score threshold for rewrites (default: {SCORE_THRESHOLD})")

    args = parser.parse_args()

    if args.threshold:
        SCORE_THRESHOLD = args.threshold

    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        sys.exit(1)

    run_pipeline(
        html_path=args.file,
        gate=args.gate,
        rounds=args.rounds,
        auto_fix=args.auto_fix
    )

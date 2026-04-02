import json, sys, os
sys.stdout.reconfigure(encoding="utf-8")
import anthropic
from dotenv import load_dotenv
load_dotenv()

key = os.environ.get("ANTHROPIC_API_KEY")
if not key:
    for p in [".env", "../iran-crisis-v2/.env"]:
        if os.path.exists(p):
            for line in open(p):
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
        if key:
            break
client = anthropic.Anthropic(api_key=key)

from datetime import datetime, date
TODAY = date.today().strftime("%B %d, %Y")
WAIVER_DATE = date(2026, 4, 3)
DAYS_TO_WAIVER = (WAIVER_DATE - date.today()).days
print(f"Today: {TODAY} | Waiver in {DAYS_TO_WAIVER} days")


def strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return t


import time as _time

def call(system, user, max_tokens=16384, retries=5):
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=max_tokens,
                system=system, messages=[{"role": "user", "content": user}],
            )
            return resp.content[0].text
        except Exception as e:
            if "overloaded" in str(e).lower() or "529" in str(e):
                wait = 10 * (attempt + 1)
                print(f"    API overloaded, retrying in {wait}s (attempt {attempt+1}/{retries})...")
                _time.sleep(wait)
            else:
                raise
    raise Exception("API overloaded after all retries")


# Context that must appear on every one-pager
CRISIS_CONTEXT = f"""CONTEXT FOR THE ONE-PAGER:
TODAY'S DATE: {TODAY}. The crisis is ONGOING. Deadlines are FUTURE dates.
Iran-US conflict has closed the Strait of Hormuz since February 28, 2026 (27 days ago).
Iran mined the strait. 20M bbl/day of global crude is offline.
Indian crude basket at $156/bbl (up from $69 pre-crisis).
India imports 88% of its crude. 42% transited Hormuz.
Russia sanctions waiver (informal US non-enforcement) expires April 3 — that is {DAYS_TO_WAIVER} DAYS from now, NOT tonight.
This is the largest oil supply disruption in history.
The one-pager audience is a CEO or senior LinkedIn reader who may NOT be an oil industry specialist.
CRITICAL: All dates must be stated relative to today ({TODAY}). Use "in X days (Date)" format. Never say "tonight" or "tomorrow" unless the actual date is the day after {TODAY}."""


PS_DETAILS = {
    "iocl_hmel": {
        "name": "IOCL & HMEL",
        "refineries": "Indian Oil Corporation (Paradip, Panipat, Gujarat/Koyali) and HPCL-Mittal Energy (Bathinda)",
        "brief_purpose": "What IOCL and HMEL must decide in the next 7 days to avoid refinery shutdown, banking default, and cooking-gas rationing in southern India.",
    },
    "lownci_psu": {
        "name": "Low-Complexity Government Refiners",
        "refineries": "HPCL Mumbai, BPCL Mumbai, BPCL Kochi, CPCL Manali (Chennai), IOCL Bina, and NRL Numaligarh — India's six most vulnerable refineries",
        "brief_purpose": "What the government must decide in the next 48 hours to prevent a cascade of refinery shutdowns that would cut fuel supply to 400 million people.",
    },
}

for ps in ["iocl_hmel", "lownci_psu"]:
    print(f"\n{'='*60}")
    print(f"  {ps.upper()}")
    print(f"{'='*60}")

    # Load the final JSON
    fp = f"outputs/reports/{ps}/one_pager_final.json"
    if not os.path.exists(fp):
        fp = f"outputs/reports/{ps}/one_pager_ceo.json"
    if not os.path.exists(fp):
        fp = f"outputs/reports/{ps}/one_pager.json"
    op = json.load(open(fp, encoding="utf-8"))

    # Also load hypothesis tree for evidence
    ht = json.load(open(f"outputs/hypothesis_trees/{ps}/hypotheses_final.json", encoding="utf-8"))

    content = json.dumps(op, indent=2, ensure_ascii=False)
    hyp_content = json.dumps(ht, indent=2, ensure_ascii=False)[:8000]

    # ─── PASS 1: Design Director ───
    print("  Pass 1: Design Director...")
    design_html = call(
        system="""You are a world-class information designer (Edward Tufte meets Apple).
You are given a one-pager JSON and must produce a SINGLE self-contained HTML file.

DESIGN RULES:
- WHITE background EVERYWHERE. No dark headers, no dark banners, no black sections. Pure white page with black text.
- The page must feel like a single printed A4 sheet — not a scrolling website
- NO decorative elements. No colored blocks. No gradients. Clean like a McKinsey memo printed on paper.
- Use Inter font family (Google Fonts), JetBrains Mono for numbers
- Visual hierarchy: Title (largest) > Section headers > Body > Sources
- KPIs displayed as large numbers with small labels beneath, in a horizontal row — NOT a table
- Analysis as numbered cards with clear visual separation
- Decisions as bold numbered blocks with red accent
- A thin context banner at the very top with TWO parts: (1) one line explaining the crisis (Hormuz closure, $156/bbl, April 3 waiver expiry) and (2) one line explaining what THIS BRIEF covers — who it's for, what decisions it addresses, and why these specific entities matter. Example: "This brief: What IOCL and HMEL must decide in the next 72 hours to avoid refinery shutdown and sovereign debt default."
- Source attributions in small grey text where needed
- No tabs, no navigation, no links — this is a standalone document
- Must include: condensed problem statement, recommendation headline, situation, KPIs, analysis, decisions
- Page should look like it came from McKinsey, not from a coder

Return ONLY the complete HTML. No markdown wrapping. No explanation.""",
        user=f"""{CRISIS_CONTEXT}

THIS BRIEF COVERS: {PS_DETAILS[ps]["refineries"]}
BRIEF PURPOSE: {PS_DETAILS[ps]["brief_purpose"]}

The context banner at the top must have TWO lines:
Line 1: The crisis -- Hormuz closed, crude at $156, waiver expires in {DAYS_TO_WAIVER} days
Line 2: This brief -- {PS_DETAILS[ps]["brief_purpose"]}

ONE-PAGER DATA:
{content}

HYPOTHESIS TREE (for additional context/evidence):
{hyp_content}

Generate the HTML one-pager. ALL WHITE background. Name every refinery explicitly.

CRITICAL — USE THIS EXACT HTML TEMPLATE STRUCTURE (same for both briefs, only content changes):
1. Grey context banner (2 lines, small text)
2. Bold headline (the decision)
3. Situation paragraph (2 sentences)
4. 2-3 large KPI cards in a horizontal row (big number + small label + small variance)
5. 3 numbered analysis findings (finding + impact in red + so-what in grey)
6. 3-4 numbered decisions (verb + specific ask + owner + deadline)
7. "Developed by Parth Reddy" footer

Use this exact CSS approach — Inter font, JetBrains Mono for numbers, 800px max-width, generous padding, thin borders only. No boxes, no cards with backgrounds, no colored sections. Just clean typography on white."""
    )
    design_html = strip_fences(design_html)

    # Save design pass
    open(f"outputs/reports/{ps}/onepager_v2_design.html", "w", encoding="utf-8").write(design_html)
    print(f"    Design: {len(design_html):,} chars")

    # ─── PASS 2: MBB Senior Partner — Storytelling ───
    print("  Pass 2: MBB Partner (storytelling)...")
    story_review = call(
        system="""You are a McKinsey Senior Partner. You review HTML one-pagers for storytelling quality.

CHECK:
1. Does the headline TELL the CEO what to decide? (not describe the situation)
2. Does the situation create URGENCY in under 30 words?
3. Does each analysis finding follow: WHAT happened > WHY it matters > WHAT TO DO?
4. Are decisions ATOMIC (one action, one owner, one deadline each)?
5. Is there a clear CONTEXT banner so a non-specialist understands the crisis?
6. Is the pyramid structure correct: conclusion first, then proof?
7. Are numbers CRISP (single figures, not ranges)?

Return a JSON with:
{"score": 1-10, "issues": ["specific problem"], "rewrites": {"selector_or_section": "exact replacement text"}}
If score >= 8, return empty rewrites. JSON only.""",
        user=f"Review this HTML one-pager for storytelling:\n\n{design_html[:12000]}"
    )
    story_data = json.loads(strip_fences(story_review))
    print(f"    Story score: {story_data.get('score')}/10")
    for issue in story_data.get("issues", []):
        print(f"    ISSUE: {issue[:120]}")

    # ─── PASS 3: CEO / LinkedIn Reader — Comprehension ───
    print("  Pass 3: CEO/LinkedIn reader (comprehension)...")
    ceo_review = call(
        system="""You are a CEO who has never worked in oil & gas. You are seeing this one-pager for the first time on LinkedIn.

You have 45 seconds. Rate:
1. Do you understand WHAT is being decided? (yes/no + what you think it is)
2. Do you understand WHY it's urgent? (yes/no + what you think the urgency is)
3. Do you understand the NUMBERS? (flag any number you can't parse in 3 seconds)
4. Do you understand WHAT HAPPENS if nothing is done? (yes/no)
5. Would you share this on LinkedIn? (yes/no + why)
6. Any sentence you had to read twice?

Return JSON:
{"comprehension_score": 1-10, "would_share": true/false, "confused_by": ["specific text"], "suggestions": ["specific fix"]}
JSON only.""",
        user=f"Read this one-pager as a non-oil CEO:\n\n{design_html[:12000]}"
    )
    ceo_data = json.loads(strip_fences(ceo_review))
    print(f"    Comprehension: {ceo_data.get('comprehension_score')}/10 | Would share: {ceo_data.get('would_share')}")
    for c in ceo_data.get("confused_by", []):
        print(f"    CONFUSED: {c[:120]}")

    # ─── SINGLE PASS: Apply ALL fixes at once ───
    all_fixes = []
    if story_data.get("score", 0) < 8:
        all_fixes.extend(story_data.get("fixes", []))
        if story_data.get("rewrites"):
            for k, v in story_data["rewrites"].items():
                all_fixes.append(f"In section '{k}': rewrite to: {v}")
    if ceo_data.get("comprehension_score", 0) < 8:
        all_fixes.extend(ceo_data.get("suggestions", []))

    if all_fixes:
        print(f"    Applying {len(all_fixes)} combined fixes in one pass...")
        fix_html = call(
            system="You are given an HTML one-pager and a list of fixes from two reviewers (an MBB partner and a CEO reader). Apply ALL fixes in a single pass. Do not break anything that already works. Return the complete fixed HTML only. No markdown wrapping.",
            user=f"HTML:\n{design_html}\n\nALL FIXES TO APPLY:\n" + "\n".join(f"- {f}" for f in all_fixes) + "\n\nApply all. Return complete HTML."
        )
        design_html = strip_fences(fix_html)
        print(f"    Fixed: {len(design_html):,} chars")

    # Save final
    final_path = f"outputs/reports/{ps}/onepager.html"
    open(final_path, "w", encoding="utf-8").write(design_html)
    print(f"    FINAL: {len(design_html):,} chars -> {final_path}")

    # Save all reviews
    json.dump({
        "design_pass": True,
        "story_score": story_data.get("score"),
        "story_issues": story_data.get("issues", []),
        "comprehension_score": ceo_data.get("comprehension_score"),
        "would_share": ceo_data.get("would_share"),
        "confused_by": ceo_data.get("confused_by", []),
    }, open(f"outputs/reports/{ps}/onepager_reviews.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("\n\nDONE")

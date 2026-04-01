#!/usr/bin/env python3
"""
Step 1: Tiered research pipeline.
  1A: Score all questions T1/T2/T3
  1B: Deduplicate into common research themes
  1C: Generate research briefs
  1D: Compile and map

Usage:
    python run_research.py                  # full pipeline
    python run_research.py --step 1a        # just scoring
    python run_research.py --step 1b        # just dedup (needs 1a output)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384
ROOT = Path(__file__).parent
OUTPUTS = ROOT.parent / "outputs" / "mece_3ps"
RESEARCH_DIR = ROOT.parent / "outputs" / "research"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_client() -> anthropic.Anthropic:
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        for p in [ROOT.parent / ".env", ROOT.parent.parent / "oil-dashboard" / ".env"]:
            if p.exists():
                for line in p.read_text().splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            if api_key:
                break
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def call_claude(client: anthropic.Anthropic, system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break
    if response.stop_reason == "max_tokens" and text:
        print("  (continuing truncated response...)")
        resp2 = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[
                {"role": "user", "content": user},
                {"role": "assistant", "content": text},
                {"role": "user", "content": "Continue EXACTLY where you left off. Output ONLY the remaining JSON."},
            ],
        )
        for block2 in resp2.content:
            if block2.type == "text":
                text += block2.text
                break
    return text


def parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        cleaned = cleaned[first_nl + 1 : last_fence].strip()
    # Remove control characters that break JSON parsing
    import re
    cleaned = re.sub(r'[\x00-\x1f\x7f]', lambda m: ' ' if m.group() not in ('\n', '\r', '\t') else m.group(), cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try with strict=False as fallback
        return json.loads(cleaned, strict=False)


def load_all_questions() -> list[dict]:
    """Load all questions from all 3 PS decompositions."""
    all_qs = []
    for ps_id in [1, 2, 3]:
        path = OUTPUTS / f"ps{ps_id}" / "3_final.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        ps_label = f"PS{ps_id}"
        for sec in data["sections"]:
            for q in sec["questions"]:
                all_qs.append({
                    "ps": ps_label,
                    "bucket_id": sec["section_id"],
                    "bucket_title": sec["title"],
                    "question_id": q["id"],
                    "question": q["question"],
                })
    return all_qs


def print_divider(title: str) -> None:
    width = 72
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


# ---------------------------------------------------------------------------
# Step 1A: Tier Scoring
# ---------------------------------------------------------------------------

TIER_SCORE_SYSTEM = """\
You are a senior strategy consultant triaging research priorities for a \
crisis decision brief. You score questions by DECISION IMPACT — how much \
getting this wrong would change the recommendation."""

TIER_SCORE_USER = """\
Below are {count} questions from 3 problem statements about the Iran-Israel \
Hormuz crisis impact on Indian refineries. Score each question into one of \
three tiers:

TIER 1 — "Must research deeply"
  If you get this wrong, the recommendation FLIPS.
  Numbers that feed directly into GRM calculations, inventory runway, \
  procurement economics, or crisis timeline.
  Examples: crude inventory days, alternative crude prices/availability, \
  waiver status, SPR volumes, MRPL gap sizing, crack spreads.

TIER 2 — "Should research moderately"
  Affects recommendation quality but doesn't flip it alone.
  Constrains or enables Tier 1 decisions.
  Examples: crude compatibility matrices, logistics constraints, financial \
  covenants, stakeholder positions, insurance costs, regulatory specifics.

TIER 3 — "Extrapolate from T1+T2"
  Answerable from Tier 1+2 findings + domain knowledge.
  Would not change the recommendation even if somewhat wrong.
  Examples: cyber posture, catalyst inventory, workforce/union issues, \
  medium-term capex, legal technicalities, communication plans, \
  organizational governance, decision sequencing details.

QUESTIONS:
{questions_formatted}

Return ONLY valid JSON (no markdown fences):
{{
  "scores": [
    {{"ps": "PS1", "question_id": "1.1", "tier": 1, "reason": "5 words max"}},
    ...
  ],
  "summary": {{
    "tier1_count": 0,
    "tier2_count": 0,
    "tier3_count": 0
  }}
}}"""


def step1a_score(client: anthropic.Anthropic) -> list[dict]:
    print_divider("STEP 1A: Tier Scoring")
    all_qs = load_all_questions()
    print(f"  Loaded {len(all_qs)} questions across 3 PS")

    # Format questions compactly
    lines = []
    for q in all_qs:
        # Truncate question to save tokens
        qtext = q["question"][:200]
        lines.append(f"[{q['ps']}/{q['question_id']}] {qtext}")

    questions_formatted = "\n".join(lines)

    print(f"  Sending to LLM for tier scoring...")
    t0 = time.time()
    raw = call_claude(client, TIER_SCORE_SYSTEM, TIER_SCORE_USER.format(
        count=len(all_qs),
        questions_formatted=questions_formatted,
    ))
    t1 = time.time()
    print(f"  Done in {t1 - t0:.1f}s")

    result = parse_json(raw)
    scores = result["scores"]

    # Merge scores back into questions
    score_map = {}
    for s in scores:
        key = f"{s['ps']}/{s['question_id']}"
        score_map[key] = s

    scored_qs = []
    for q in all_qs:
        key = f"{q['ps']}/{q['question_id']}"
        s = score_map.get(key, {"tier": 2, "reason": "unscored"})
        q["tier"] = s["tier"]
        q["tier_reason"] = s.get("reason", "")
        scored_qs.append(q)

    # Stats
    t1_count = sum(1 for q in scored_qs if q["tier"] == 1)
    t2_count = sum(1 for q in scored_qs if q["tier"] == 2)
    t3_count = sum(1 for q in scored_qs if q["tier"] == 3)
    print(f"\n  Tier 1 (deep research):    {t1_count}")
    print(f"  Tier 2 (moderate research): {t2_count}")
    print(f"  Tier 3 (extrapolate):       {t3_count}")
    print(f"  Total researched (T1+T2):   {t1_count + t2_count}")

    # Save
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESEARCH_DIR / "1a_scored_questions.json"
    out_path.write_text(json.dumps(scored_qs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Saved -> {out_path}")

    # Print T1 questions
    print(f"\n  TIER 1 QUESTIONS ({t1_count}):")
    for q in scored_qs:
        if q["tier"] == 1:
            print(f"    [{q['ps']}/{q['question_id']}] {q['question'][:100]}")

    return scored_qs


# ---------------------------------------------------------------------------
# Step 1B: Deduplicate into Research Themes
# ---------------------------------------------------------------------------

DEDUP_SYSTEM = """\
You are a research director organizing an analyst team. Your job is to \
eliminate redundant research by grouping related questions into research \
themes that can be answered with a single research brief."""

DEDUP_USER = """\
Below are all Tier 1 and Tier 2 questions from 3 problem statements about \
the Hormuz crisis. Many questions overlap across PS1/PS2/PS3 — they ask \
about the same underlying fact but for different refinery segments.

Group these into RESEARCH THEMES. Each theme is a research brief that will \
be executed once and its findings applied to all relevant questions.

TWO TYPES OF THEMES:

1. COMMON THEMES — answer applies across multiple PS segments.
   Examples: crude prices, waiver status, SPR, MRPL shutdown impact,
   alternative crude availability, government policy, war-risk insurance.

2. SEGMENT-SPECIFIC THEMES — unique to one PS segment.
   Examples: PS1 petrochemical integration, PS2 ESMA compliance,
   PS3 shutdown sequencing.

For each theme provide:
- A clear title
- Whether it's COMMON or SEGMENT-SPECIFIC (and which PS)
- The research depth: TIER_1 (deep) or TIER_2 (moderate)
  Set to TIER_1 if ANY of the grouped questions is Tier 1.
- The specific questions it covers (by PS/ID)
- 3-5 specific data points or numbers to find
- 2-3 recommended sources (EIA, Platts, Argus, Kpler, MoPNG, filings, news)

Target: 12-15 common themes + 5-6 per segment = ~27-33 total.

QUESTIONS (Tier 1 and Tier 2 only):
{questions_formatted}

Return ONLY valid JSON (no markdown fences):
{{
  "themes": [
    {{
      "theme_id": "C1",
      "title": "...",
      "scope": "COMMON" | "PS1" | "PS2" | "PS3",
      "research_depth": "TIER_1" | "TIER_2",
      "questions_covered": ["PS1/1.1", "PS2/1.1", "PS3/1.1"],
      "data_points_to_find": ["...", "...", "..."],
      "recommended_sources": ["...", "..."],
      "search_queries": ["...", "...", "..."]
    }},
    ...
  ],
  "summary": {{
    "common_themes": 0,
    "ps1_themes": 0,
    "ps2_themes": 0,
    "ps3_themes": 0,
    "total_questions_covered": 0,
    "uncovered_questions": ["PS1/x.x"]
  }}
}}"""


def step1b_dedup(client: anthropic.Anthropic, scored_qs: list[dict]) -> list[dict]:
    print_divider("STEP 1B: Deduplicate into Research Themes")

    # Filter to T1 + T2 only
    research_qs = [q for q in scored_qs if q["tier"] in (1, 2)]
    print(f"  {len(research_qs)} questions to research (T1+T2)")

    lines = []
    for q in research_qs:
        tier_label = "T1" if q["tier"] == 1 else "T2"
        qtext = q["question"][:180]
        lines.append(f"[{q['ps']}/{q['question_id']}] ({tier_label}) {qtext}")

    questions_formatted = "\n".join(lines)

    print(f"  Sending to LLM for theme grouping...")
    t0 = time.time()
    raw = call_claude(client, DEDUP_SYSTEM, DEDUP_USER.format(
        questions_formatted=questions_formatted,
    ))
    t1 = time.time()
    print(f"  Done in {t1 - t0:.1f}s")

    result = parse_json(raw)
    themes = result["themes"]
    summary = result.get("summary", {})

    print(f"\n  Common themes:  {summary.get('common_themes', '?')}")
    print(f"  PS1-specific:   {summary.get('ps1_themes', '?')}")
    print(f"  PS2-specific:   {summary.get('ps2_themes', '?')}")
    print(f"  PS3-specific:   {summary.get('ps3_themes', '?')}")
    print(f"  Total themes:   {len(themes)}")
    print(f"  Questions covered: {summary.get('total_questions_covered', '?')}")

    uncovered = summary.get("uncovered_questions", [])
    if uncovered:
        print(f"  UNCOVERED: {uncovered}")

    # Print themes
    for t in themes:
        depth = t["research_depth"]
        scope = t["scope"]
        n_qs = len(t["questions_covered"])
        print(f"\n  [{t['theme_id']}] {t['title']} ({scope}, {depth}, {n_qs}q)")
        print(f"    Data: {', '.join(t['data_points_to_find'][:3])}")
        print(f"    Sources: {', '.join(t['recommended_sources'][:3])}")

    # Save
    out_path = RESEARCH_DIR / "1b_research_themes.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Saved -> {out_path}")

    return themes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Step 1: Tiered research pipeline")
    parser.add_argument("--step", choices=["1a", "1b", "all"], default="all")
    args = parser.parse_args()

    client = get_client()
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    if args.step in ("1a", "all"):
        scored_qs = step1a_score(client)
    else:
        scored_path = RESEARCH_DIR / "1a_scored_questions.json"
        scored_qs = json.loads(scored_path.read_text(encoding="utf-8"))
        print(f"Loaded scored questions from {scored_path}")

    if args.step in ("1b", "all"):
        themes = step1b_dedup(client, scored_qs)

    print_divider("STEPS 1A-1B COMPLETE")
    print(f"  Output dir: {RESEARCH_DIR.resolve()}")
    print(f"  Next: Execute research briefs (Step 1C)")


if __name__ == "__main__":
    main()

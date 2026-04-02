"""
Briefing Engine — End-to-end pipeline.
Single command: python run.py --topic "..." --audience "..."

Steps:
  0. Problem framing ← HUMAN
  1. Research (automated)
  2. Card decomposition — 3 options ← HUMAN picks
  3. Design Agent (automated)
  4. Build (automated)
  5. Critique loop — Gate 1 + Gate 2 auto-fix (automated)
  6. Final review ← HUMAN
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(OUTPUTS / "pipeline.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def human_checkpoint(prompt_text):
    """Pause for human input. Returns the input string."""
    print(f"\n{'='*60}")
    print(f"  🙋 HUMAN CHECKPOINT")
    print(f"{'='*60}")
    print(f"\n{prompt_text}\n")
    response = input(">>> ").strip()
    return response

def load_api_key():
    """Load Anthropic API key."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        env_paths = [
            ROOT / ".env",
            ROOT.parent / "iran-crisis-v2" / ".env",
            ROOT.parent / "iran-crisis" / ".env",
        ]
        for p in env_paths:
            if p.exists():
                for line in p.read_text().splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        os.environ["ANTHROPIC_API_KEY"] = key
                        break
            if key:
                break
    if not key:
        print("ERROR: No ANTHROPIC_API_KEY found")
        sys.exit(1)
    return key

# ---------------------------------------------------------------------------
# Step 0: Problem Framing
# ---------------------------------------------------------------------------

def step0_problem_framing(client, topic, audience):
    log("STEP 0: Problem Framing")

    from story_engine.prompts import PROBLEM_FRAMING_SYSTEM, PROBLEM_FRAMING_USER

    prompt = PROBLEM_FRAMING_USER.format(topic=topic, audience=audience)

    while True:
        log("  Generating problem statement + MECE questions...")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=PROBLEM_FRAMING_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text
        print(f"\n{result}\n")

        # Save
        (OUTPUTS / "0_problem_statement.txt").write_text(result, encoding="utf-8")

        feedback = human_checkpoint(
            "Review the problem statement and MECE questions above.\n"
            "Press ENTER to approve, or type feedback to revise:"
        )

        if not feedback:
            log("  Problem statement approved.")
            return result
        else:
            prompt = f"{prompt}\n\nUSER FEEDBACK: {feedback}\n\nRevise accordingly."
            log(f"  Revising with feedback: {feedback[:50]}...")


# ---------------------------------------------------------------------------
# Step 1: Research
# ---------------------------------------------------------------------------

def step1_research(client, problem_statement, topic, audience):
    log("STEP 1: Research")

    # Check if working document already exists
    existing_paths = [
        ROOT.parent / "iran-crisis-v2" / "working_document_v3.md",
        OUTPUTS / "1_working_document.md",
    ]

    for p in existing_paths:
        if p.exists():
            log(f"  Found existing working document: {p}")
            doc = p.read_text(encoding="utf-8")
            print(f"\n  Working document: {len(doc):,} chars")

            feedback = human_checkpoint(
                f"Found existing working document ({len(doc):,} chars) at:\n  {p}\n\n"
                "Press ENTER to use it, or type 'new' to generate fresh research:"
            )

            if feedback.lower() != "new":
                (OUTPUTS / "1_working_document.md").write_text(doc, encoding="utf-8")
                return doc

    # Generate research prompts (placeholder — real implementation would use agents)
    log("  No existing working document found.")
    log("  Generating research prompts for manual execution...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system="You are a research coordinator. Generate specific research prompts.",
        messages=[{"role": "user", "content": f"Generate research prompts for each MECE section:\n\n{problem_statement}"}]
    )

    prompts = response.content[0].text
    (OUTPUTS / "1_research_prompts.txt").write_text(prompts, encoding="utf-8")

    print(f"\n{prompts}\n")

    human_checkpoint(
        "Research prompts saved. Execute these with Claude Code agents,\n"
        "then save results to outputs/1_working_document.md\n"
        "Press ENTER when ready:"
    )

    doc = (OUTPUTS / "1_working_document.md").read_text(encoding="utf-8")
    return doc


# ---------------------------------------------------------------------------
# Step 2: Card Decomposition — 3 Options
# ---------------------------------------------------------------------------

def step2_card_decomposition(client, working_document, topic, audience):
    log("STEP 2: Card Decomposition (Story Arc → Proof → Story Check)")

    # ─── STEP 2A: STORY ARC ───
    log("  STEP 2A: Generating story arc (one-sentence messages only)...")

    arc_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system="You are a McKinsey senior partner who writes action titles for strategic briefings. You use the SCQA framework (Situation, Complication, Question, Answer) and Minto's Pyramid Principle. Every headline is a complete sentence that IS the takeaway — never a topic label.",
        messages=[{"role": "user", "content": f"""TOPIC: {topic}
AUDIENCE: {audience}

WORKING DOCUMENT:
{working_document[:40000]}

Write the HEADLINES of this briefing in sequence. When I read them top to bottom — skipping charts, data, everything — I must understand the full story.

STRUCTURE (SCQA):
- Slides 1-5: SITUATION — what happened, how bad, how long. Each headline raises the stakes.
- Slide 6: "—— Your refinery ——"
- Slides 7-9: COMPLICATION for refinery operations. Address the reader directly.
- Slide 10: "—— Your balance sheet ——"
- Slides 11-13: COMPLICATION for CFO. What's bleeding, what's expiring, what to lock.
- Slide 14: "—— Your government ——"
- Slides 15-17: COMPLICATION for policy. What Delhi is doing, what diplomacy buys, what's coming.
- Slide 18: "—— Your board ——"
- Slides 19-20: QUESTION — the macro damage and risks the board must face.
- Slide 21: "—— What everyone else is missing ——"
- Slides 22-23: ANSWER — the edge and the call to act.

RULES:
- Each headline is ONE short sentence. Action title, not topic label.
- Each headline raises the stakes higher than the last.
- Address the reader directly: "Your refinery", "You are losing", "Your board".
- NEVER write topic labels like "Duration Considerations" or "Supply Assessment".
- ALWAYS write action titles like "Even after a ceasefire, mines keep the strait closed until August."
- EACH HEADLINE IS 8-12 WORDS MAXIMUM. No semicolons. No compound sentences. No clauses joined by dashes or commas. If it's longer than 12 words, split it or cut it.
- Section breaks use "——" format: "—— Your refinery ——"
- Maximum 23 headlines including section breaks.

REFERENCE (this is the quality bar — match this tone and directness):
[
  "India faces the largest oil disruption in history.",
  "It happened in 20 days. Both sides are still escalating.",
  "22 Indian ships are stranded. Only 3 made it through.",
  "Crude is manageable. Cooking gas is not. 330 million households are rationing.",
  "Even after a ceasefire, mines keep the strait closed until August.",
  "—— Your refinery ——",
  "Russia flipped from $13 discount to $5 premium. Gulf terminals are offline. Alternatives take 30-45 days.",
  "Jamnagar thrives at $146. HPCL Mumbai is insolvent. The difference is complexity.",
  "The government overrode your product slate. LPG first. No choice.",
  "—— Your balance sheet ——",
  "You are losing ₹19.8 on every litre you sell.",
  "The Russia waiver expires in 15 days. Your largest alternative supply is at risk.",
  "December crude is $69. Today's is $146. Lock it this week.",
  "—— Your government ——",
  "Delhi is hoarding every barrel. They expect this to last months.",
  "Non-alignment got India 3 ships through. That diplomatic capital is finite — use it now.",
  "Fertilizer is 40% Gulf-dependent. Secure kharif supply before June or face a food crisis.",
  "—— Your board ——",
  "The import bill just tripled to $266 billion.",
  "Three risks could make it worse. Your board isn't planning for any of them.",
  "—— What everyone else is missing ——",
  "Banks say weeks. Mine clearance alone is 51 days.",
  "You have 15 days before your fallback disappears. Decide now."
]

Return JSON: {{"story_arc": ["sentence 1", "sentence 2", ...]}}
JSON only. No markdown."""}]
    )

    arc_text = arc_response.content[0].text.strip()
    if arc_text.startswith("```"):
        arc_text = arc_text.split("\n", 1)[1].rsplit("```", 1)[0]

    arc = json.loads(arc_text)
    story_arc = arc.get("story_arc", [])

    log(f"  Story arc: {len(story_arc)} messages")
    print(f"\n{'='*60}")
    print(f"  STORY ARC — {len(story_arc)} CARDS")
    print(f"{'='*60}\n")
    for i, msg in enumerate(story_arc):
        print(f"  {i+1:>2}. {msg}")

    (OUTPUTS / "2a_story_arc.json").write_text(
        json.dumps({"story_arc": story_arc}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    feedback = human_checkpoint(
        "Review the story arc above.\n"
        "Press ENTER to approve.\n"
        "Or type changes: 'cut 5', 'swap 3 and 7', 'add: India's navy response after 6', etc."
    )

    if feedback:
        # Re-generate with feedback
        log(f"  Revising arc with feedback: {feedback[:60]}")
        arc_response2 = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system="You are a McKinsey senior partner. Revise the story arc based on user feedback.",
            messages=[{"role": "user", "content": f"Current story arc:\n{json.dumps(story_arc, indent=2)}\n\nUser feedback: {feedback}\n\nReturn revised JSON: {{\"story_arc\": [...]}}. JSON only."}]
        )
        arc_text2 = arc_response2.content[0].text.strip()
        if arc_text2.startswith("```"):
            arc_text2 = arc_text2.split("\n", 1)[1].rsplit("```", 1)[0]
        story_arc = json.loads(arc_text2).get("story_arc", story_arc)
        log(f"  Revised arc: {len(story_arc)} messages")

        (OUTPUTS / "2a_story_arc.json").write_text(
            json.dumps({"story_arc": story_arc}, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ─── STEP 2B: PROOF ASSIGNMENT ───
    log("  STEP 2B: Assigning proof (2-3 numbers + visual per message)...")

    proof_text = ""
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=16384,
        system="You are a data visualization designer for McKinsey-quality briefings. You assign the minimum proof needed for each message — no more.",
        messages=[{"role": "user", "content": f"""STORY ARC (approved — do NOT change the messages or their order):
{json.dumps(story_arc, indent=2)}

WORKING DOCUMENT (source of all data — do NOT invent numbers):
{working_document[:35000]}

For each message in the story arc, create a card spec with:
- card_id: "c01", "c02", etc.
- card_type: hero, timeline, kpi_card, verdict_panel, scenario_card, chart_card, map_card, quote_pair, checklist, act_break, closing
- key_message: the EXACT sentence from the story arc (do not modify)
- data: ONLY the 2-3 numbers/facts that PROVE the message. Nothing supplementary.
- visual_type: the ONE visual that shows these numbers best. Choose from:
  waterfall, sankey, gauge, line_chart, before_after_bars, bubble_scatter,
  horizontal_bar, map, scenario_cards, 2x2_matrix, quote_pair, timeline,
  dot_grid, checklist, big_number
- source: one-line attribution
- background: "dark" for hero card only, "light" for everything else

CRITICAL RULES:
- If a message is an act break, card_type = "act_break", data = just title + subtitle
- Each card gets MAX 3 data points. If you need more, the story arc needs more cards.
- NO supplementary context. NO background info. NO footnotes.
- The data exists ONLY to prove the message. Nothing else.

CHART MINIMUM (MANDATORY):
- At least 60% of non-act-break cards MUST have a chart or visualization (Chart.js, SVG, Leaflet map).
- No more than 3 text-only/KPI-only cards in the entire deck.
- Prefer charts over text: if data can be shown as a bar, line, waterfall, gauge, scatter, sankey, or map — USE IT.
- Use the FT Visual Vocabulary to select the right chart for the data relationship:
  Deviation → divergence bars, tornado, slope chart
  Correlation → scatter, bubble
  Ranking → horizontal bars, lollipop
  Change over time → line, area, sparkline, gantt
  Magnitude → waterfall, gauge, comparison towers
  Part-to-whole → donut, waffle, stacked bar
  Spatial → map with numbered markers
  Flow → sankey, process flow

Return JSON: {{"cards": [...]}}
JSON only."""}]
    ) as stream:
        for chunk in stream.text_stream:
            proof_text += chunk

    if proof_text.startswith("```"):
        proof_text = proof_text.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        proof_spec = json.loads(proof_text)
    except json.JSONDecodeError:
        # Repair
        for j in range(len(proof_text)-1, 0, -1):
            if proof_text[j] == "}":
                try:
                    proof_spec = json.loads(proof_text[:j+1] + "]}")
                    break
                except:
                    continue
        else:
            log("  ERROR: Could not parse proof assignment. Saving raw.")
            (OUTPUTS / "2b_proof_raw.txt").write_text(proof_text, encoding="utf-8")
            raise ValueError("Proof assignment JSON parse failed")

    cards = proof_spec.get("cards", [])
    log(f"  Proof assigned: {len(cards)} cards")

    (OUTPUTS / "2b_card_spec_raw.json").write_text(
        json.dumps(proof_spec, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ─── STEP 2C: STORY CHECK ───
    log("  STEP 2C: Story check — verifying deck matches approved arc...")

    card_summary = [{"card_id": c.get("card_id"), "key_message": c.get("key_message"), "data_points": len(c.get("data", {}))} for c in cards]

    check_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system="You are a quality checker. You verify that a card deck matches an approved story arc.",
        messages=[{"role": "user", "content": f"""APPROVED STORY ARC:
{json.dumps(story_arc, indent=2)}

CARD SPEC PRODUCED:
{json.dumps(card_summary, indent=2)}

Check:
1. DRIFT: Did any card's key_message change from the approved arc? List card_ids.
2. GAPS: Are any arc messages missing from the cards? List missing messages.
3. ADDITIONS: Are there cards with messages NOT in the arc? List card_ids.
4. DENSITY: Are any cards carrying more than 3 data points? List card_ids.

Return JSON: {{
  "passed": true/false,
  "drift": ["c05"],
  "gaps": ["message text that's missing"],
  "additions": ["c12"],
  "dense": ["c03", "c07"],
  "summary": "one sentence overall assessment"
}}
JSON only."""}]
    )

    check_text = check_response.content[0].text.strip()
    if check_text.startswith("```"):
        check_text = check_text.split("\n", 1)[1].rsplit("```", 1)[0]

    check = json.loads(check_text)

    (OUTPUTS / "2c_story_check.json").write_text(
        json.dumps(check, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if check.get("passed"):
        log(f"  Story check PASSED: {check.get('summary', '')}")
    else:
        log(f"  Story check FAILED: {check.get('summary', '')}")
        if check.get("drift"):
            log(f"    Drift: {check['drift']}")
        if check.get("gaps"):
            log(f"    Gaps: {check['gaps']}")
        if check.get("additions"):
            log(f"    Additions: {check['additions']}")
        if check.get("dense"):
            log(f"    Dense cards: {check['dense']}")

        # Auto-fix: regenerate drifted/dense cards
        # For now, log and proceed — full auto-fix is a future enhancement
        log("  Proceeding with current spec (auto-fix TODO)")

    # Set backgrounds
    for c in cards:
        if "background" not in c:
            c["background"] = "dark" if c.get("card_type") == "hero" else "light"

    # Save final spec
    full_spec = {
        "title": "India's Energy War",
        "subtitle": "Strategic Intelligence Briefing",
        "date": datetime.now().strftime("%B %d, %Y"),
        "audience": audience,
        "cards": cards,
    }

    spec_path = OUTPUTS / "2_card_spec.json"
    spec_path.write_text(json.dumps(full_spec, indent=2, ensure_ascii=False), encoding="utf-8")

    log(f"  Card spec finalized: {len(cards)} cards")
    return full_spec

    # ─── Original per-act generation below (kept for reference) ───

def step2_card_decomposition_legacy(client, working_document, topic, audience):
    """Legacy per-act generation. Replaced by Story Arc → Proof → Check flow."""

    from story_engine.prompts import CARD_DECOMPOSITION_SYSTEM

    ACTS = [
        {
            "act_id": "1",
            "name": "Situation",
            "instruction": "Generate 5-6 cards for Act 1: The Situation. Set the scene for a C-suite audience who needs to understand the crisis in 60 seconds. Include: hero/opening card, timeline of escalation, key exposure numbers, the triple crisis (crude + LPG + fertilizer), and duration/mine clearance insight.",
            "card_count": "5-6",
        },
        {
            "act_id": "2a",
            "name": "Refinery CEO",
            "instruction": "Generate 4-5 cards for the Refinery CEO lane. Include: act break card, crude supply alternatives (Russia/Gulf/alternatives), Nelson Complexity divide (who survives), ESMA government override, and a Monday checklist with deadlines.",
            "card_count": "4-5",
        },
        {
            "act_id": "2b",
            "name": "CFO / Treasury",
            "instruction": "Generate 4-5 cards for the CFO lane. Include: act break card, 3 price scenarios with probabilities, margin destruction (OMCs vs RIL divergence), hedging strategy (futures curve in backwardation), April 3 waiver cliff, and a Monday checklist.",
            "card_count": "4-5",
        },
        {
            "act_id": "2c",
            "name": "Policy Advisor",
            "instruction": "Generate 4-5 cards for the Policy Advisor lane. Include: act break card, SPR lever (India refused IEA), retail price freeze (OMC cash burn to insolvency), non-alignment scorecard (who's getting through Hormuz — China 11, India 3, Japan 0), and a Monday checklist.",
            "card_count": "4-5",
        },
        {
            "act_id": "2d",
            "name": "Board Director",
            "instruction": "Generate 3-4 cards for the Board Director lane. Include: act break card, company-level macro impact ($266B import bill, CAD, GDP, rupee), 3 tail risks (waiver expiry, Gulf facility strikes, dual chokepoint), and board approvals checklist.",
            "card_count": "3-4",
        },
        {
            "act_id": "3",
            "name": "Edge + Closing",
            "instruction": "Generate 3-4 cards for Act 3: The Edge. Include: act break, 4 things banks are getting wrong (duration, LPG, infrastructure damage, sour premium — use 'Banks say X vs Reality Y' format), and a closing card with key deadlines (Apr 3, Apr 5, Apr 26, June) and a single decisive closing line.",
            "card_count": "3-4",
        },
    ]

    VISUAL_INSTRUCTIONS = """
For EACH card, think HARD about the visual. Use the FULL visual vocabulary:
- waterfall_chart (sequential impact like earnings destruction)
- sankey (flow redirection like ESMA)
- gauge/tank (countdown/depletion like reserves)
- line_chart (trends like futures curve, cash burn)
- before_after_bars (price flip like Russia discount→premium)
- bubble_scatter (correlation like NCI vs GRM)
- horizontal_bar (comparison like dependency %, butterfly chart)
- map with numbered markers + legend (geographic like shipping, risk zones)
- scenario_cards (probability + price ranges)
- 2x2_matrix (strategic positioning)
- decision_tree (branching outcomes)
- quote_pair (opposing viewpoints)
- timeline (animated, phased)
- dot_grid (fleet/unit visualization)
- checklist (numbered actions with deadlines)

NEVER use the same visual type on adjacent cards.
If you have >2 horizontal_bar charts in any 5-card window, switch one to: waterfall, gauge, bubble_scatter, sankey, or 2x2_matrix.
Every graph MUST have: (1) key takeaway headline, (2) description line with units, (3) the chart.
Every chart MUST have at least one annotation (callout label, reference line, or "YOU ARE HERE" marker).
No unexplained abbreviations — spell out on first use or add footnote.
"""

    all_cards = []
    previous_cards_summary = ""

    for act in ACTS:
        log(f"  Generating Act {act['act_id']}: {act['name']} ({act['card_count']} cards)...")

        user_prompt = f"""TOPIC: {topic}
AUDIENCE: {audience}

{act['instruction']}

{VISUAL_INSTRUCTIONS}

CARDS GENERATED SO FAR (for narrative continuity):
{previous_cards_summary if previous_cards_summary else "This is the first act."}

WORKING DOCUMENT (use this data — do NOT invent numbers):
{working_document[:30000]}

Return ONLY valid JSON: {{"cards": [...]}}
Each card needs: card_id (use act prefix like "c{act['act_id']}_01"), card_type, key_message, sub_messages (with visual_type, visual_weight), relationship, data (with ALL actual numbers from the working document), source.

Generate exactly {act['card_count']} cards. No more, no less."""

        text = ""
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=CARD_DECOMPOSITION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}]
        ) as stream:
            for chunk in stream.text_stream:
                text += chunk

        # Parse JSON
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]

        try:
            spec = json.loads(text)
        except json.JSONDecodeError:
            # Repair
            for j in range(len(text)-1, 0, -1):
                if text[j] == "}":
                    try:
                        spec = json.loads(text[:j+1] + "]}")
                        break
                    except:
                        continue
            else:
                log(f"  WARNING: Could not parse Act {act['act_id']}. Skipping.")
                continue

        cards = spec.get("cards", [])

        # Set backgrounds
        for c in cards:
            c["background"] = "dark" if c.get("card_type") == "hero" else "light"
            c["act"] = act["act_id"]

        all_cards.extend(cards)

        # Build summary for next act
        previous_cards_summary = "\n".join([
            f"- {c.get('card_id','?')}: {c.get('key_message','')[:80]}"
            for c in all_cards
        ])

        log(f"    Generated {len(cards)} cards for Act {act['act_id']}. Total so far: {len(all_cards)}")

    # Score the complete deck
    visual_types = set()
    for c in all_cards:
        for sm in c.get("sub_messages", []):
            visual_types.add(sm.get("visual_type", "text"))

    log(f"  COMPLETE: {len(all_cards)} cards, {len(visual_types)} visual types")

    # Present summary to user
    print(f"\n{'='*60}")
    print(f"  CARD DECK — {len(all_cards)} CARDS")
    print(f"{'='*60}")

    current_act = ""
    for c in all_cards:
        act = c.get("act", "?")
        if act != current_act:
            current_act = act
            act_name = next((a["name"] for a in ACTS if a["act_id"] == act), act)
            print(f"\n  ACT {act}: {act_name}")
            print(f"  {'─'*50}")

        vis = [sm.get("visual_type", "?") for sm in c.get("sub_messages", [])]
        print(f"    {c.get('card_id','?'):<14} {c.get('card_type','?'):<16} {', '.join(vis)}")

    choice = human_checkpoint(
        f"Review the {len(all_cards)}-card deck above.\n"
        "Press ENTER to approve, or type feedback to adjust:"
    )

    if choice and choice.lower() != "":
        log(f"  User feedback: {choice}")
        # TODO: re-generate specific acts based on feedback

    # Save
    full_spec = {
        "title": "India's Energy War",
        "subtitle": "Strategic Intelligence Briefing",
        "date": datetime.now().strftime("%B %d, %Y"),
        "audience": audience,
        "cards": all_cards,
    }

    spec_path = OUTPUTS / "2_card_spec.json"
    spec_path.write_text(json.dumps(full_spec, indent=2, ensure_ascii=False), encoding="utf-8")

    return full_spec


# ---------------------------------------------------------------------------
# Step 3: Design Agent
# ---------------------------------------------------------------------------

def step3_design_agent(client, card_spec):
    log("STEP 3: Design Agent — generating HTML per card")

    sys.path.insert(0, str(ROOT / "design_agent"))
    from design_prompts import build_design_prompt

    cards = card_spec["cards"]
    results = []

    for i, card in enumerate(cards):
        card_id = card.get("card_id", f"card_{i}")
        card_type = card.get("card_type", "unknown")

        log(f"  [{i+1}/{len(cards)}] {card_id} ({card_type})")

        system_prompt, user_prompt = build_design_prompt(card, card_type)

        for attempt in range(3):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )

                html = response.content[0].text.strip()

                # Strip markdown fences
                if html.startswith("```"):
                    html = html.split("\n", 1)[1].rsplit("```", 1)[0]

                # Find the card div
                if '<div class="card"' in html:
                    start = html.index('<div class="card"')
                    html = html[start:]

                results.append({
                    "card_id": card_id,
                    "card_type": card_type,
                    "html": html
                })

                log(f"           OK ({len(html):,} chars)")
                break

            except Exception as e:
                log(f"           ERROR attempt {attempt+1}: {e}")
                if attempt == 2:
                    results.append({
                        "card_id": card_id,
                        "card_type": card_type,
                        "html": f'<div class="card" id="{card_id}"><div class="card-inner"><h3 class="card-title">Error generating card</h3><p class="card-sub">{str(e)[:100]}</p></div></div>'
                    })
                time.sleep(2 ** attempt)

    output = {"cards": results}
    out_path = OUTPUTS / "3_card_html.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")

    log(f"  Design Agent complete: {len(results)} cards, {sum(len(c['html']) for c in results):,} chars total")
    return output


# ---------------------------------------------------------------------------
# Step 4: Build
# ---------------------------------------------------------------------------

def step4_build(card_html):
    log("STEP 4: Build briefing HTML")

    # Save card_html to temp file, then use builder
    card_html_path = str(OUTPUTS / "3_card_html.json")
    Path(card_html_path).write_text(
        json.dumps(card_html, ensure_ascii=False), encoding="utf-8"
    )

    sys.path.insert(0, str(ROOT / "presentation_engine"))
    from builder import build_briefing

    out_path = str(OUTPUTS / "4_briefing.html")
    build_briefing(card_html_path, out_path)

    size = Path(out_path).stat().st_size
    log(f"  Built: {out_path} ({size:,} bytes)")
    return out_path


# ---------------------------------------------------------------------------
# Step 5: Critique Loop (Gate 1 + Gate 2)
# ---------------------------------------------------------------------------

def step5_critique(client, briefing_path, card_html):
    log("STEP 5: Critique Loop")

    # --- Gate 1: Content critique ---
    log("  Gate 1: Content critique (Claude Opus)...")

    html = Path(briefing_path).read_text(encoding="utf-8")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        system="You are a McKinsey senior partner. Score each card 1-10 on message clarity, visual-message alignment, and so-what strength. Return JSON array with id, score, issue, fix for each card.",
        messages=[{"role": "user", "content": f"Score each card:\n\n{html[:80000]}\n\nJSON array only."}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        gate1 = json.loads(text)
    except:
        gate1 = []
        log("  WARNING: Could not parse Gate 1 results")

    if gate1:
        scores = [r.get("score", 5) for r in gate1]
        avg = sum(scores) / len(scores)
        below = sum(1 for s in scores if s < 7)
        log(f"  Gate 1: avg {avg:.1f}/10, {below} cards below 7")

        (OUTPUTS / "5_gate1_results.json").write_text(
            json.dumps(gate1, indent=2), encoding="utf-8"
        )

    # --- Gate 2: Visual QA via screenshots ---
    log("  Gate 2: Visual QA (screenshots + multimodal)...")

    screenshots_dir = OUTPUTS / "5_screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
        import base64

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file:///{os.path.abspath(briefing_path).replace(os.sep, '/')}")
            page.wait_for_timeout(5000)

            cards = page.query_selector_all(".card")
            log(f"  Screenshotting {len(cards)} cards...")

            visual_issues = []

            for i, card in enumerate(cards):
                card.scroll_into_view_if_needed()
                page.wait_for_timeout(1000)

                ss_path = screenshots_dir / f"card_{i+1:02d}.png"
                card.screenshot(path=str(ss_path))

                # Send screenshot to Claude for visual QA (batch every 4 cards)
                if (i + 1) % 4 == 0 or i == len(cards) - 1:
                    batch_start = max(0, i - 3) if (i + 1) % 4 == 0 else i - ((i + 1) % 4 - 1)
                    batch_paths = [screenshots_dir / f"card_{j+1:02d}.png" for j in range(batch_start, i + 1)]

                    content = []
                    for bp in batch_paths:
                        with open(bp, "rb") as f:
                            img_data = base64.standard_b64encode(f.read()).decode("utf-8")
                        content.append({"type": "text", "text": f"Card {bp.stem}:"})
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": img_data}
                        })

                    content.append({
                        "type": "text",
                        "text": """Check each card for visual issues. For each card, report:
- Any text that is cut off, overlapping, or overflowing
- Any chart/map labels that overlap or are unreadable
- Any alignment issues (text not centered, elements misaligned)
- Any empty containers or missing content
- Map zoom too close (labels overlapping)

Return JSON array: [{"card": "card_01", "issues": ["text cut off on right"], "severity": "high"}]
If no issues, return empty array. JSON only."""
                    })

                    try:
                        vqa_response = client.messages.create(
                            model="claude-opus-4-6",
                            max_tokens=4096,
                            messages=[{"role": "user", "content": content}]
                        )

                        vqa_text = vqa_response.content[0].text.strip()
                        if vqa_text.startswith("```"):
                            vqa_text = vqa_text.split("\n", 1)[1].rsplit("```", 1)[0]

                        try:
                            batch_issues = json.loads(vqa_text)
                            for issue in batch_issues:
                                if issue.get("issues"):
                                    visual_issues.append(issue)
                                    log(f"    {issue['card']}: {', '.join(issue['issues'][:2])}")
                        except:
                            pass
                    except Exception as e:
                        log(f"    Visual QA batch error: {e}")

            browser.close()

        (OUTPUTS / "5_gate2_visual.json").write_text(
            json.dumps(visual_issues, indent=2), encoding="utf-8"
        )

        # --- Auto-fix visual issues ---
        if visual_issues:
            high_severity = [v for v in visual_issues if v.get("severity") == "high"]
            log(f"  Gate 2: {len(visual_issues)} issues found, {len(high_severity)} high severity")

            if high_severity:
                log("  Auto-fixing high severity visual issues...")

                cards_to_fix = set()
                fix_instructions = {}

                for issue in high_severity:
                    card_name = issue.get("card", "")
                    cards_to_fix.add(card_name)
                    fix_instructions[card_name] = issue.get("issues", [])

                # Regenerate problem cards
                card_html_data = card_html
                spec_data = json.loads((OUTPUTS / "2_card_spec.json").read_text(encoding="utf-8"))

                sys.path.insert(0, str(ROOT / "design_agent"))
                from design_prompts import build_design_prompt

                for card_name in cards_to_fix:
                    # Find the card spec
                    card_idx = int(card_name.replace("card_", "")) - 1
                    if card_idx < len(spec_data["cards"]):
                        card = spec_data["cards"][card_idx]
                        card_id = card.get("card_id", card_name)
                        card_type = card.get("card_type", "unknown")

                        # Add fix instructions to the card
                        card["_fix_instructions"] = fix_instructions[card_name]

                        log(f"    Regenerating {card_id}: {fix_instructions[card_name][:2]}")

                        system_prompt, user_prompt = build_design_prompt(card, card_type)
                        user_prompt += f"\n\nIMPORTANT FIX: The previous version had these visual issues: {json.dumps(fix_instructions[card_name])}. Fix them in this version."

                        try:
                            response = client.messages.create(
                                model="claude-sonnet-4-6",
                                max_tokens=8192,
                                system=system_prompt,
                                messages=[{"role": "user", "content": user_prompt}]
                            )

                            new_html = response.content[0].text.strip()
                            if new_html.startswith("```"):
                                new_html = new_html.split("\n", 1)[1].rsplit("```", 1)[0]
                            if '<div class="card"' in new_html:
                                new_html = new_html[new_html.index('<div class="card"'):]

                            # Replace in card_html
                            for j, ch in enumerate(card_html_data["cards"]):
                                if ch["card_id"] == card_id:
                                    card_html_data["cards"][j]["html"] = new_html
                                    log(f"    Fixed {card_id} ({len(new_html):,} chars)")
                                    break
                        except Exception as e:
                            log(f"    Fix failed for {card_id}: {e}")

                # Rebuild
                log("  Rebuilding with fixes...")
                (OUTPUTS / "3_card_html.json").write_text(
                    json.dumps(card_html_data, ensure_ascii=False), encoding="utf-8"
                )
                step4_build(card_html_data)
                log("  Rebuilt with visual fixes applied.")
        else:
            log("  Gate 2: No visual issues found.")

    except ImportError:
        log("  WARNING: Playwright not available. Skipping Gate 2.")
    except Exception as e:
        log(f"  Gate 2 error: {e}")

    return gate1


# ---------------------------------------------------------------------------
# Step 6: Final Review
# ---------------------------------------------------------------------------

def step6_final_review(briefing_path):
    log("STEP 6: Final Review")

    # Open in browser
    os.startfile(briefing_path)

    while True:
        feedback = human_checkpoint(
            "Briefing is open in your browser.\n\n"
            "Options:\n"
            "  ENTER     → Ship it (deploy to GitHub Pages)\n"
            "  'fix N'   → Fix card N (e.g., 'fix 7')\n"
            "  'done'    → Save and exit without deploying\n"
        )

        if not feedback or feedback.lower() == "done":
            log("  Final review complete.")
            return feedback
        elif feedback.lower().startswith("fix"):
            log(f"  User requested: {feedback}")
            print(f"  Note: manual fix requested. Edit card spec and re-run Design Agent for that card.")
            # TODO: implement single-card re-generation
        else:
            log(f"  User feedback: {feedback}")


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Briefing Engine — End-to-end pipeline")
    parser.add_argument("--topic", required=True, help="Briefing topic")
    parser.add_argument("--audience", required=True, help="Target audience")
    parser.add_argument("--resume", type=int, default=0, help="Resume from step N")
    args = parser.parse_args()

    # Clear log
    (OUTPUTS / "pipeline.log").write_text("", encoding="utf-8")

    log(f"BRIEFING ENGINE")
    log(f"  Topic:    {args.topic}")
    log(f"  Audience: {args.audience}")
    log(f"  Resume:   step {args.resume}")
    log(f"  Started:  {datetime.now().isoformat()}")

    load_api_key()

    import anthropic
    client = anthropic.Anthropic()

    # --- Step 0 ---
    if args.resume <= 0:
        problem = step0_problem_framing(client, args.topic, args.audience)
    else:
        problem = (OUTPUTS / "0_problem_statement.txt").read_text(encoding="utf-8")

    # --- Step 1 ---
    if args.resume <= 1:
        working_doc = step1_research(client, problem, args.topic, args.audience)
    else:
        working_doc = (OUTPUTS / "1_working_document.md").read_text(encoding="utf-8")

    # --- Step 2 ---
    if args.resume <= 2:
        card_spec = step2_card_decomposition(client, working_doc, args.topic, args.audience)
    else:
        card_spec = json.loads((OUTPUTS / "2_card_spec.json").read_text(encoding="utf-8"))

    # --- Step 3 (automated) ---
    card_html = step3_design_agent(client, card_spec)

    # --- Step 4 (automated) ---
    briefing_path = step4_build(card_html)

    # --- Step 5 (automated) ---
    critique = step5_critique(client, briefing_path, card_html)

    # --- Step 6 ---
    step6_final_review(briefing_path)

    log(f"PIPELINE COMPLETE: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()

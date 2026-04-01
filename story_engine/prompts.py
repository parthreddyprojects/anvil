"""Prompt templates for each step of the Story Engine pipeline."""

# ---------------------------------------------------------------------------
# Step 0 – Problem Framing
# ---------------------------------------------------------------------------

PROBLEM_FRAMING_SYSTEM = """\
You are a senior strategic intelligence analyst. Your job is to frame \
analytical problems with precision. You write for decision-makers who need \
clarity under time pressure."""

PROBLEM_FRAMING_USER = """\
TOPIC: {topic}
AUDIENCE: {audience}

Draft the following:

1. A SMART problem statement in the form:
   "Within [timeframe], what should [AUDIENCE] decide to [OBJECTIVE] given [CONSTRAINTS]?"
   Rules:
   - Always a QUESTION, not a statement
   - Name the decision-maker, the domain, the geography
   - Include a measurable target or threshold
   - Time-bound with explicit deadline
   - Include a decision sensitivity break point: the number at which the
     opposite recommendation becomes correct

2. A MECE (Mutually Exclusive, Collectively Exhaustive) breakdown into 4-7 buckets.

   PURPOSE — EXPLORATORY, NOT PRESCRIPTIVE:
   Sub-questions must be INVESTIGATIVE — they map the landscape of facts,
   dynamics, constraints, and uncertainties. They do NOT prescribe actions.
   Think of them as the research questions an analyst must answer BEFORE
   anyone can recommend what to do.

   BAD (prescriptive): "What new markets should the company enter within 6 months?"
   GOOD (exploratory): "Which adjacent markets have >$500M TAM, <3 established
   competitors, and alignment with the company's existing capabilities and
   distribution channels?"

   BAD: "How should the company hedge its currency exposure?"
   GOOD: "What is the company's current unhedged currency exposure by currency
   pair and duration, and how does it compare to peer benchmarks?"

   The sub-questions should surface FACTS, MAGNITUDES, DYNAMICS, COMPARISONS,
   and UNCERTAINTIES — not recommendations. Recommendations come later in
   Step 4 (Hypotheses), where testable claims directly answer the problem
   statement using the evidence gathered from these exploratory questions.

   CRITICAL — EXHAUSTIVENESS PROTOCOL:
   Before writing sub-questions for each bucket, you MUST first enumerate ALL
   possible dimensions that could belong in that bucket. Use these lenses:

   a) SOURCES: List every possible source/origin (e.g., for revenue: existing
      customers, new segments, adjacent markets, partnerships, acquisitions,
      pricing changes, upsell/cross-sell, geographic expansion)
   b) ASSETS: List every relevant asset and differentiate them
      (e.g., each business unit has different capabilities, margins, growth rates)
   c) CONSTRAINTS: For each source/asset, what limits it? (capital, talent,
      regulatory, competitive, technological, contractual, timeline)
   d) TIME HORIZONS: Does the bucket need sub-questions for immediate (0-5d),
      near-term (5-30d), and medium-term (30-90d)?
   e) STAKEHOLDERS: Who else is involved? (competitors, government, NOCs,
      banks, insurers, workforce, communities)
   f) SECOND-ORDER EFFECTS: What cascades from this bucket into others?

   For each bucket, provide:
   - A clear headline framed as an EXPLORATORY question (e.g., "What is the
     current competitive landscape and how is it shifting?")
   - A one-sentence rationale for why this bucket is necessary
   - 6-10 sub-questions that EXHAUST the bucket — one per dimension identified above
   - Each sub-question must be INVESTIGATIVE and SPECIFIC — it asks about a
     fact, magnitude, dynamic, comparison, or uncertainty (contains WHAT, WHERE,
     HOW MUCH, COMPARED TO WHAT). Do NOT use "should" or "how to" phrasing.
   - After writing sub-questions, do a COMPLETENESS CHECK: "If I answer all these
     sub-questions, is there any FACT or DYNAMIC within this bucket I still do
     not understand?" If yes, add the missing sub-question.

   STRUCTURAL COMPLETENESS CHECK:
   After writing all buckets, verify:
   - Is there a bucket for the CURRENT STATE (inventory, position, exposure)?
   - Is there a bucket for the LANDSCAPE OF OPTIONS (what exists, what is available)?
   - Is there a bucket for OPERATIONAL REALITIES (capacity, configuration, constraints)?
   - Is there a bucket for FINANCIAL/COMMERCIAL exposure (margins, cash, credit)?
   - Is there a bucket for RISK FACTORS (insurance, force majeure, counterparty)?
   - Is there a bucket for MARKET DYNAMICS (competitors, substitutes, pricing)?
   - Is there a bucket for REGULATORY/POLITICAL environment (policy, mandates, precedent)?
   If any of these dimensions is missing entirely, add a bucket.

Return ONLY valid JSON matching this schema (no markdown fences):
{{
  "smart_statement": "...",
  "decision_sensitivity": "...",
  "sections": [
    {{
      "section_id": 1,
      "title": "...",
      "rationale": "...",
      "dimensions_enumerated": ["source X", "source Y", "constraint Z", "..."],
      "questions": [
        {{"id": "1.1", "question": "..."}},
        ...
      ],
      "completeness_check": "What decision within this bucket can I still not make after answering all sub-questions? None / [gap identified]"
    }},
    ...
  ]
}}"""

# ---------------------------------------------------------------------------
# Step 0b – MECE Audit (adversarial gap analysis)
# ---------------------------------------------------------------------------

MECE_AUDIT_SYSTEM = """\
You are a ruthless quality-assurance analyst at McKinsey. Your ONLY job is to \
find gaps in MECE decompositions. You are paranoid about missing dimensions. \
You treat "probably covered" as "definitely missing." You never rubber-stamp."""

MECE_AUDIT_USER = """\
Below is a MECE decomposition for a strategic problem statement. Your job is \
to audit it for EXHAUSTIVENESS — not style, not wording, just: are there gaps?

IMPORTANT: Sub-questions must be EXPLORATORY, not prescriptive. They should \
investigate facts, magnitudes, dynamics, comparisons, and uncertainties — NOT \
recommend actions. If you find sub-questions that say "should", "how to", or \
prescribe what the audience ought to do, flag them and rewrite as investigative \
questions. Recommendations belong in the Hypotheses step, not here.

PROBLEM STATEMENT:
{smart_statement}

AUDIENCE: {audience}

CURRENT DECOMPOSITION:
{decomposition_json}

For EACH bucket, do the following:

1. LIST every dimension that SHOULD exist in this bucket using these lenses:
   - Every possible SOURCE or ORIGIN of the thing being analyzed
   - Every relevant ASSET, ENTITY, or ACTOR that should be differentiated
   - Every CONSTRAINT that could limit options (physical, financial, regulatory,
     logistical, contractual, political, safety, environmental)
   - Every TIME HORIZON that matters (immediate, near-term, medium-term)
   - Every STAKEHOLDER whose actions affect this bucket
   - Every SECOND-ORDER EFFECT or cascade

2. CHECK each dimension against the existing sub-questions. Mark as:
   - ✅ COVERED — an existing sub-question addresses this dimension
   - ❌ MISSING — no sub-question addresses this dimension

3. For each ❌ MISSING dimension, write a new sub-question that closes the gap.
   The question must be EXPLORATORY and SPECIFIC — it investigates a fact,
   magnitude, dynamic, or uncertainty (WHAT, WHERE, HOW MUCH, COMPARED TO WHAT).
   Do NOT write prescriptive questions ("should", "how to").

4. STRUCTURAL CHECK — after auditing all buckets:
   - Is there an ENTIRE BUCKET missing? (e.g., no bucket for risk, no bucket
     for medium-term strategy, no bucket for stakeholder engagement)
   - Are any sub-questions DUPLICATED across buckets? Flag them.

Return ONLY valid JSON matching this schema (no markdown fences):
{{
  "bucket_audits": [
    {{
      "section_id": 1,
      "title": "...",
      "dimensions_found": [
        {{"dimension": "...", "status": "covered", "existing_question_id": "1.2"}},
        {{"dimension": "...", "status": "missing", "new_question": {{"id": "1.6", "question": "..."}}}}
      ],
      "completeness_verdict": "exhaustive" | "gaps_found"
    }}
  ],
  "missing_buckets": [
    {{
      "title": "...",
      "rationale": "...",
      "questions": [
        {{"id": "7.1", "question": "..."}},
        ...
      ]
    }}
  ],
  "duplicate_flags": [
    {{"question_ids": ["1.3", "3.2"], "reason": "Both ask about the same competitive dynamic"}}
  ],
  "overall_verdict": "pass" | "gaps_found",
  "total_questions_added": 0
}}"""

# ---------------------------------------------------------------------------
# Step 0c – MECE Merge (apply audit results)
# ---------------------------------------------------------------------------

MECE_MERGE_SYSTEM = """\
You are a precise data-merge tool. You take an original MECE decomposition and \
an audit result, and produce a clean merged output. You do NOT editorialize — \
you mechanically apply the additions."""

MECE_MERGE_USER = """\
ORIGINAL DECOMPOSITION:
{original_json}

AUDIT RESULT:
{audit_json}

Merge the audit findings into the original decomposition:
1. For each bucket, append any new questions identified as "missing" by the audit.
   Renumber sequentially (e.g., if bucket 2 had 2.1-2.6, new questions become 2.7, 2.8, etc.)
2. Add any entirely new buckets from "missing_buckets".
3. Do NOT remove or reword existing questions — only ADD.
4. Update dimensions_enumerated to include newly identified dimensions.
5. Update completeness_check to reflect the post-audit state.

Return the COMPLETE merged decomposition in the EXACT same JSON schema as the \
original (with smart_statement, decision_sensitivity, sections array). \
No markdown fences."""

# ---------------------------------------------------------------------------
# Step 0 – Problem Framing (revision)
# ---------------------------------------------------------------------------

PROBLEM_FRAMING_REVISION = """\
The analyst reviewed your problem framing and provided this feedback:

FEEDBACK: {feedback}

Here is the previous output:
{previous_output}

Revise the problem statement and MECE breakdown to incorporate the feedback. \
Return the same JSON schema as before."""

# ---------------------------------------------------------------------------
# Step 1 – Research Prompts
# ---------------------------------------------------------------------------

RESEARCH_PROMPT_SYSTEM = """\
You are a research director designing web-search briefs for junior analysts. \
Each brief must be self-contained and actionable."""

RESEARCH_PROMPT_USER = """\
TOPIC: {topic}
AUDIENCE: {audience}
PROBLEM STATEMENT: {smart_statement}

SECTION {section_id}: {section_title}
RATIONALE: {rationale}
QUESTIONS:
{questions_formatted}

Write a detailed research prompt that an analyst (or AI agent with web search) \
can use to find answers to ALL the above questions. The prompt should:
- Specify what data, reports, and sources to look for
- Include specific search queries to try
- Note what date ranges matter
- Flag any numbers or statistics that must be found

Return the prompt as plain text (no JSON)."""

# ---------------------------------------------------------------------------
# Step 2 – Working Document
# ---------------------------------------------------------------------------

WORKING_DOCUMENT_SYSTEM = """\
You are a senior analyst at a strategic advisory firm. You write concise, \
evidence-backed briefing documents for C-suite executives. Every claim must \
be grounded in the research provided. Use short paragraphs, bullet points \
for data, and bold assertions where the evidence is strong."""

WORKING_DOCUMENT_USER = """\
TOPIC: {topic}
AUDIENCE: {audience}
PROBLEM STATEMENT: {smart_statement}

MECE STRUCTURE:
{mece_structure}

COMPILED RESEARCH:
{research}

Write a working document with:
1. A title
2. An executive summary (3-4 sentences)
3. One section per MECE section, each containing:
   - A narrative body (2-3 paragraphs)
   - 3-5 key findings as bullet points
4. An analyst compare/contrast section with at least 2 opposing viewpoints \
   (e.g. bull vs bear, hawk vs dove, optimist vs pessimist) — each with a \
   label and a 2-3 sentence summary.

Return ONLY valid JSON matching this schema (no markdown fences):
{{
  "title": "...",
  "executive_summary": "...",
  "sections": [
    {{
      "section_id": 1,
      "title": "...",
      "body": "...",
      "key_findings": ["...", "..."]
    }},
    ...
  ],
  "analyst_compare_contrast": [
    {{"analyst_label": "Bull case", "summary": "..."}},
    {{"analyst_label": "Bear case", "summary": "..."}}
  ]
}}"""

# ---------------------------------------------------------------------------
# Step 3 – Card Decomposition
# ---------------------------------------------------------------------------

CARD_DECOMPOSITION_SYSTEM = """\
You are a presentation strategist who converts analyst reports into visual \
card decks. Each card must carry ONE key message with 2-3 supporting \
sub-messages. You think visually: every piece of data gets matched to the \
right visual form using strict rules."""

CARD_DECOMPOSITION_USER = """\
TOPIC: {topic}
AUDIENCE: {audience}

WORKING DOCUMENT:
{working_document}

Convert this into a card deck. The deck follows a 3-act structure:

Act 1 — Situation (act="1"): Set the scene. Hero card, timeline, KPIs.
Act 2a — Operations lens (act="2a"): Operational impact and constraints.
Act 2b — Financial lens (act="2b"): Financial exposure, margin/P&L impact.
Act 2c — External lens (act="2c"): Regulatory, competitive, or market dynamics.
Act 2d — Strategic lens (act="2d"): Strategic options, risk appetite, long-term positioning.
Act 3 — Edge (act="3"): Contrarian signals, what others are missing.

For EACH card, think HARD about what visual tells the story best. Don't default \
to bar charts and text. Consider the FULL visual vocabulary:

VISUAL DECISION TREE (apply in order):
1. Can a single BIG NUMBER prove it? → "big_number" (e.g., 3.2x, -$40M, 12 days)
2. Does sequential IMPACT matter? → "waterfall_chart" (margin erosion step by step)
3. Does FLOW or REDIRECTION matter? → "sankey" or flow diagram (resource reallocation)
4. Does COUNTDOWN or DEPLETION matter? → "gauge" or "tank" (runway, capacity)
5. Does the SHAPE of change matter? → "line_chart" (trend, forecast, cash burn)
6. Does BEFORE vs AFTER matter? → "before_after_bars" (pre/post comparison)
7. Does GEOGRAPHIC POSITION matter? → "map" with numbered markers + legend
8. Does RANKING or COMPARISON matter? → "horizontal_bar" (butterfly chart) or "bubble_scatter"
9. Does PROBABILITY matter? → "scenario_cards" with gradient tints
10. Does STRATEGIC POSITION matter? → "2x2_matrix" (capability × opportunity)
11. Is it a TIMELINE? → animated timeline with pulsing dots and phase colors
12. Is it a DECISION? → "decision_tree" with branching outcomes
13. Is it opposing VIEWPOINTS? → "quote_pair" side by side
14. Is it ACTIONS? → "checklist" with numbered items and deadlines
15. None of the above? → "text" with strong typographic hierarchy

THINK CREATIVELY: For each card, ask yourself: "Is there a chart type that would \
make this message UNDENIABLE in 3 seconds?" If a waterfall chart shows margin \
eroding step by step, that's more powerful than a bar chart. If a gauge shows \
runway depleting, that's more visceral than a number. If a Sankey shows resources \
being reallocated between divisions, that's more dramatic than bullet points.

Card types: hero, timeline, kpi_card, verdict_panel, scenario_card, checklist, \
chart_card, map_card, quote_pair, act_break, closing.

Relationships: cause_effect, before_after, compare_contrast, parallel, escalating.

Generate 15-25 cards covering all sections. Include act_break cards between acts.

Return ONLY valid JSON matching this schema (no markdown fences):
{{
  "cards": [
    {{
      "card_id": "card_01",
      "act": "1",
      "card_type": "hero",
      "key_message": "One sentence.",
      "sub_messages": [
        {{
          "text": "...",
          "visual_weight": "3/4",
          "visual_type": "big_number",
          "chart_type": null
        }},
        {{
          "text": "...",
          "visual_weight": "1/4",
          "visual_type": "text",
          "chart_type": null
        }}
      ],
      "relationship": "cause_effect",
      "visual_decision": "Reasoning for visual choices...",
      "data": {{"key": "value", "numbers": 42}},
      "source": "Attribution line"
    }},
    ...
  ]
}}"""

# Slide Deck Automator — Product Spec v2
## Decision Document Generator

### What It Is
Takes a topic + audience + brief type → produces a one-pager decision document + appendix slides with proof. Every claim sourced, triangulated, stress-tested. 100x better than MBB in depth, speed, and transparency.

### Output Format
- One-pager: HTML + PDF (5 fixed sections, clean memo format)
- Appendix: HTML + PDF slides (one chart per page, MBB style)
- Each appendix slide maps 1:1 to a sentence on the one-pager

---

## THE ONE-PAGER (5 sections, fixed order)

| Section | Purpose | Constraint |
|---------|---------|------------|
| 1. Header | Signal what is being decided | Title = conclusion, not topic label |
| 2. Situation | Establish stakes | 2-3 sentences max. One anchor number. What happens if nothing is done. |
| 3. Performance data | Validate with numbers | 3-4 KPIs only. Every KPI has a variance — never a raw number alone. |
| 4. Analysis | Defend diagnosis OR present choice OR report progress | Pick ONE form based on brief type: root causes (problem), options (decision), findings (update). 3 items max, each quantified. |
| 5. Decision required | State what is needed from the room | 2-3 numbered asks. Each specific. Each sized (₹ amount or scope). No vague language. |

---

## THE APPENDIX (4 slot types)

| Slot | Purpose | Format | Trigger |
|------|---------|--------|---------|
| A | Prove a number on the one-pager | Bridge / waterfall / variance table | One per KPI that needs defending |
| B | Prove a claim or finding | Benchmark / causal chain / scenario model / peer comparison | One per root cause, finding, or claim |
| C | Prove a choice is the right one | Comparison matrix (options as columns, criteria as rows) | One per option set |
| D | Prove an ask is executable | Implementation timeline / resource plan / governance / containment playbook* | One per ask requiring approval |

*Crisis brief: slot D = containment playbook, not implementation plan
*Initiative brief: slot A = milestone tracker, not financial bridge

### Slot activation by brief type:

| Brief type | A | B | C | D |
|------------|---|---|---|---|
| Performance review | ✅ | ✅ | ❌ | ❌ |
| Strategic decision | ❌ | ✅ | ✅ | ✅ |
| Capital allocation | ✅ | ✅ | ✅ | ✅ |
| Crisis / exception | ✅ | ✅ | ❌ | ✅ |
| Initiative update | ✅ | ✅ | ❌ | ✅ |
| External briefing | ✅ | ✅ | ❌ | ❌ |

### The mapping rule:
Every sentence on the one-pager that makes a claim must be provable by exactly one appendix slide. Every appendix slide must map back to exactly one sentence on the one-pager. Anything that doesn't satisfy both directions gets cut.

---

## PIPELINE

```
═══════════════════════════════════════════════════════════════
STEP 0: PROBLEM FRAMING (per problem statement)
═══════════════════════════════════════════════════════════════

  Input: topic + audience + segment description

  STEP 0A: SMART PROBLEM STATEMENT
    Format: "Within [timeframe], what should [AUDIENCE] decide to
             [OBJECTIVE] given [CONSTRAINTS]?"
    Rules:
      - Always a QUESTION, not a statement
      - Name the decision-maker, domain, geography
      - Include measurable target or threshold
      - Time-bound with explicit deadline
      - Include DECISION SENSITIVITY BREAK POINT: the number at
        which the opposite recommendation becomes correct
      - Problem statement is ONLY the decision question — no
        situation data (prices, events). That goes in one-pager S2.

  STEP 0B: MECE DECOMPOSITION (improved prompt)
    Generate 4-7 MECE buckets, each with 6-10 sub-questions.
    EXHAUSTIVENESS PROTOCOL baked into prompt:
      a) SOURCES — enumerate every possible origin
      b) ASSETS — differentiate each physical asset
      c) CONSTRAINTS — logistics, financial, regulatory, political
      d) TIME HORIZONS — immediate, near-term, medium-term
      e) STAKEHOLDERS — competitors, government, NOCs, banks, etc.
      f) SECOND-ORDER EFFECTS — cascades across buckets
    Each bucket gets a COMPLETENESS CHECK before finalizing.
    STRUCTURAL CHECK: verify buckets exist for current state,
      alternatives, operations, financial, risk, strategic, stakeholder.

  STEP 0C: MECE AUDIT (adversarial)
    Separate LLM call plays McKinsey QA analyst:
      - For each bucket: enumerate ALL dimensions, mark ✅/❌
      - Write new sub-questions for every ❌ MISSING dimension
      - Flag entirely missing buckets
      - Flag duplicates across buckets

  STEP 0D: MERGE
    Mechanically merge audit gaps into original decomposition.
    Only ADD — never remove or reword existing questions.

  Output: problem_statement.json with MECE decomposition
  Typical result: 9 buckets, 100-115 questions per PS
  ← HUMAN: approve/adjust

═══════════════════════════════════════════════════════════════
STEP 1: RESEARCH (80/20 tiered, common pool)
═══════════════════════════════════════════════════════════════

  STEP 1A: TIER SCORING
    LLM scores each question (across all problem statements) for
    DECISION IMPACT on a 3-tier scale:

    TIER 1 — "Must research" (drives the actual decision)
      Score criteria: If you get this wrong, the recommendation
      flips. Numbers that feed directly into GRM, inventory runway,
      or procurement economics.
      Examples: crude inventory days, alternative crude prices,
        waiver status, SPR availability, MRPL gap volume
      Research depth: DEEP — multiple sources, triangulated numbers,
        chain of custody, confidence intervals

    TIER 2 — "Should research" (important context, shapes options)
      Score criteria: Affects the quality of the recommendation
      but doesn't flip it alone. Constrains or enables Tier 1.
      Examples: crude compatibility matrices, crack spreads by
        product, financial covenants, logistics constraints,
        stakeholder engagement status
      Research depth: MODERATE — 1-2 good sources, key numbers,
        directional confidence

    TIER 3 — "Extrapolate" (nice-to-have, can be inferred)
      Score criteria: Answerable from Tier 1+2 findings + domain
      knowledge + reasonable assumptions. Would not change the
      recommendation even if wrong.
      Examples: cyber security posture, catalyst inventory levels,
        workforce/union considerations, medium-term infra capex,
        legal/fiduciary technicalities
      Research depth: NONE — synthesized from Tier 1+2 data +
        domain reasoning in the working document step

  STEP 1B: DEDUPLICATION INTO COMMON RESEARCH THEMES
    Many questions overlap across PS1/PS2/PS3 (crude prices, waiver
    status, SPR, MRPL impact). Deduplicate into:

    COMMON RESEARCH BRIEFS (research once, apply 3 ways):
      - Crude market state (prices, curves, spreads)
      - Russia waiver status and probability
      - SPR inventory and release mechanisms
      - MRPL shutdown impact and product gap
      - Alternative crude availability by source
      - Government policy signals
      - War-risk insurance market
      - Freight and logistics

    SEGMENT-SPECIFIC BRIEFS (unique per PS):
      - PS1: Export market opportunities, petrochemical integration
      - PS2: Subsidy mechanisms, inter-refinery optimization, ESMA
      - PS3: Shutdown sequencing, minimum throughput thresholds

    Target: ~12-15 common + ~5-6 per segment = ~27-33 research briefs
    (vs 329 individual questions — 10x reduction in research load)

  STEP 1C: RESEARCH EXECUTION
    For each brief (Tier 1 and Tier 2):
      - Generate specific search queries
      - Specify data sources (EIA, Platts, Argus, Kpler, MoPNG,
        company filings, broker reports, news)
      - Execute via web-search agents (parallel)
      - Quality features on Tier 1:
          * Source quality scoring (primary > analyst > news > opinion)
          * Triangulation (3 sources min for critical numbers)
          * Recency weighting (flag stale data)
          * Chain of custody (trace every number to original source)
      - Quality features on Tier 2:
          * 1-2 good sources per number
          * Directional confidence (high/medium/low)
          * Flag where data is estimated vs confirmed

    Output: research_briefs/*.md (one per theme)

  STEP 1D: COMPILE & MAP
    Map each research brief back to the specific questions it answers
    across all 3 problem statements. Flag any Tier 1/2 question that
    remains unanswered after research — these become targeted follow-ups.

    Output: research_compiled.md + coverage_map.json
    ← HUMAN: review coverage

═══════════════════════════════════════════════════════════════
STEP 2: WORKING DOCUMENT (per problem statement)
═══════════════════════════════════════════════════════════════

  Input: MECE decomposition + compiled research + coverage map

  For each bucket in the MECE decomposition:
    - Tier 1 questions: Answer with researched data, sourced numbers
    - Tier 2 questions: Answer with researched data, note confidence
    - Tier 3 questions: EXTRAPOLATE from Tier 1+2 findings using
      domain knowledge and reasonable assumptions. Clearly mark as
      "Extrapolated from [Tier 1/2 finding X]" so reader knows.

  Include:
    - Executive summary (3-4 sentences)
    - Narrative per bucket with key findings
    - Analyst compare/contrast (bull vs bear, hawk vs dove)
    - Assumption register (what we assumed for Tier 3 answers)

  Output: working_document.md + working_document.json
  ← HUMAN: review

═══════════════════════════════════════════════════════════════
STEP 3: HYPOTHESIS TREE
═══════════════════════════════════════════════════════════════

  Generate 15-20 hypotheses structured as MECE tree from working doc
  Quality features:
    - Second-order effects (map cascades, not just first dominos)
    - Historical pattern matching (which past crisis resembles this)
    - Contrarian search (strongest counterargument per branch)
    - Test each leaf against Tier 1/2 data
    - Mark confirmed/killed/uncertain
    - Hypothesis graveyard with reasoning
  Output: hypothesis_tree.json
  ← HUMAN: review tree

═══════════════════════════════════════════════════════════════
STEP 4: ONE-PAGER (per problem statement)
═══════════════════════════════════════════════════════════════

  5 fixed sections from surviving branches:
    1. Header: conclusion + decision sensitivity break point
    2. Situation: anchor number with confidence interval (2-3 sentences)
    3. Performance data: 3-4 KPIs with variance, never raw numbers alone
    4. Analysis: ONE form based on brief type (root causes / options / findings)
    5. Decision required: 2-3 numbered asks, each specific and sized

  Output: one_pager.html
  ← HUMAN: approve

═══════════════════════════════════════════════════════════════
STEP 5: APPENDIX
═══════════════════════════════════════════════════════════════

  One slide per provable claim on the one-pager:
    - Slot A: Prove a number (bridge / waterfall / variance table)
    - Slot B: Prove a claim (benchmark / causal chain / scenario)
    - Slot C: Prove a choice (comparison matrix)
    - Slot D: Prove an ask is executable (timeline / resource plan)
    - Graveyard slot: dead hypotheses + why

  The mapping rule: every one-pager sentence with a claim maps 1:1
  to exactly one appendix slide. Both directions must hold.

  Output: appendix/*.html

═══════════════════════════════════════════════════════════════
STEP 6: CRITIQUE
═══════════════════════════════════════════════════════════════

  Multi-perspective review:
    - MBB Partner (story, redundancy, rigor)
    - Target Reader (clarity, actionability, what's missing)
    - Design Director (chart selection, visual proof)
  Auto-fix flagged issues.

═══════════════════════════════════════════════════════════════
STEP 7: EXPORT
═══════════════════════════════════════════════════════════════

  HTML + PDF for one-pager and appendix per problem statement.

═══════════════════════════════════════════════════════════════
STEP 8: REAL-TIME MONITORING (post-delivery)
═══════════════════════════════════════════════════════════════

  Watch assumptions. Alert if stale.
  "If Brent crosses $120, Section 2 needs updating."
```

---

## HUMAN CHECKPOINTS

| Step | What human reviews | Time required |
|------|-------------------|---------------|
| 1 | Problem statement + break points | 2 min |
| 2 | Working document (data quality) | 5 min |
| 3 | Hypothesis tree structure | 3 min |
| 6 | One-pager content | 3 min |

Total human time: ~13 minutes
Total automated time: ~30 minutes
Total: ~45 minutes from topic to decision document

---

## RESEARCH QUALITY FEATURES (what makes this 100x better than MBB)

| # | Feature | What it does | Where in pipeline |
|---|---------|-------------|-------------------|
| 1 | Source quality scoring | Primary > analyst > news > opinion | Step 2 |
| 2 | Triangulation | 3 sources min for critical numbers | Step 2 |
| 3 | Recency weighting | Flag stale data | Step 2 |
| 4 | Contrarian search | Find strongest counterargument | Step 3 |
| 5 | Blind spot detection | What did no source address | Step 4 |
| 6 | Chain of custody | Trace every number to original | Step 2 |
| 7 | Assumption surfacing | Name assumptions behind claims | Step 4 |
| 8 | Real-time monitoring | Watch assumptions, alert if stale | Step 10 |
| 9 | Hypothesis graveyard | Why dead branches died | Step 5 |
| 10 | Second-order effects | Map cascades, not just first dominos | Step 3 |
| 11 | Decision sensitivity | Break points where recommendation flips | Step 1, 6 |
| 12 | Peer intelligence | What competitors are actually doing | Step 2 |
| 13 | Historical pattern matching | Which past crisis resembles this | Step 3 |
| 14 | Confidence intervals | Ranges not point estimates | Step 4 |
| 15 | Pre-mortem | If this fails, most likely reason why | Step 6 |

---

## MBB SLIDE DESIGN RULES (for appendix)

Each appendix slide follows:
```
ACTION TITLE (conclusion in 8-12 words)
SUBTITLE (units, time period, source)
BODY (one chart or one table — the proof)
SOURCE LINE (chain of custody)
```

Rules:
- One message per slide
- One chart per slide
- 3-4 colors max
- Action title = takeaway, not topic
- Every chart has: title, units, legend, source
- No paragraphs — charts, tables, or structured bullets only
- FT Visual Vocabulary determines chart type from data relationship

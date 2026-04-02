#!/usr/bin/env python3
"""Run 4 problem statements end-to-end in autopilot mode."""
import json, os, sys, time, traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

ALL_CASES = [
    {
        "id": "saas_ai_disruption",
        "topic": "What strategic moves should a mid-market B2B SaaS company ($50-500M ARR, vertical or horizontal) make in the next 1-3 years to defend its position, adapt its business model, and avoid displacement by AI-native competitors or incumbents embedding AI at marginal cost?",
        "audience": "CEO, CPO, CFO; board is growth-oriented but increasingly nervous about NRR compression",
        "context": "AI-native startups are rebuilding SaaS workflows end-to-end (Cursor vs GitHub Copilot vs legacy IDEs; Glean vs legacy search; etc.). Large incumbents (Salesforce, SAP, ServiceNow) are embedding AI into existing seats at near-zero incremental cost, compressing willingness-to-pay for point solutions. Per-seat pricing is under structural pressure as AI reduces headcount and changes the unit of value delivery. Customer switching costs -- historically the moat -- are being eroded by AI-assisted migration tools and API-first architecture. The company has an existing installed base, proprietary data, and workflow integrations -- all potential moats if leveraged correctly. Constraints: Cannot do a full product rebuild in under 12 months; M&A is possible but not guaranteed; must protect EBITDA margins while investing.",
    },
    {
        "id": "indian_psu_hormuz",
        "topic": "What should India's state-owned downstream refiners (IOCL, BPCL, HPCL) do in the next 30 days to optimize crude supply, refining margins, and stakeholder confidence given the active closure of the Strait of Hormuz?",
        "audience": "CMD, Director Refining, Director Finance; MoPNG has pricing veto and is the ultimate authority on strategic reserve drawdown",
        "context": "The Strait of Hormuz has been effectively closed since March 2, 2026, following US-Israeli strikes on Iran that killed Supreme Leader Khamenei. This is not a scenario -- it is the operating reality. Daily transits have fallen 90-95% with hundreds of tankers trapped inside the Persian Gulf. Brent peaked at $126/bbl. India is among the most acutely exposed: 53% of LNG imports and roughly 60% of crude imports originate from Gulf producers transiting Hormuz. Iraqi Basra crude -- India's single largest source -- has been cut 70% from 3.3 million bpd to 900,000 bpd. Saudi Aramco, ADNOC, and KPC have all invoked force majeure; long-term OSP contracts are effectively suspended. Refineries configured for medium-sour Gulf crude; shifting to light sweet alternatives requires yield trade-offs taking weeks. Alternative sourcing via Cape of Good Hope adds 15-25 days. War risk insurance 4-5x pre-conflict. Strategic petroleum reserves cover only 9.5 days. Iran selectively allows Chinese vessels to transit, creating two-tier market. Trump extended ultimatum on striking Iranian energy infrastructure to April 6. MoPNG under political pressure to hold pump prices stable ahead of state elections. India's Russian Urals sourcing playbook gives non-Western options but Arabian Sea routing faces its own complications.",
    },
    {
        "id": "openai_commoditization",
        "topic": "What must OpenAI do in the next 12-18 months to avoid becoming a commodity infrastructure provider in a market it created?",
        "audience": "Sam Altman, post-restructuring board, with Microsoft as a shadow constraint on every major move",
        "context": "OpenAI pioneered the frontier model category but finds itself in a structural trap -- the faster AI capability diffuses, the more its core product becomes undifferentiated. Well-capitalized competitors are converging on model quality parity, inference pricing is in freefall, and open-source releases from Meta structurally cap what any closed provider can charge. OpenAI cost structure requires a revenue trajectory that the current model mix cannot credibly support: $40B raised at ~$300B valuation demands a path to $100B+ in annual revenue within 5 years. ChatGPT 500M weekly users represent brand dominance but not monetization dominance. The enterprise motion -- where revenue concentration actually sits -- is contested terrain where Google and Microsoft hold structural distribution advantages, and Microsoft is simultaneously OpenAI largest investor, primary cloud provider, and most dangerous competitor. OpenAI is making bets on reasoning models, agentic platforms, hardware, and consumer devices simultaneously -- but it is unclear whether this is a coherent platform strategy or capital being deployed to delay an inevitable reckoning with the commoditization question. Binding constraint: every strategic option that could work requires OpenAI to become something fundamentally different from what it is today.",
    },
    {
        "id": "mbb_palantir_disruption",
        "topic": "What must McKinsey, BCG, and Bain do in the next 12-18 months to defend their strategic relevance and client relationships as Palantir's embedded AI deployment model makes the traditional MBB engagement model -- senior partner judgment, delivered as a document, then abandoned -- look structurally obsolete?",
        "audience": "Managing partners, global practice leads, chief talent officers at McKinsey, BCG, and Bain",
        "context": "Palantir valued at ~$350B on ~$3B revenue because the market believes it is building a permanent monopoly on AI-native decision infrastructure. Its AIP platform operationalizes decisions, embeds into live workflows, and compounds in value the longer it stays. MBB model does the opposite: extracts high day rate for synthesized judgment, produces a deliverable, and exits. The structural threat is not losing RFPs -- it is that Palantir redefines what solving a problem means, from a strategy document to a running system. Palantir delivery: small teams of forward-deployed engineers, outcome-based contracts, no PowerPoint, IP stays and scales. MBB delivery: large pyramidal teams, time-and-materials, partner-led synthesis, zero residual IP. Talent pipeline under direct pressure -- Palantir hires same Rhodes Scholar profile, paying more, with narrative of building real things. MBB moats -- CEO access, institutional trust, proprietary frameworks, alumni network -- are real but not AI-native advantages. A CEO with Palantir AIP running across operations has a live decision cockpit; they do not need a McKinsey deck. Binding constraints: MBB cannot become a software company without destroying margin structure and talent model; cannot out-Palantir on technical depth; any move toward outcome-based pricing cannibalizes most profitable engagements first.",
    },
    {
        "id": "mbb_ai_structural",
        "topic": "What must MBB firms do to sustain relevance and commercial viability as AI fundamentally disrupts the strategy consulting industry?",
        "audience": "Senior partners, managing partners, global practice leads, chief talent officers at MBB firms",
        "context": "MBB firms charge premium rates for research, synthesis, benchmarking, financial modeling, and recommendation -- tasks AI now performs at near-zero marginal cost and increasing quality. Clients are building internal AI-literate strategy teams that can replicate work previously requiring external firms. The junior analyst and associate pyramid that underpins MBB economics is under structural pressure from both the demand side (clients need fewer bodies) and the supply side (top talent has more compelling options in AI companies, startups, and technology firms). MBB firms core assets -- CEO relationships, cross-industry pattern recognition, proprietary benchmarks, and change management capability -- are not equally threatened by AI, but firms have not disaggregated which are defensible and which are not. MBB responses to date have been largely internal -- AI tool rollouts, practice rebranding, selective hiring of technical profiles -- without a structural bet on what the business model looks like when the analyst pyramid is no longer the economic engine. The partnership structure is the deepest constraint on transformation: partners are owner-operators with carried interest tied to current-year revenue, consensus is required across a distributed power structure with no single decision maker, and the brand promise of our people are the product is difficult to sustain if the people are being augmented or replaced by tools. Time horizon: 12-18 months for structural decisions; 3-5 years for full model consequences.",
    },
    {
        "id": "reliance_downstream_ai",
        "topic": "What must Reliance's downstream business -- spanning refining, trading, and marketing -- do to adapt its operations, decision-making, and competitive positioning in response to AI?",
        "audience": "Refining leadership, trading desk heads, IT/OT integration teams, strategy function reporting to Executive Director",
        "context": "Reliance operates the world's largest single-location refinery complex at Jamnagar with combined capacity of 1.4 million bpd across DTA and SEZ units, a sophisticated crude trading book, and retail fuel and petrochemical marketing at scale. The downstream business has been optimized over decades around human expertise -- crude selection, yield optimization, crack spread management, and hedging decisions driven by experienced domain specialists with deep institutional knowledge and proprietary heuristics. AI is beginning to restructure each layer: crude procurement optimization, real-time refinery planning, predictive maintenance, trading signal generation, and demand forecasting are categories where AI-native tools generate measurable edge for early adopters. Competitors -- Saudi Aramco, Shell, bp -- are making material AI investments in downstream, with Aramco deploying AI across refining and trading as part of a broader digitization mandate. The risk is not disruption from an external AI competitor but internal obsolescence -- gradual erosion of margin and operational advantage as peers compound AI-driven efficiency gains while Reliance downstream runs on legacy decision infrastructure. The business sits at the intersection of OT systems (DCS, SCADA, historian data) and IT systems (ERP, CTRM, planning tools) -- an integration challenge that has historically slowed AI deployment in industrial settings. Proprietary data is abundant but siloed: crude assay libraries, yield histories, trading P&L, and customer demand patterns exist but are not connected into a unified decision layer. Domain experts who hold institutional knowledge are not AI-native, and AI-native talent has no domain depth. Binding constraints: OT safety and reliability requirements limit pace of AI deployment in live refinery environments; CTRM system architecture constrains trading AI integration; transformation must preserve operational continuity where unplanned downtime costs millions per hour.",
    },
    {
        "id": "reliance_hormuz_crisis",
        "topic": "What must Reliance do in the next 30 days to protect its refining operations, crude supply continuity, and margin position in response to the active closure of the Strait of Hormuz?",
        "audience": "Refining leadership, trading desk, CFO, and Chairman's office given scale of financial exposure",
        "context": "Reliance operates the world's largest single-location refinery complex at Jamnagar -- 1.4 million bpd across DTA and SEZ units -- making it among the most exposed private refining assets globally to a Hormuz closure. Unlike Indian PSU refiners, Reliance is a fully commercial operator with no government pricing mandate, no subsidized retail obligation, and full discretion over crude slate and margin optimization -- but also no access to strategic petroleum reserve drawdowns or sovereign diplomatic leverage. Reliance sources significant crude from Gulf producers transiting Hormuz, including Iraqi Basra Heavy, Saudi Arab Heavy, and Kuwaiti Export Crude -- all effectively suspended under force majeure since March 2. Brent peaked at $126/bbl; crack spread environment simultaneously attractive and operationally constrained by crude availability. Jamnagar configured for heavy sour Gulf crude -- Nelson Complexity Index and secondary conversion units (cokers, hydrocrackers) optimized for this slate; shifting to light sweet alternatives sacrifices yield economics. Reliance trading arm has historically run sophisticated hedging book and opportunistic crude procurement -- this is a moment where trading capability is either significant advantage or liability depending on positioning entering the crisis. Existing relationships with non-Gulf producers -- US WTI, West African NOCs, Russian Urals -- give more flexible sourcing than PSU peers, but volume replacement at 1.4 million bpd is fundamentally different from marginal optimization. Iran channel completely closed; Chinese preferential transit creates two-tier market Reliance cannot access diplomatically. Live geopolitical deadline: April 6 Trump ultimatum on Iranian energy infrastructure -- outcome could be rapid de-escalation or significant further escalation. Binding constraints: Jamnagar crude flexibility real but not unlimited; cannot wait for diplomatic resolution; any public signal of supply stress affects commercial negotiations and equity story.",
    },
]

# Run order: Hormuz PSU, OpenAI, SaaS, MBB/AI, MBB/Palantir, Reliance AI, Reliance Hormuz
CASES = [ALL_CASES[1], ALL_CASES[2], ALL_CASES[0], ALL_CASES[4], ALL_CASES[3], ALL_CASES[5], ALL_CASES[6]]


def run_case(case):
    import importlib
    import pipeline as p
    importlib.reload(p)

    run_dir = ROOT / "outputs" / "runs" / case["id"]
    p._run_dir = run_dir
    p._llm_call_count = 0
    p._total_input_tokens = 0
    p._total_output_tokens = 0

    state = p.State(run_dir)
    state.set("topic", case["topic"])
    state.set("audience", case["audience"])

    print(f"\n{'='*70}")
    print(f"  RUNNING: {case['id']}")
    print(f"  {case['topic'][:80]}...")
    print(f"{'='*70}\n")

    t0 = time.time()
    ps_text = case["topic"]
    context = case.get("context", "")

    # PS Worksheet (full McKinsey SP66)
    print(f"  Building Problem Statement Worksheet...")
    smart = p.llm_json(
        f"""You are a McKinsey engagement manager completing the Problem Statement Worksheet.
Source: McKinsey Staff Paper No. 66 (July 2007)
Today is {p.TODAY_STR}.

Complete ALL 6 components:

1. BASIC QUESTION TO BE RESOLVED
   Keep it BROAD, ACTION-ORIENTED, and SHORT (1-2 sentences max).
   Name who, what domain, and the timeframe. Do NOT pack metrics into the question.
   GOOD: "What steps must Workday take in the next 1-3 years to defend against AI disruption?"
   BAD: "What specific combination of moves must the company execute to defend 90% of ARR..." (too specific)

2. CONTEXT -- situation and complication facing the client
3. CRITERIA FOR SUCCESS -- quantitative and qualitative measures
4. SCOPE -- what is in and out of scope
5. CONSTRAINTS -- limits on the solution space
6. STAKEHOLDERS -- decision makers, supporters, blockers

Also infer:
- DECISION SENSITIVITY BREAK POINT
- KEY ASSUMPTIONS (2-3)

Return JSON:
{{"basic_question": "...", "context": "...", "criteria_for_success": ["..."], "scope": {{"in_scope": ["..."], "out_of_scope": ["..."]}}, "constraints": ["..."], "stakeholders": {{"decision_makers": ["..."], "supporters": ["..."], "potential_blockers": ["..."]}}, "decision_sensitivity": "...", "key_assumptions": ["..."]}}""",
        f"RAW PROBLEM STATEMENT:\n{ps_text}\n\nCONTEXT:\n{context}\n\nComplete the McKinsey Problem Statement Worksheet."
    )

    smart_ps = smart.get("basic_question", ps_text)
    sens = smart.get("decision_sensitivity", "")
    ctx = smart.get("context", context)
    scope = smart.get("scope", {})
    constraints = smart.get("constraints", [])
    stakeholders = smart.get("stakeholders", {})

    mece_dir = state.dir / "mece"
    mece_dir.mkdir(exist_ok=True)
    json.dump(smart, open(mece_dir / "0_problem_worksheet.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"  PS: {smart_ps[:100]}...")

    # Broad research scan -- read landscape BEFORE MECE
    print(f"  Broad research scan...")
    landscape = p._broad_research_scan(smart_ps, ctx, state)
    current_events = landscape.get("events", [])
    landscape_summary = landscape.get("summary", "")
    print(f"  Landscape: {len(landscape.get('articles', []))} articles, {len(current_events)} events")

    # MECE -- informed by landscape
    landscape_block = ""
    if landscape_summary:
        landscape_block = f"\nLANDSCAPE SCAN (from reading articles about this topic):\n{landscape_summary[:4000]}\n\nYour MECE buckets MUST reflect what the articles cover.\n"
    elif current_events:
        landscape_block = "\nCURRENT EVENTS:\n" + "\n".join(
            f"- [{e.get('date','')}] {e.get('title','')}: {e.get('snippet','')}"
            for e in current_events[:10]
        ) + "\n"

    issue_vault = p.load_vault("issue_tree_vault")
    vault_text = ""
    if issue_vault:
        vault_text = "\n\nDECOMPOSITION METHODS (choose the best fit):\n"
        for m in issue_vault.get("decomposition_methods", []):
            vault_text += f"\n{m['method']}: {m['when']}\n"
            for ex in m.get("examples", [])[:1]:
                branches = ex.get("branches", [])
                vault_text += f"  Example: {' / '.join(branches)}\n"
        vault_text += "\n\nEXAMPLES:\n"
        for ex in issue_vault.get("full_examples", [])[:6]:
            vault_text += f"\nProblem: \"{ex['problem']}\"\n"
            for i, b in enumerate(ex["buckets"], 1):
                vault_text += f"  {i}. \"{b}\"\n"

    print(f"  Generating issue tree buckets...")
    buckets = p.llm_json(
        """You are building an ISSUE TREE.

STEP 1 -- Choose decomposition method:
- ALGEBRAIC: number to explain? decompose the equation
- PROCESS: sequence of steps? decompose the flow
- CAUSAL: different actors/forces? partition by actor
- SITUATION ASSESSMENT: need to understand before deciding? cover independent dimensions

STEP 2 -- Write 4-6 MECE buckets:
- OPEN QUESTION, max 8 words. Plain English.
- Ask about FACTS. No "should", "must", "how to".
- Must be about THIS specific problem.

STEP 3 -- AUXILIARY FORCES:
Read the LANDSCAPE SCAN. What external forces, competitor actions, or market dynamics could MATERIALLY CHANGE the answer -- even if the problem statement does not mention them? Add 1-2 buckets for these.

STEP 4 -- MECE check:
- Overlap: does bucket 1 info belong in bucket 2? Fix.
- Gap: important question outside all buckets? Add.

Return JSON: {"method": "...", "method_rationale": "...", "buckets": [{"id": 1, "title": "...", "rationale": "..."}]}""",
        "PROBLEM: {ps}\nCONTEXT: {ctx}\n{landscape}{vault}".format(ps=smart_ps, ctx=ctx, landscape=landscape_block, vault=vault_text)
    )

    bucket_list = buckets.get("buckets", [])
    print(f"  Method: {buckets.get('method', '?')}")
    for b in bucket_list:
        print(f"    {b['id']}. {b['title']}")

    # Auxiliary forces check — separate call
    if landscape_summary:
        print(f"  Checking auxiliary forces...")
        existing = "\n".join(f"- {b['title']}" for b in bucket_list)
        try:
            aux = p.llm_json(
                """Review this issue tree. The landscape scan reveals external forces NOT in the existing buckets. Identify 1-3 EXTERNAL forces that could materially impact the decision. Write each as a bucket title (max 8 words, open question). If all forces are covered, return empty. Return JSON: {"auxiliary_buckets": [{"id": 7, "title": "...", "rationale": "...", "landscape_evidence": "what triggered this"}]}""",
                "PROBLEM: {ps}\n\nEXISTING BUCKETS:\n{existing}\n\nLANDSCAPE SCAN:\n{landscape}".format(
                    ps=smart_ps, existing=existing, landscape=landscape_summary[:5000]
                ),
                model=p.SONNET
            )
            for ab in aux.get("auxiliary_buckets", []):
                ab["id"] = max(b["id"] for b in bucket_list) + 1
                bucket_list.append(ab)
                print(f"    + {ab['id']}. {ab['title']} (auxiliary)")
        except Exception:
            pass

    # Sub-questions per bucket (parallel)
    print(f"  Sub-questions (parallel)...")
    def _gen_qs(b):
        bid = b["id"]
        title = b["title"]
        qs = p.llm_json(
            'Generate 5-8 questions that answer: "' + title + '". Each asks about a FACT or NUMBER. No "should/must/how to". Return JSON: {"questions": [{"id": "' + str(bid) + '.1", "question": "..."}]}',
            "PROBLEM: " + smart_ps,
            model=p.HAIKU, max_tokens=2048
        )
        return bid, title, qs.get("questions", [])

    results_map = {}
    with ThreadPoolExecutor(max_workers=min(len(bucket_list), 6)) as executor:
        futures = {executor.submit(_gen_qs, b): b for b in bucket_list}
        for future in as_completed(futures):
            b = futures[future]
            try:
                bid, title, questions = future.result()
                results_map[bid] = {"section_id": bid, "title": title, "rationale": b.get("rationale", ""), "questions": questions}
                print(f"    Bucket {bid}: {len(questions)}q")
            except Exception as e:
                print(f"    Bucket {b['id']} FAILED: {e}")

    sections = [results_map[bid] for bid in sorted(results_map.keys())]
    result = {"smart_statement": smart_ps, "decision_sensitivity": sens, "sections": sections}
    if context:
        result["context"] = context

    json.dump(result, open(mece_dir / "decomposition.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    state.set("mece_path", str(mece_dir / "decomposition.json"))
    mece = result
    n_b = len(sections)
    n_q = sum(len(s.get("questions", [])) for s in sections)
    print(f"  MECE: {n_b} buckets, {n_q} questions")
    state.complete(0)

    # Issue Tree
    print(f"  Issue tree...")
    _, tree_path = p.step1(state, mece)
    state.complete(1)

    # Tiering
    print(f"  Tiering...")
    p.tier_questions(state, mece)
    json.dump(mece, open(state.get("mece_path"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Research brief
    print(f"  Research brief...")
    brief, total_must, total_nice = p.step2_research_brief(state, mece)
    print(f"  Brief: {total_must} must-have, {total_nice} nice-to-have")

    # Research + Working Doc (parallel pipeline)
    print(f"  Research + Working Doc (parallel)...")
    sections = mece.get("sections", [])
    topic = state.get("topic", "")
    audience = state.get("audience", "")
    research_dir = state.dir / "research"
    research_dir.mkdir(exist_ok=True)
    wd_dir = state.dir / "working_doc"
    wd_dir.mkdir(exist_ok=True)

    ce_path = state.get("current_events_path")
    ce_data = None
    if ce_path and Path(ce_path).exists():
        ce_file = json.load(open(ce_path, encoding="utf-8"))
        ce_data = ce_file.get("ranked", ce_file) if isinstance(ce_file, dict) else ce_file

    # Phase 1: ALL web searches — sequential, throttled (no rate limiting)
    print(f"    Phase 1: Web search (sequential)...")
    search_data = p._web_search_all_buckets(topic, sections, current_events=ce_data)

    # Phase 2: ALL synthesis + working doc — parallel (LLM calls, no rate limit)
    print(f"    Phase 2: Synthesis + Working Doc (parallel)...")
    def _synth_and_wd(s):
        sid, r_text = p._synthesize_one_bucket(topic, s, search_data, None, research_dir, current_events=ce_data)
        _, title, wd_text = p._working_doc_one_bucket(topic, audience, s, {sid: r_text}, "", state.dir, "")
        return sid, r_text, title, wd_text

    research_by_bucket = {}
    wd_results = {}
    with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
        futures = {executor.submit(_synth_and_wd, s): s for s in sections}
        for future in as_completed(futures):
            s = futures[future]
            try:
                sid, r_text, title, wd_text = future.result()
                research_by_bucket[sid] = r_text
                wd_results[sid] = (title, wd_text)
                print(f"    Bucket {sid} done")
            except Exception as e:
                print(f"    Bucket {s['section_id']} FAILED: {e}")

    compiled = "\n\n---\n\n".join(research_by_bucket[sid] for sid in sorted(research_by_bucket.keys()))
    (research_dir / "compiled.md").write_text(compiled, encoding="utf-8")
    state.set("research_path", str(research_dir / "compiled.md"))
    state.complete(2)

    wd_parts = [f"## Bucket {sid}: {wd_results[sid][0]}\n\n{wd_results[sid][1]}" for sid in sorted(wd_results.keys())]
    working_doc = f"# Working Document\n\n**Topic:** {topic}\n**Date:** {p.TODAY_STR}\n\n" + "\n\n---\n\n".join(wd_parts)
    (wd_dir / "working_document.md").write_text(working_doc, encoding="utf-8")
    state.set("wd_path", str(wd_dir / "working_document.md"))
    state.complete(3)
    print(f"  Working doc: {len(working_doc):,} chars")

    # Debrief
    print(f"  Debrief...")
    debrief_path = research_dir / "debrief.md"
    debrief_text = p.llm(
        f"You are a research analyst debriefing a senior partner. Today is {p.TODAY_STR}. Present findings in 2-5 pages. Every fact must have time period, source, and comparison baseline. Write like you are talking, not writing a report.",
        f"PROBLEM: {smart_ps}\n\nWORKING DOCUMENT:\n{working_doc[:50000]}\n\nDebrief."
    )
    debrief_path.write_text(f"# Research Debrief\n\n{debrief_text}", encoding="utf-8")

    # Synthesis
    print(f"  Synthesis...")
    summary, synthesis = p.step4_synthesis(state, mece, working_doc)
    state.complete(4)
    n_f = len([f for b in synthesis.get("findings", {}).get("buckets", []) for f in b.get("findings", [])])
    n_p = len(synthesis.get("patterns", {}).get("patterns", []))
    n_i = len(synthesis.get("inferences", {}).get("inferences", []))
    print(f"  Synthesis: {n_f} findings, {n_p} patterns, {n_i} inferences")

    # Hypotheses
    print(f"  Hypotheses...")
    summary, hyp_tree = p.step5_hypotheses(state, mece, working_doc, synthesis)
    state.complete(5)
    all_hyps = hyp_tree.get("hypotheses", [])
    confirmed = len([h for h in all_hyps if h.get("status") == "confirmed"])
    killed = len([h for h in all_hyps if h.get("status") == "killed"])
    print(f"  Hypotheses: {len(all_hyps)} total, {confirmed} confirmed, {killed} killed")

    # Final Document + MBB Critique
    print(f"  Final document...")
    doc_path = p.step6_final_doc(state, mece, hyp_tree, working_doc, synthesis)
    state.complete(6)

    # Appendix
    print(f"  Appendix...")
    app_path = p.step7_appendix(state, mece, hyp_tree, working_doc)
    state.complete(7)

    # Combined output
    print(f"  Building combined output...")
    combined = p._build_combined_output(run_dir)

    duration = time.time() - t0
    est_cost = (p._total_input_tokens * 3 + p._total_output_tokens * 15) / 1_000_000
    print(f"\n  DONE: {case['id']} | {duration:.0f}s | {p._llm_call_count} calls | ~${est_cost:.2f}")

    return {
        "id": case["id"],
        "duration_s": round(duration, 1),
        "llm_calls": p._llm_call_count,
        "est_cost": round(est_cost, 2),
        "smart_ps": smart_ps[:200],
        "mece_buckets": n_b,
        "mece_questions": n_q,
        "findings": n_f,
        "patterns": n_p,
        "inferences": n_i,
        "hypotheses": len(all_hyps),
        "confirmed": confirmed,
        "killed": killed,
        "combined": combined,
        "status": "success",
    }


def main():
    results = []
    t_start = time.time()

    for case in CASES:
        try:
            r = run_case(case)
            results.append(r)
        except Exception as e:
            print(f"\n  FAILED: {case['id']} -- {e}")
            traceback.print_exc()
            results.append({"id": case["id"], "status": "failed", "error": str(e)[:500]})

        json.dump(results, open(ROOT / "outputs" / "runs" / "4ps_results.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    total = time.time() - t_start
    passed = len([r for r in results if r.get("status") == "success"])
    total_cost = sum(r.get("est_cost", 0) for r in results)

    print(f"\n{'='*70}")
    print(f"  ALL DONE: {passed}/{len(results)} passed | {total:.0f}s ({total/60:.1f} min) | ~${total_cost:.2f}")
    print(f"{'='*70}")

    for r in results:
        status = "OK" if r.get("status") == "success" else "FAIL"
        print(f"  [{status}] {r['id']}: {r.get('duration_s', '?')}s | {r.get('llm_calls', '?')} calls | ~${r.get('est_cost', '?')}")
        if r.get("combined"):
            print(f"         {r['combined']}")


if __name__ == "__main__":
    main()

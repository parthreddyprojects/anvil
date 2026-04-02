#!/usr/bin/env python3
"""Run 3 problem statements end-to-end in autopilot mode."""
import json, os, sys, time, traceback
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

CASES = [
    {
        "id": "workday_ai_disruption",
        "topic": "What steps must Workday take in the next 1-3 years to defend its position in HCM and financial management against AI-native competitors and incumbents embedding AI at marginal cost?",
        "audience": "Carl Eschenbach (CEO), Zane Rowe (CFO), Workday board of directors",
        "context": "Workday is a $7.7B ARR enterprise SaaS company (FY25) with ~10,500 customers, dominant in enterprise HCM and growing in financial management. AI-native startups (Rippling, Deel, Lattice) are attacking HCM workflows from below with simpler, cheaper, AI-first products. ServiceNow is expanding aggressively into HR service delivery. SAP SuccessFactors and Oracle HCM are embedding AI copilots into existing seats at no incremental cost. Microsoft Copilot integrates with everything. Workday's per-seat pricing ($100-200/employee/year) is under pressure as AI reduces the HR headcount that justifies seat counts. Workday has deep proprietary data (payroll, performance, workforce planning across thousands of enterprises) and high switching costs (12-18 month implementations), but AI-assisted migration tools are compressing switching friction. NRR has been declining from 120%+ to ~105%. Workday AI platform launched but adoption data is not public. Stock has underperformed S&P 500 by 30%+ over 2024-2025.",
    },
    {
        "id": "psu_hormuz_crisis",
        "topic": "What immediate operational and strategic actions should a state-owned downstream energy company (refining + fuel marketing) take in the next 30 days to maintain supply security, protect margins, and manage stakeholder confidence in the event of a full or partial closure of the Strait of Hormuz?",
        "audience": "CMD, Director Refining, Director Finance; Ministry of Petroleum has oversight and veto on pricing",
        "context": "Roughly 20% of global crude oil and LNG transits through Hormuz. The company sources 35-60% of crude from Gulf producers on long-term OSPs without automatic rerouting clauses. Alternative crude sources require 15-45 days for cargo repositioning. The refinery is configured for medium-sour Gulf crude. Government is under political pressure to hold pump prices stable. Strategic petroleum reserves cover only 15-20 days of consumption. Ports and logistics add execution complexity including single-port dependency, demurrage risk, and LC processing delays.",
    },
    {
        "id": "openai_commoditization",
        "topic": "What must OpenAI do in the next 12-18 months to avoid margin collapse and strategic commoditization as frontier model capability gaps close, inference pricing races to zero, and well-capitalized competitors (Google, Anthropic, Meta, xAI) compete on both quality and cost?",
        "audience": "Sam Altman (CEO), Greg Brockman (returning), post-restructuring board, with Microsoft as a shadow constraint on every major strategic move",
        "context": "Frontier model differentiation is compressing. Inference is on a deflationary curve with API pricing down roughly 90% in two years. OpenAI cost structure is extreme: $40B raised at ~$300B valuation. ChatGPT has ~500M weekly users but consumer monetization per user is low. Microsoft is simultaneously largest investor, primary cloud provider, and most dangerous enterprise competitor. The o-series reasoning models and agent platform represent current differentiation bet. Binding constraints: cannot reduce model quality without brand damage; cannot out-distribute Google or Microsoft; cannot out-open-source Meta; valuation requires a credible path to $100B+ revenue within 5 years.",
    },
]


def run_case(case):
    import importlib
    import pipeline as p
    importlib.reload(p)

    run_dir = ROOT / "outputs" / "runs" / case["id"]
    p._run_dir = run_dir
    p._llm_call_count = 0

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

    # PS Worksheet — full McKinsey Staff Paper No. 66 framework
    print(f"  Building Problem Statement Worksheet (McKinsey SP66)...")
    smart = p.llm_json(
        f"""You are a McKinsey engagement manager completing the Problem Statement Worksheet.
Source: McKinsey Staff Paper No. 66 (July 2007) -- "The McKinsey Approach to Problem Solving"
Today is {p.TODAY_STR}.

The human has given you a raw problem statement and optional context. Your job is to complete ALL 6 components of the McKinsey Problem Statement Worksheet.

MCKINSEY PROBLEM STATEMENT WORKSHEET (6 COMPONENTS)

1. BASIC QUESTION TO BE RESOLVED
   Keep it BROAD, ACTION-ORIENTED, and SHORT (1-2 sentences max).
   - Name who, what domain, and the timeframe. That's it.
   - Do NOT pack metrics or thresholds into the question -- those go in section 3.
   GOOD: "What steps must this company take in the next 1-3 years to defend its position?"
   BAD: "What specific combination of moves must the company execute to defend 90% of ARR..." (too specific)

2. CONTEXT
   The situation and complication facing the client:
   - Industry trends and dynamics
   - Client's relative position within the industry
   - Capability gaps
   - Financial flexibility
   - Key internal and external complications

3. CRITERIA FOR SUCCESS
   How the client and team define success and failure:
   - Quantitative measures (revenue, margin, market share targets)
   - Qualitative measures (capability building, mindset shifts)
   - Impact timing (when must results be visible?)
   - Visibility of improvement (who needs to see it?)

4. SCOPE OF SOLUTION SPACE
   What will and will NOT be included in the analysis:
   - Markets, segments, geographies in scope
   - Business units or functions in scope
   - What is explicitly OUT of scope

5. CONSTRAINTS WITHIN SOLUTION SPACE
   Limits on the set of solutions that can be considered:
   - Must it be organic vs. inorganic growth?
   - Budget or capital constraints?
   - Regulatory or political constraints?
   - Timeline constraints on implementation?
   - Sacred cows or non-negotiables?

6. KEY STAKEHOLDERS
   Who makes the decisions and who can support or derail:
   - Decision maker(s)
   - Supporters / champions
   - Potential blockers
   - Key influencers

Also infer:
- DECISION SENSITIVITY BREAK POINT: the specific number or condition at which the opposite recommendation becomes correct
- KEY ASSUMPTIONS: 2-3 assumptions baked into the worksheet that should be validated

TIPS (from McKinsey Staff Paper No. 66):
- Think "opportunity" not just "problem" -- expansive, not reductive mindset
- The first cut will be imperfect -- get to paper quickly and iterate
- There is interplay between all elements -- refining one forces you to refine others

Return JSON:
{{"basic_question": "SMART question...",
"context": "situation and complication...",
"criteria_for_success": ["quantitative measure 1", "qualitative measure 2", "..."],
"scope": {{"in_scope": ["..."], "out_of_scope": ["..."]}},
"constraints": ["constraint 1", "constraint 2", "..."],
"stakeholders": {{"decision_makers": ["..."], "supporters": ["..."], "potential_blockers": ["..."]}},
"decision_sensitivity": "The recommendation reverses if...",
"key_assumptions": ["...", "..."]}}""",
        f"RAW PROBLEM STATEMENT:\n{ps_text}\n\nCONTEXT:\n{context}\n\nComplete the McKinsey Problem Statement Worksheet."
    )

    smart_ps = smart.get("basic_question", ps_text)
    sens = smart.get("decision_sensitivity", "")
    ctx = smart.get("context", context)
    criteria = smart.get("criteria_for_success", [])
    scope = smart.get("scope", {})
    constraints = smart.get("constraints", [])
    stakeholders = smart.get("stakeholders", {})

    mece_dir = state.dir / "mece"
    mece_dir.mkdir(exist_ok=True)
    json.dump(smart, open(mece_dir / "0_problem_worksheet.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"  SMART: {smart_ps[:100]}...")

    # Web scan
    print(f"  Scanning web...")
    current_events = p._scan_current_events(smart_ps, ctx, state)
    print(f"  Found {len(current_events)} relevant results")

    # MECE
    # MECE — two-step: bucket titles first, then sub-questions per bucket (parallel)
    events_block = ""
    if current_events:
        events_block = "\nCURRENT EVENTS:\n" + "\n".join(
            f"- [{e.get('date','')}] {e.get('title','')}: {e.get('snippet','')}"
            for e in current_events[:10]
        ) + "\n"

    # Load issue tree vault for examples
    issue_vault = p.load_vault("issue_tree_vault")
    vault_text = ""
    if issue_vault:
        vault_text = "\n\nDECOMPOSITION METHODS (choose the best fit):\n"
        for m in issue_vault.get("decomposition_methods", []):
            vault_text += f"\n{m['method']}: {m['when']}\n"
            for ex in m.get("examples", [])[:1]:
                branches = ex.get("branches", [])
                vault_text += f"  Example: {' / '.join(branches)}\n"
        vault_text += "\n\nEXAMPLES OF GOOD ISSUE TREES:\n"
        for ex in issue_vault.get("full_examples", [])[:6]:
            vault_text += f"\nProblem: \"{ex['problem']}\"\n"
            for i, b in enumerate(ex["buckets"], 1):
                vault_text += f"  {i}. \"{b}\"\n"
            vault_text += f"  Why MECE: {ex.get('why_mece', '')}\n"

    print(f"  Generating issue tree buckets...")
    buckets = p.llm_json(
        """You are building an ISSUE TREE.

STEP 1 -- Choose your decomposition method:
- ALGEBRAIC: if there is a number to explain, decompose the equation
- PROCESS: if there is a sequence of steps, decompose the flow
- CAUSAL: if different actors or forces drive the problem
- SEGMENTATION: if the problem differs across natural segments
- SITUATION ASSESSMENT: if you need to understand a situation before deciding

STEP 2 -- Write 4-6 MECE buckets:
- Each is an OPEN QUESTION, max 8 words. Plain English.
- Questions ask about FACTS. No "should", "must", "how to".
- Must be about THIS specific problem.

STEP 3 -- MECE check:
- Overlap test: does answering bucket 1 give info that belongs in bucket 2?
- Gap test: is there an important question outside all buckets?

State which method you chose and why.

Return JSON: {"method": "...", "method_rationale": "...", "buckets": [{"id": 1, "title": "...", "rationale": "..."}]}""",
        "PROBLEM: {ps}\nCONTEXT: {ctx}\n{events}{vault}".format(ps=smart_ps, ctx=ctx, events=events_block, vault=vault_text)
    )

    bucket_list = buckets.get("buckets", [])
    for b in bucket_list:
        print(f"    {b['id']}. {b['title']}")

    print(f"  Generating sub-questions (parallel)...")
    def _gen_qs(b):
        bid = b["id"]
        title = b["title"]
        qs = p.llm_json(
            'You are a research analyst. Generate 5-8 questions that answer: "' + title + '". Each asks about a FACT or NUMBER. No "should/must/how to". Return JSON: {"questions": [{"id": "' + str(bid) + '.1", "question": "..."}]}',
            "PROBLEM: " + smart_ps,
            model=p.HAIKU, max_tokens=2048
        )
        return bid, title, qs.get("questions", [])

    sections = []
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

    n_b = len(mece.get("sections", []))
    n_q = sum(len(s.get("questions", [])) for s in mece.get("sections", []))
    print(f"  MECE: {n_b} buckets, {n_q} questions")
    state.complete(0)

    # Issue Tree
    print(f"  Issue tree...")
    _, tree_path = p.step1(state, mece)
    state.complete(1)

    # Tiering
    print(f"  80/20 tiering...")
    p.tier_questions(state, mece)
    json.dump(mece, open(state.get("mece_path"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Research brief
    print(f"  Research brief...")
    brief, total_must, total_nice = p.step2_research_brief(state, mece)
    print(f"  Brief: {total_must} must-have, {total_nice} nice-to-have")

    # Research + Working Doc (parallel)
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

    def _pipeline_one(s):
        sid, r_text = p._research_one_bucket(topic, s, brief, None, research_dir, current_events=ce_data)
        _, title, wd_text = p._working_doc_one_bucket(topic, audience, s, {sid: r_text}, "", state.dir, "")
        return sid, r_text, title, wd_text

    research_by_bucket = {}
    wd_results = {}
    with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
        futures = {executor.submit(_pipeline_one, s): s for s in sections}
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
        f"You are a research analyst debriefing a senior partner. Today is {p.TODAY_STR}. Present findings in 2-5 pages. Every fact must have time period, source, and comparison baseline.",
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

    # Final Document
    print(f"  Final document...")
    doc_path = p.step6_final_doc(state, mece, hyp_tree, working_doc, synthesis)
    state.complete(6)

    # Appendix
    print(f"  Appendix...")
    app_path = p.step7_appendix(state, mece, hyp_tree, working_doc)
    state.complete(7)

    duration = time.time() - t0
    print(f"\n  DONE: {case['id']} | {duration:.0f}s | {p._llm_call_count} LLM calls")

    return {
        "id": case["id"],
        "duration_s": round(duration, 1),
        "llm_calls": p._llm_call_count,
        "smart_ps": smart_ps[:200],
        "mece_buckets": n_b,
        "mece_questions": n_q,
        "findings": n_f,
        "patterns": n_p,
        "inferences": n_i,
        "hypotheses": len(all_hyps),
        "hypotheses_confirmed": confirmed,
        "hypotheses_killed": killed,
        "final_doc": doc_path,
        "appendix": app_path,
        "run_dir": str(run_dir),
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

        # Save progress
        json.dump(results, open(ROOT / "outputs" / "runs" / "3ps_results.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    total = time.time() - t_start
    passed = len([r for r in results if r.get("status") == "success"])

    print(f"\n{'='*70}")
    print(f"  ALL DONE: {passed}/{len(results)} passed | {total:.0f}s ({total/60:.1f} min)")
    print(f"{'='*70}")

    for r in results:
        status = "OK" if r.get("status") == "success" else "FAIL"
        print(f"  [{status}] {r['id']}: {r.get('duration_s', '?')}s, {r.get('llm_calls', '?')} calls")
        if r.get("final_doc"):
            print(f"         {r['final_doc']}")

    print(f"\n  Results: {ROOT / 'outputs' / 'runs' / '3ps_results.json'}")
    print(f"  Run folders:")
    for case in CASES:
        print(f"    {ROOT / 'outputs' / 'runs' / case['id']}")


if __name__ == "__main__":
    main()

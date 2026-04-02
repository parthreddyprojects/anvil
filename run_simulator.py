#!/usr/bin/env python3
"""
Pipeline Simulator — Functional + Quality Testing
===================================================
Runs multiple problem statements through the pipeline in autopilot mode.
Outputs a single HTML report with all results for review.

Usage:
    python run_simulator.py                    # Run all test cases
    python run_simulator.py --cases 1,3,5      # Run specific cases
    python run_simulator.py --list              # List test cases without running
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUTS = ROOT / "outputs"
SIM_DIR = OUTPUTS / "simulator"
TODAY = date.today()
TODAY_STR = TODAY.strftime("%B %d, %Y")

# ---------------------------------------------------------------------------
# Test Cases — diverse domain × question type × complexity
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "id": 1,
        "domain": "Tech / SaaS",
        "type": "Growth Strategy",
        "complexity": "Medium",
        "topic": "Should a mid-market B2B SaaS company with $50M ARR and 110% NDR expand into the enterprise segment (>1000 employees) given current product-market fit in SMB, or double down on SMB density?",
        "audience": "CEO, CRO, and board of directors of the SaaS company",
    },
    {
        "id": 2,
        "domain": "Energy / Oil & Gas",
        "type": "Capital Allocation",
        "complexity": "Complex",
        "topic": "How should a national oil company with 2 million bpd refining capacity allocate its next $10 billion in capital between refinery modernization, petrochemical integration, renewable energy, and retail network expansion over a 5-year horizon?",
        "audience": "Board investment committee and CEO of the national oil company",
    },
    {
        "id": 3,
        "domain": "Financial Services",
        "type": "Competitive Response",
        "complexity": "Medium",
        "topic": "How should a traditional retail bank with 15 million customers and $200B in deposits respond to neobank competitors that have captured 8% of new account openings in the last 18 months?",
        "audience": "CEO, CDO, and head of retail banking",
    },
    {
        "id": 4,
        "domain": "Healthcare / Pharma",
        "type": "M&A",
        "complexity": "Complex",
        "topic": "Should a top-10 pharmaceutical company with a patent cliff on 3 blockbuster drugs (combined $12B revenue expiring 2027-2029) acquire a mid-cap biotech with a promising GLP-1 pipeline, or pursue organic R&D and licensing deals?",
        "audience": "CEO, CFO, head of strategy, and board M&A committee",
    },
    {
        "id": 5,
        "domain": "Consumer / Retail",
        "type": "Turnaround",
        "complexity": "Simple",
        "topic": "A direct-to-consumer fashion brand has seen gross margins decline from 65% to 48% over 3 years while CAC has tripled. What is driving the margin erosion and what are the realistic options to reverse it within 18 months?",
        "audience": "Founder-CEO and the lead investor on the board",
    },
    {
        "id": 6,
        "domain": "Manufacturing",
        "type": "Regulatory Response",
        "complexity": "Medium",
        "topic": "How should a European automotive parts manufacturer with 12 factories across 6 countries adapt its operations and supply chain to the EU Carbon Border Adjustment Mechanism taking full effect in 2026?",
        "audience": "COO, head of supply chain, and head of sustainability",
    },
    {
        "id": 7,
        "domain": "Technology",
        "type": "Market Entry",
        "complexity": "Simple",
        "topic": "Should an Indian IT services company with $5B revenue and 200,000 employees launch a proprietary AI platform product, or remain a services-first company that integrates third-party AI tools for clients?",
        "audience": "CEO and executive committee",
    },
    {
        "id": 8,
        "domain": "Real Estate",
        "type": "Portfolio Strategy",
        "complexity": "Complex",
        "topic": "A commercial real estate fund with $8B AUM concentrated in Class A office space across 5 US metro areas is facing 22% vacancy rates post-COVID. Should it convert assets to mixed-use, sell and reinvest in logistics/data centers, or hold and wait for office demand recovery?",
        "audience": "Fund GP, investment committee, and LP advisory board",
    },
]


# ---------------------------------------------------------------------------
# Run one test case
# ---------------------------------------------------------------------------

def run_one(case, sim_run_dir):
    """Run a single test case through the pipeline. Returns result dict."""
    case_id = case["id"]
    slug = f"sim_{case_id}_{case['domain'][:20].lower().replace(' ', '_').replace('/', '_')}"
    run_dir = sim_run_dir / slug

    result = {
        "id": case_id,
        "domain": case["domain"],
        "type": case["type"],
        "complexity": case["complexity"],
        "topic": case["topic"][:100],
        "status": "pending",
        "start_time": None,
        "end_time": None,
        "duration_s": None,
        "error": None,
        "outputs": {},
    }

    print(f"\n{'='*60}")
    print(f"  TEST CASE {case_id}: {case['domain']} / {case['type']}")
    print(f"  {case['topic'][:80]}...")
    print(f"{'='*60}\n")

    t0 = time.time()
    result["start_time"] = datetime.now().isoformat()

    try:
        # Import and run pipeline
        import importlib
        import pipeline as p
        importlib.reload(p)  # Reload to get fresh state

        # Set up args
        p._run_dir = run_dir
        p._llm_call_count = 0

        state = p.State(run_dir)
        state.set("topic", case["topic"])
        state.set("audience", case["audience"])

        # Run step by step with error tracking
        mece = None
        working_doc = ""
        synthesis = None
        hyp_tree = {}

        # Step 0: Problem Statement
        print(f"  [Step 0] Problem Statement...")
        summary, mece, _ = p.step0(state, autopilot=True)
        state.complete(0)
        result["outputs"]["mece_buckets"] = len(mece.get("sections", []))
        result["outputs"]["mece_questions"] = sum(len(s.get("questions", [])) for s in mece.get("sections", []))

        # Step 1: Issue Tree
        print(f"  [Step 1] Issue Tree...")
        _, tree_path = p.step1(state, mece)
        state.complete(1)
        result["outputs"]["tree_html"] = os.path.exists(tree_path)

        # Tiering
        print(f"  [Tiering]...")
        p.tier_questions(state, mece)
        json.dump(mece, open(state.get("mece_path"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

        # Step 2: Research brief
        print(f"  [Step 2] Research Brief...")
        brief, total_must, total_nice = p.step2_research_brief(state, mece)
        result["outputs"]["research_must_have"] = total_must
        result["outputs"]["research_nice_have"] = total_nice

        # Steps 2+3: Research + Working Doc (parallel)
        print(f"  [Steps 2+3] Research + Working Doc...")
        sections = mece.get("sections", [])
        topic = state.get("topic", "")
        audience = state.get("audience", "")
        research_dir = state.dir / "research"
        research_dir.mkdir(exist_ok=True)
        wd_dir = state.dir / "working_doc"
        wd_dir.mkdir(exist_ok=True)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _pipeline_one(s):
            sid, r_text = p._research_one_bucket(topic, s, brief, None, research_dir)
            _, title, wd_text = p._working_doc_one_bucket(topic, audience, s, {sid: r_text}, "", state.dir, "")
            return sid, r_text, title, wd_text

        research_by_bucket = {}
        wd_results = {}
        with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
            futures = {executor.submit(_pipeline_one, s): s for s in sections}
            for future in as_completed(futures):
                s = futures[future]
                sid, r_text, title, wd_text = future.result()
                research_by_bucket[sid] = r_text
                wd_results[sid] = (title, wd_text)

        compiled = "\n\n---\n\n".join(research_by_bucket[sid] for sid in sorted(research_by_bucket.keys()))
        (research_dir / "compiled.md").write_text(compiled, encoding="utf-8")
        state.set("research_path", str(research_dir / "compiled.md"))
        state.complete(2)

        wd_parts = [f"## Bucket {sid}: {wd_results[sid][0]}\n\n{wd_results[sid][1]}" for sid in sorted(wd_results.keys())]
        working_doc = f"# Working Document\n\n**Topic:** {topic}\n**Date:** {p.TODAY_STR}\n\n" + "\n\n---\n\n".join(wd_parts)
        (wd_dir / "working_document.md").write_text(working_doc, encoding="utf-8")
        state.set("wd_path", str(wd_dir / "working_document.md"))
        state.complete(3)
        result["outputs"]["working_doc_chars"] = len(working_doc)

        # Research Debrief
        print(f"  [Debrief]...")
        ps = mece.get("smart_statement", "")
        debrief_path = state.dir / "research" / "debrief.md"
        if not debrief_path.exists():
            debrief_text = p.llm(
                f"You are a research analyst debriefing a senior partner. Today is {p.TODAY_STR}. Summarize key findings in 2-3 pages. Every fact must have time period, source, and comparison baseline.",
                f"PROBLEM STATEMENT: {ps}\n\nWORKING DOCUMENT:\n{working_doc[:50000]}\n\nDebrief."
            )
            debrief_path.write_text(f"# Research Debrief\n\n{debrief_text}", encoding="utf-8")

        # Step 4: Synthesis
        print(f"  [Step 4] Synthesis...")
        summary, synthesis = p.step4_synthesis(state, mece, working_doc)
        state.complete(4)
        result["outputs"]["findings"] = len([f for b in synthesis.get("findings", {}).get("buckets", []) for f in b.get("findings", [])])
        result["outputs"]["patterns"] = len(synthesis.get("patterns", {}).get("patterns", []))
        result["outputs"]["inferences"] = len(synthesis.get("inferences", {}).get("inferences", []))

        # Step 5: Hypotheses
        print(f"  [Step 5] Hypotheses...")
        summary, hyp_tree = p.step5_hypotheses(state, mece, working_doc, synthesis)
        state.complete(5)
        all_hyps = hyp_tree.get("hypotheses", [])
        result["outputs"]["hypotheses_total"] = len(all_hyps)
        result["outputs"]["hypotheses_confirmed"] = len([h for h in all_hyps if h.get("status") == "confirmed"])
        result["outputs"]["hypotheses_killed"] = len([h for h in all_hyps if h.get("status") == "killed"])

        # Step 6: Final Document
        print(f"  [Step 6] Final Document...")
        doc_path = p.step6_final_doc(state, mece, hyp_tree, working_doc, synthesis)
        state.complete(6)
        result["outputs"]["final_doc_path"] = doc_path
        result["outputs"]["final_doc_size"] = os.path.getsize(doc_path)

        # Step 7: Appendix
        print(f"  [Step 7] Appendix...")
        app_path = p.step7_appendix(state, mece, hyp_tree, working_doc)
        state.complete(7)
        result["outputs"]["appendix_path"] = app_path

        result["status"] = "success"

    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {str(e)[:500]}"
        result["traceback"] = traceback.format_exc()
        print(f"\n  ERROR: {result['error']}\n")

    t1 = time.time()
    result["end_time"] = datetime.now().isoformat()
    result["duration_s"] = round(t1 - t0, 1)
    result["llm_calls"] = p._llm_call_count

    print(f"\n  Status: {result['status']} | Duration: {result['duration_s']}s | LLM calls: {result['llm_calls']}")
    return result


# ---------------------------------------------------------------------------
# Generate HTML report
# ---------------------------------------------------------------------------

def generate_report(results, sim_run_dir):
    """Generate a single HTML report with all test results."""

    rows = ""
    details = ""
    passed = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_time = sum(r.get("duration_s", 0) or 0 for r in results)
    total_calls = sum(r.get("llm_calls", 0) or 0 for r in results)

    for r in results:
        status_color = "#22c55e" if r["status"] == "success" else "#ef4444"
        status_icon = "&#10004;" if r["status"] == "success" else "&#10008;"

        out = r.get("outputs", {})
        rows += f"""<tr>
<td>{r['id']}</td>
<td>{r['domain']}</td>
<td>{r['type']}</td>
<td>{r['complexity']}</td>
<td style="color:{status_color};font-weight:700">{status_icon} {r['status']}</td>
<td>{r.get('duration_s', '?')}s</td>
<td>{r.get('llm_calls', '?')}</td>
<td>{out.get('mece_buckets', '-')}b / {out.get('mece_questions', '-')}q</td>
<td>{out.get('findings', '-')}</td>
<td>{out.get('patterns', '-')}</td>
<td>{out.get('hypotheses_total', '-')} ({out.get('hypotheses_confirmed', '-')}C / {out.get('hypotheses_killed', '-')}K)</td>
<td><a href="#case-{r['id']}">details</a></td>
</tr>"""

        # Detail section
        error_html = ""
        if r.get("error"):
            error_html = f'<div style="background:#fef2f2;border:1px solid #fecaca;padding:12px;border-radius:6px;margin:8px 0"><strong>Error:</strong> {r["error"]}<pre style="font-size:11px;margin-top:8px;white-space:pre-wrap">{r.get("traceback", "")[:1000]}</pre></div>'

        # Link to outputs
        output_links = ""
        slug = f"sim_{r['id']}_{r['domain'][:20].lower().replace(' ', '_').replace('/', '_')}"
        run_path = sim_run_dir / slug
        if run_path.exists():
            for fname in ["final_document.html", "appendix.html", "tree.html", "research/debrief.md", "synthesis/synthesis.md"]:
                fpath = run_path / fname
                if fpath.exists():
                    output_links += f'<a href="{fpath}" style="margin-right:12px;color:#2563eb">{fname}</a> '

        details += f"""<div id="case-{r['id']}" style="margin:24px 0;padding:16px;border:1px solid #e5e7eb;border-radius:8px">
<h3 style="margin:0 0 8px">Case {r['id']}: {r['domain']} / {r['type']} ({r['complexity']})</h3>
<p style="font-size:13px;color:#666;margin:0 0 12px">{r.get('topic', '')}</p>
<div style="display:flex;gap:24px;font-size:13px;margin-bottom:8px">
<span><strong>Duration:</strong> {r.get('duration_s', '?')}s</span>
<span><strong>LLM calls:</strong> {r.get('llm_calls', '?')}</span>
<span><strong>MECE:</strong> {out.get('mece_buckets', '-')} buckets, {out.get('mece_questions', '-')} questions</span>
<span><strong>Findings:</strong> {out.get('findings', '-')}</span>
<span><strong>Patterns:</strong> {out.get('patterns', '-')}</span>
<span><strong>Hypotheses:</strong> {out.get('hypotheses_total', '-')}</span>
</div>
{error_html}
<div style="font-size:12px;margin-top:8px">{output_links}</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pipeline Simulator Report — {TODAY_STR}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
body{{font-family:'Inter',sans-serif;max-width:1200px;margin:0 auto;padding:32px 24px;color:#1a1a1a;background:#fff}}
h1{{font:800 24px/1.3 'Inter';margin:0 0 8px}}
h2{{font:700 18px/1.3 'Inter';margin:32px 0 12px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:16px 0}}
th{{background:#f8fafc;padding:8px 12px;text-align:left;border-bottom:2px solid #e2e8f0;font-weight:600}}
td{{padding:8px 12px;border-bottom:1px solid #f1f5f9}}
tr:hover{{background:#f8fafc}}
.summary{{display:flex;gap:32px;margin:16px 0 24px;font-size:14px}}
.summary .stat{{padding:12px 20px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0}}
.stat strong{{display:block;font-size:24px;margin-bottom:2px}}
a{{color:#2563eb;text-decoration:none}}
</style></head><body>

<h1>Pipeline Simulator Report</h1>
<p style="color:#666;margin:0 0 4px">{TODAY_STR} | {len(results)} test cases</p>

<div class="summary">
<div class="stat"><strong style="color:#22c55e">{passed}</strong>passed</div>
<div class="stat"><strong style="color:#ef4444">{failed}</strong>failed</div>
<div class="stat"><strong>{total_time:.0f}s</strong>total time</div>
<div class="stat"><strong>{total_calls}</strong>LLM calls</div>
<div class="stat"><strong>{total_time/len(results):.0f}s</strong>avg per case</div>
</div>

<h2>Summary</h2>
<table>
<tr><th>#</th><th>Domain</th><th>Type</th><th>Complexity</th><th>Status</th><th>Time</th><th>LLM Calls</th><th>MECE</th><th>Findings</th><th>Patterns</th><th>Hypotheses</th><th></th></tr>
{rows}
</table>

<h2>Details</h2>
{details}

<div style="text-align:center;color:#bbb;font-size:11px;margin-top:40px;padding-top:12px;border-top:1px solid #e5e7eb">
Pipeline Simulator | Developed by Parth Reddy
</div>
</body></html>"""

    report_path = sim_run_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pipeline Simulator")
    parser.add_argument("--cases", type=str, help="Comma-separated case IDs to run (e.g., 1,3,5)")
    parser.add_argument("--list", action="store_true", help="List test cases without running")
    args = parser.parse_args()

    if args.list:
        print(f"\n  {'#':<4} {'Domain':<25} {'Type':<22} {'Complexity':<10}")
        print(f"  {'—'*4} {'—'*25} {'—'*22} {'—'*10}")
        for tc in TEST_CASES:
            print(f"  {tc['id']:<4} {tc['domain']:<25} {tc['type']:<22} {tc['complexity']:<10}")
            print(f"       {tc['topic'][:90]}...")
        print()
        return

    # Select cases
    if args.cases:
        ids = [int(x.strip()) for x in args.cases.split(",")]
        cases = [tc for tc in TEST_CASES if tc["id"] in ids]
    else:
        cases = TEST_CASES

    # Setup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sim_run_dir = SIM_DIR / f"run_{timestamp}"
    sim_run_dir.mkdir(parents=True, exist_ok=True)

    print(f"""
{'='*60}
  PIPELINE SIMULATOR
{'='*60}

  Cases:    {len(cases)}
  Output:   {sim_run_dir}
  Mode:     Autopilot (all checkpoints auto-approved)
  Started:  {datetime.now().strftime('%H:%M:%S')}
""")

    # Run
    results = []
    for case in cases:
        result = run_one(case, sim_run_dir)
        results.append(result)

        # Save intermediate results
        json.dump(results, open(sim_run_dir / "results.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Generate report
    report_path = generate_report(results, sim_run_dir)

    passed = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_time = sum(r.get("duration_s", 0) or 0 for r in results)

    print(f"""
{'='*60}
  SIMULATOR COMPLETE
{'='*60}

  Passed:   {passed}/{len(results)}
  Failed:   {failed}/{len(results)}
  Time:     {total_time:.0f}s ({total_time/60:.1f} min)
  Report:   {report_path}
""")

    # Open report
    import webbrowser
    webbrowser.open(f"file:///{os.path.abspath(report_path).replace(os.sep, '/')}")


if __name__ == "__main__":
    main()

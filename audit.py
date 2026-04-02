#!/usr/bin/env python3
"""
Anvil Output Audit
==================
Checks output quality: recommendation traceability, chart data sourcing, and LLM injection detection.

Usage:
    python audit.py outputs/runs/openai_commoditization
    python audit.py outputs/runs/openai_commoditization --fix   # Fix issues found
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def audit_run(run_dir):
    """Run full audit on a completed run."""
    run_dir = Path(run_dir)
    if not run_dir.exists():
        print(f"  Error: {run_dir} does not exist")
        return

    print(f"\n  ANVIL AUDIT: {run_dir.name}")
    print(f"  {'='*50}\n")

    issues = []

    # 1. Recommendation Traceability
    print(f"  1. RECOMMENDATION TRACEABILITY")
    print(f"  {'-'*40}")
    issues += audit_traceability(run_dir)

    # 2. Chart Data Sourcing
    print(f"\n  2. CHART DATA SOURCING")
    print(f"  {'-'*40}")
    issues += audit_charts(run_dir)

    # 3. LLM Reasoning Tags
    print(f"\n  3. LLM REASONING TRANSPARENCY")
    print(f"  {'-'*40}")
    issues += audit_llm_tags(run_dir)

    # Summary
    print(f"\n  {'='*50}")
    print(f"  AUDIT SUMMARY: {len(issues)} issues found")
    for i, issue in enumerate(issues, 1):
        print(f"    {i}. [{issue['severity']}] {issue['message']}")

    return issues


def audit_traceability(run_dir):
    """Check if recommendations trace back to sourced findings."""
    issues = []

    # Load synthesis
    syn_path = run_dir / "synthesis" / "synthesis.json"
    if not syn_path.exists():
        print(f"    No synthesis.json found")
        return [{"severity": "ERROR", "message": "No synthesis data to trace"}]

    synthesis = json.load(open(syn_path, encoding="utf-8"))
    findings = synthesis.get("findings", {}).get("buckets", [])
    patterns = synthesis.get("patterns", {}).get("patterns", [])
    inferences = synthesis.get("inferences", {}).get("inferences", [])

    # Load hypotheses
    hyp_path = run_dir / "hypotheses" / "hypotheses.json"
    if not hyp_path.exists():
        print(f"    No hypotheses.json found")
        return [{"severity": "ERROR", "message": "No hypotheses to audit"}]

    hyp_tree = json.load(open(hyp_path, encoding="utf-8"))
    hypotheses = hyp_tree.get("hypotheses", [])

    # Check each hypothesis traces to patterns/findings
    all_finding_ids = set()
    for b in findings:
        for f in b.get("findings", []):
            all_finding_ids.add(f.get("id", ""))

    all_pattern_ids = set(p.get("id", "") for p in patterns)
    all_inference_ids = set(i.get("id", "") for i in inferences)

    traced = 0
    untraced = 0
    for h in hypotheses:
        hid = h.get("id", "?")
        src_findings = h.get("source_findings", [])
        src_patterns = h.get("source_patterns", [])
        src_inferences = h.get("source_inferences", [])

        has_trace = bool(src_findings or src_patterns or src_inferences)
        if has_trace:
            traced += 1
            print(f"    [OK] {hid}: traces to {len(src_findings)}F, {len(src_patterns)}P, {len(src_inferences)}I")
        else:
            untraced += 1
            print(f"    [!!] {hid}: NO TRACE — may be LLM-generated")
            issues.append({"severity": "WARN", "message": f"Hypothesis {hid} has no source trace — may be LLM-injected"})

    print(f"    Traced: {traced}/{traced+untraced}")
    return issues


def audit_charts(run_dir):
    """Check if chart values appear in the final document."""
    issues = []

    # Load slides
    slides_path = run_dir / "appendix" / "slides.json"
    if not slides_path.exists():
        print(f"    No slides.json found")
        return [{"severity": "ERROR", "message": "No appendix slides to audit"}]

    slides = json.load(open(slides_path, encoding="utf-8"))

    # Load final document text
    doc_path = run_dir / "final_document.html"
    if not doc_path.exists():
        print(f"    No final_document.html found")
        return []

    doc_text = re.sub(r'<[^>]+>', ' ', doc_path.read_text(encoding="utf-8"))

    for s in slides.get("slides", []):
        num = s.get("appendix_num", "?")
        title = s.get("action_title", "?")[:50]
        cd = s.get("chart_data", {})

        if not isinstance(cd, dict):
            continue

        values = cd.get("values", [])
        sourced = 0
        unsourced = 0

        for v in values:
            if isinstance(v, (int, float)):
                # Check if this number appears in the document
                v_str = str(int(v)) if v == int(v) else str(v)
                if v_str in doc_text:
                    sourced += 1
                else:
                    unsourced += 1

        if unsourced > 0:
            print(f"    [!!] Slide {num}: {unsourced}/{len(values)} values NOT in document — {title}")
            issues.append({"severity": "WARN", "message": f"Slide {num} has {unsourced} unsourced chart values"})
        else:
            print(f"    [OK] Slide {num}: all {sourced} values found in document — {title}")

    return issues


def audit_llm_tags(run_dir):
    """Check if LLM reasoning is properly tagged throughout."""
    issues = []

    # Check research buckets
    research_dir = run_dir / "research"
    if research_dir.exists():
        total_reasoning = 0
        tagged_reasoning = 0
        for f in sorted(research_dir.glob("bucket_*.md")):
            text = f.read_text(encoding="utf-8")
            # Count [LLM reasoning] tags
            tags = text.count("[LLM reasoning]")
            total_reasoning += tags

            # Look for analytical reasoning without tags
            reasoning_phrases = [
                "typically", "generally", "historically",
                "in practice", "as a rule", "conventionally",
                "industry standard", "common pattern",
            ]
            untagged = 0
            for phrase in reasoning_phrases:
                matches = [m for m in re.finditer(phrase, text, re.IGNORECASE)]
                for m in matches:
                    # Check if [LLM reasoning] appears within 200 chars after
                    after = text[m.end():m.end()+200]
                    if "[LLM reasoning]" not in after:
                        untagged += 1

        print(f"    [LLM reasoning] tags found: {total_reasoning}")
        if total_reasoning == 0:
            issues.append({"severity": "WARN", "message": "No [LLM reasoning] tags in research — analytical reasoning may be unmarked"})
            print(f"    [!!] No tags found — reasoning may be presented as sourced fact")
        else:
            print(f"    [OK] Research has {total_reasoning} tagged reasoning statements")

    # Check final document
    doc_path = run_dir / "final_document.html"
    if doc_path.exists():
        doc_text = doc_path.read_text(encoding="utf-8")
        doc_tags = doc_text.count("[LLM reasoning]")
        source_citations = len(re.findall(r'\(per [^)]+\)', doc_text))
        print(f"    Final doc: {source_citations} source citations, {doc_tags} [LLM reasoning] tags")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Audit Anvil outputs")
    parser.add_argument("run_dir", help="Path to run directory")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues (future)")
    args = parser.parse_args()

    audit_run(args.run_dir)


if __name__ == "__main__":
    main()

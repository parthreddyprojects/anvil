#!/usr/bin/env python3
"""
Step 2: Generate working documents for all 3 problem statements.
Each bucket gets its own LLM call with only the relevant research themes.
Parallel execution across buckets and PS.

Usage:
    python run_working_doc.py
    python run_working_doc.py --ps 1   # just PS1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
ROOT = Path(__file__).parent
OUTPUTS = ROOT.parent / "outputs"
MECE_DIR = OUTPUTS / "mece_3ps"
RESEARCH_DIR = OUTPUTS / "research"
BRIEFS_DIR = RESEARCH_DIR / "briefs"
WD_DIR = OUTPUTS / "working_docs"

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


def call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break
    if response.stop_reason == "max_tokens" and text:
        resp2 = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[
                {"role": "user", "content": user},
                {"role": "assistant", "content": text},
                {"role": "user", "content": "Continue EXACTLY where you left off. Do not repeat any content."},
            ],
        )
        for block2 in resp2.content:
            if block2.type == "text":
                text += block2.text
                break
    return text


def print_divider(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}\n")


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------


def load_ps(ps_id: int) -> dict:
    path = MECE_DIR / f"ps{ps_id}" / "3_final.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_scored_questions() -> list[dict]:
    path = RESEARCH_DIR / "1a_scored_questions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_theme_map() -> dict:
    path = RESEARCH_DIR / "1b_question_theme_map.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_research_brief(theme_id: str) -> str | None:
    """Load a single research brief by theme_id."""
    for f in BRIEFS_DIR.glob(f"{theme_id}_*.md"):
        return f.read_text(encoding="utf-8")
    return None


def get_relevant_themes_for_bucket(ps_id: int, bucket_id: int, theme_map: dict, scored_qs: list[dict]) -> set[str]:
    """Find which research themes are relevant for a given bucket."""
    ps_label = f"PS{ps_id}"
    # Find all question IDs in this bucket
    bucket_qids = set()
    for q in scored_qs:
        if q["ps"] == ps_label and q["bucket_id"] == bucket_id:
            bucket_qids.add(q["question_id"])

    # Find which themes cover these questions
    relevant_themes = set()
    for theme_id, mapped_qs in theme_map.items():
        if theme_id.startswith("_"):
            continue
        for mq in mapped_qs:
            if mq["ps"] == ps_label and mq["qid"] in bucket_qids:
                relevant_themes.add(theme_id)
                break

    return relevant_themes


# ---------------------------------------------------------------------------
# Working Document Generation
# ---------------------------------------------------------------------------

WD_SYSTEM = """\
You are a senior strategic analyst at a top-tier advisory firm writing a \
crisis working document for C-suite executives. You synthesize research into \
clear, actionable findings. Every claim must be grounded in the research \
provided. Use specific numbers with sources. Flag confidence levels.

RULES:
- Lead with the answer, not the analysis
- Every number must have a source and confidence level (HIGH/MEDIUM/LOW)
- Tier 3 questions: extrapolate from research + domain knowledge, clearly \
  mark as "EXTRAPOLATED" with the reasoning chain
- Use bullet points for data, short paragraphs for narrative
- Bold the most critical findings
- End each section with "DECISION IMPLICATION: [one sentence]"
- Maximum 800 words per bucket"""

WD_USER = """\
PROBLEM STATEMENT ({ps_label}):
{smart_statement}

BUCKET {bucket_id}: {bucket_title}
Rationale: {rationale}

QUESTIONS TO ANSWER:
{questions_formatted}

RELEVANT RESEARCH:
{research_text}

Write the working document section for this bucket. For each question:
- If Tier 1 or Tier 2: Answer with data from the research above. Cite source + confidence.
- If Tier 3: Extrapolate from available data. Mark as "EXTRAPOLATED" and explain reasoning.
- If research doesn't cover it: Say "DATA GAP" and provide best estimate with caveats.

End with:
1. KEY FINDINGS (3-5 bullet points, most critical first)
2. DECISION IMPLICATION (one sentence: what this means for the decision)"""


def generate_bucket_wd(
    client: anthropic.Anthropic,
    ps_id: int,
    ps_data: dict,
    section: dict,
    scored_qs: list[dict],
    theme_map: dict,
) -> tuple[int, str]:
    """Generate working document for one bucket. Returns (bucket_id, text)."""
    bucket_id = section["section_id"]
    ps_label = f"PS{ps_id}"

    # Get questions with tier info
    questions = []
    for q in section["questions"]:
        tier = 2  # default
        for sq in scored_qs:
            if sq["ps"] == ps_label and sq["question_id"] == q["id"]:
                tier = sq["tier"]
                break
        tier_label = {1: "T1-DEEP", 2: "T2-MODERATE", 3: "T3-EXTRAPOLATE"}[tier]
        questions.append(f"[{q['id']}] ({tier_label}) {q['question']}")

    questions_formatted = "\n".join(questions)

    # Load relevant research
    relevant_themes = get_relevant_themes_for_bucket(ps_id, bucket_id, theme_map, scored_qs)
    research_parts = []
    for tid in sorted(relevant_themes):
        brief = load_research_brief(tid)
        if brief:
            # Trim to essentials — skip the header, just content
            lines = brief.split("\n")
            content_lines = [l for l in lines if not l.startswith("#") and not l.startswith("**Scope")]
            research_parts.append(f"--- {tid} ---\n" + "\n".join(content_lines)[:4000])

    research_text = "\n\n".join(research_parts) if research_parts else "No specific research available for this bucket. Use domain knowledge."

    # Trim research if too long (stay under ~12K tokens input)
    if len(research_text) > 20000:
        research_text = research_text[:20000] + "\n\n[RESEARCH TRUNCATED — focus on most relevant findings]"

    prompt = WD_USER.format(
        ps_label=ps_label,
        smart_statement=ps_data["smart_statement"][:300],
        bucket_id=bucket_id,
        bucket_title=section["title"],
        rationale=section.get("rationale", ""),
        questions_formatted=questions_formatted,
        research_text=research_text,
    )

    text = call_claude(client, WD_SYSTEM, prompt)
    return bucket_id, text


def generate_exec_summary(
    client: anthropic.Anthropic,
    ps_id: int,
    ps_data: dict,
    bucket_sections: dict[int, str],
) -> str:
    """Generate executive summary from all bucket sections."""
    # Collect key findings from each bucket
    findings_text = ""
    for sec in ps_data["sections"]:
        bid = sec["section_id"]
        if bid in bucket_sections:
            # Extract KEY FINDINGS section
            text = bucket_sections[bid]
            findings_start = text.find("KEY FINDINGS")
            if findings_start > -1:
                findings_text += f"\nBucket {bid} ({sec['title'][:50]}):\n"
                findings_text += text[findings_start:findings_start + 500] + "\n"

    system = (
        "You are a senior partner writing a 4-sentence executive summary for a "
        "crisis decision brief. Be direct. Lead with the conclusion. Include "
        "one anchor number. State what must be decided."
    )
    prompt = (
        f"PROBLEM STATEMENT (PS{ps_id}):\n{ps_data['smart_statement'][:300]}\n\n"
        f"KEY FINDINGS FROM ALL BUCKETS:\n{findings_text}\n\n"
        f"Write a 4-sentence executive summary. Sentence 1: the situation and "
        f"anchor number. Sentence 2: the core finding. Sentence 3: the risk. "
        f"Sentence 4: what must be decided by when."
    )
    return call_claude(client, system, prompt)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_ps_working_doc(client: anthropic.Anthropic, ps_id: int, scored_qs: list, theme_map: dict):
    """Generate full working document for one PS."""
    ps_data = load_ps(ps_id)
    ps_dir = WD_DIR / f"ps{ps_id}"
    ps_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  PS{ps_id}: {len(ps_data['sections'])} buckets")

    bucket_sections: dict[int, str] = {}
    t0 = time.time()

    # Run buckets in parallel (4 workers)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for section in ps_data["sections"]:
            future = executor.submit(
                generate_bucket_wd, client, ps_id, ps_data, section, scored_qs, theme_map
            )
            futures[future] = section

        for future in as_completed(futures):
            section = futures[future]
            try:
                bid, text = future.result()
                bucket_sections[bid] = text
                # Save individual bucket
                (ps_dir / f"bucket_{bid:02d}.md").write_text(text, encoding="utf-8")
                elapsed = time.time() - t0
                print(f"    [{elapsed:5.0f}s] Bucket {bid} done ({len(text)} chars)")
            except Exception as e:
                print(f"    ERROR on bucket {section['section_id']}: {e}")
                bucket_sections[section["section_id"]] = f"ERROR: {e}"

    # Generate executive summary
    print(f"    Generating executive summary...")
    exec_summary = generate_exec_summary(client, ps_id, ps_data, bucket_sections)

    # Compile full working document
    parts = [
        f"# Working Document — PS{ps_id}\n",
        f"**Problem Statement:**\n{ps_data['smart_statement']}\n",
    ]
    if ps_data.get("decision_sensitivity"):
        parts.append(f"**Decision Sensitivity:**\n{ps_data['decision_sensitivity']}\n")
    parts.append(f"\n## Executive Summary\n\n{exec_summary}\n")
    parts.append("\n---\n")

    for section in ps_data["sections"]:
        bid = section["section_id"]
        parts.append(f"\n## Bucket {bid}: {section['title']}\n")
        parts.append(bucket_sections.get(bid, "NOT GENERATED") + "\n")
        parts.append("\n---\n")

    full_doc = "\n".join(parts)
    doc_path = ps_dir / "working_document.md"
    doc_path.write_text(full_doc, encoding="utf-8")

    elapsed = time.time() - t0
    print(f"    DONE in {elapsed:.0f}s — {len(full_doc) // 1024}KB — {doc_path}")

    return full_doc


def main():
    parser = argparse.ArgumentParser(description="Step 2: Generate working documents")
    parser.add_argument("--ps", type=int, action="append", choices=[1, 2, 3])
    args = parser.parse_args()

    client = get_client()
    WD_DIR.mkdir(parents=True, exist_ok=True)

    scored_qs = load_scored_questions()
    theme_map = load_theme_map()

    ps_ids = args.ps or [1, 2, 3]

    print_divider("STEP 2: WORKING DOCUMENTS")
    print(f"  Running for: PS{', PS'.join(str(i) for i in ps_ids)}")
    print(f"  Model: {MODEL}")

    t_start = time.time()

    for ps_id in ps_ids:
        run_ps_working_doc(client, ps_id, scored_qs, theme_map)

    t_end = time.time()

    print_divider("STEP 2 COMPLETE")
    print(f"  Total time: {t_end - t_start:.0f}s")
    print(f"  Output dir: {WD_DIR.resolve()}")

    # Print sizes
    for ps_id in ps_ids:
        doc_path = WD_DIR / f"ps{ps_id}" / "working_document.md"
        if doc_path.exists():
            size = doc_path.stat().st_size // 1024
            print(f"  PS{ps_id}: {size}KB")


if __name__ == "__main__":
    main()

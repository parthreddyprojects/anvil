#!/usr/bin/env python3
"""
Story Engine — Steps 0-3 of the strategic intelligence briefing pipeline.

Usage:
    python engine.py --topic "Iran Hormuz crisis" --audience "Indian refinery C-suite"
    python engine.py --resume
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from models import (
    CardDeck,
    PipelineState,
    ProblemStatement,
    ResearchPrompt,
    WorkingDocument,
)
from prompts import (
    CARD_DECOMPOSITION_SYSTEM,
    CARD_DECOMPOSITION_USER,
    MECE_AUDIT_SYSTEM,
    MECE_AUDIT_USER,
    MECE_MERGE_SYSTEM,
    MECE_MERGE_USER,
    PROBLEM_FRAMING_REVISION,
    PROBLEM_FRAMING_SYSTEM,
    PROBLEM_FRAMING_USER,
    RESEARCH_PROMPT_SYSTEM,
    RESEARCH_PROMPT_USER,
    WORKING_DOCUMENT_SYSTEM,
    WORKING_DOCUMENT_USER,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
OUTPUT_DIR = Path(__file__).parent / "output"
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    """Create the output directory tree if it doesn't exist."""
    for sub in ["", "research_prompts", "research"]:
        (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)


def load_state() -> PipelineState | None:
    """Load saved pipeline state, or return None."""
    if STATE_FILE.exists():
        return PipelineState.model_validate_json(STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_state(state: PipelineState) -> None:
    STATE_FILE.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    """Send a single-turn message to Claude and return the text response."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    # Extract text from the first content block
    for block in response.content:
        if block.type == "text":
            return block.text
    raise RuntimeError("Claude returned no text content")


def parse_json_response(text: str) -> dict:
    """Extract JSON from a Claude response, stripping markdown fences if present."""
    cleaned = text.strip()
    # Strip ```json ... ``` wrappers
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        cleaned = cleaned[first_newline + 1 : last_fence].strip()
    return json.loads(cleaned)


def print_divider(title: str) -> None:
    width = 72
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


def human_checkpoint(step_name: str) -> str | None:
    """Prompt the human for approval or feedback. Returns None if approved."""
    print_divider(f"CHECKPOINT — {step_name}")
    print("Review the output above.")
    print("  [Enter]        → Approve and continue")
    print("  [Type feedback] → Revise with your feedback")
    print("  [q]            → Quit pipeline\n")
    response = input(">>> ").strip()
    if response.lower() == "q":
        print("Pipeline paused. Use --resume to continue later.")
        sys.exit(0)
    return response if response else None


# ---------------------------------------------------------------------------
# Step 0 — Problem Framing
# ---------------------------------------------------------------------------


def step0_problem_framing(
    client: anthropic.Anthropic, topic: str, audience: str
) -> ProblemStatement:
    """Draft and refine the SMART problem statement + MECE sub-questions."""
    print_divider("STEP 0: Problem Framing")
    print(f"Topic:    {topic}")
    print(f"Audience: {audience}\n")
    print("Generating problem statement and MECE breakdown...")

    user_prompt = PROBLEM_FRAMING_USER.format(topic=topic, audience=audience)
    raw = call_claude(client, PROBLEM_FRAMING_SYSTEM, user_prompt)
    data = parse_json_response(raw)

    revision_history: list[str] = []

    while True:
        # Build and display
        ps = ProblemStatement(
            topic=topic,
            audience=audience,
            smart_statement=data["smart_statement"],
            sections=data["sections"],
            revision_history=revision_history,
        )
        _print_problem_statement(ps)

        feedback = human_checkpoint("Problem Framing")
        if feedback is None:
            break

        # Revise
        revision_history.append(feedback)
        print("\nRevising with your feedback...")
        revision_prompt = PROBLEM_FRAMING_REVISION.format(
            feedback=feedback,
            previous_output=json.dumps(data, indent=2),
        )
        raw = call_claude(client, PROBLEM_FRAMING_SYSTEM, revision_prompt)
        data = parse_json_response(raw)

    # Persist
    ps_path = OUTPUT_DIR / "problem_statement.json"
    ps_path.write_text(ps.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nSaved → {ps_path}")
    return ps


def _print_problem_statement(ps: ProblemStatement) -> None:
    print(f"\nPROBLEM STATEMENT:\n  {ps.smart_statement}\n")
    for sec in ps.sections:
        print(f"  Section {sec.section_id}: {sec.title}")
        print(f"    Rationale: {sec.rationale}")
        for q in sec.questions:
            print(f"      [{q.id}] {q.question}")
        print()


# ---------------------------------------------------------------------------
# Step 0b — MECE Audit
# ---------------------------------------------------------------------------


def step0b_mece_audit(
    client: anthropic.Anthropic, ps: ProblemStatement
) -> ProblemStatement:
    """Run adversarial MECE audit and merge missing questions."""
    print_divider("STEP 0b: MECE Audit")
    print("Running adversarial gap analysis on MECE decomposition...")

    # Build the decomposition JSON for the audit prompt
    decomposition = {
        "smart_statement": ps.smart_statement,
        "sections": [
            {
                "section_id": s.section_id,
                "title": s.title,
                "rationale": s.rationale,
                "questions": [{"id": q.id, "question": q.question} for q in s.questions],
            }
            for s in ps.sections
        ],
    }

    audit_prompt = MECE_AUDIT_USER.format(
        smart_statement=ps.smart_statement,
        audience=ps.audience,
        decomposition_json=json.dumps(decomposition, indent=2),
    )

    raw = call_claude(client, MECE_AUDIT_SYSTEM, audit_prompt)
    audit_data = parse_json_response(raw)

    # Print audit summary
    total_added = audit_data.get("total_questions_added", 0)
    verdict = audit_data.get("overall_verdict", "unknown")
    missing_buckets = audit_data.get("missing_buckets", [])
    duplicates = audit_data.get("duplicate_flags", [])

    print(f"\n  Verdict: {verdict}")
    print(f"  Questions to add: {total_added}")
    print(f"  Missing buckets: {len(missing_buckets)}")
    print(f"  Duplicate flags: {len(duplicates)}")

    for ba in audit_data.get("bucket_audits", []):
        gaps = [d for d in ba.get("dimensions_found", []) if d["status"] == "missing"]
        if gaps:
            print(f"\n  Bucket {ba['section_id']}: {ba['title']} — {len(gaps)} gaps")
            for g in gaps:
                nq = g.get("new_question", {})
                print(f"    + [{nq.get('id', '?')}] {nq.get('question', '?')[:80]}")

    for mb in missing_buckets:
        print(f"\n  NEW BUCKET: {mb['title']}")
        for q in mb.get("questions", []):
            print(f"    + [{q['id']}] {q['question'][:80]}")

    if duplicates:
        print("\n  DUPLICATES:")
        for d in duplicates:
            print(f"    {d['question_ids']} — {d['reason']}")

    if verdict == "pass" and total_added == 0:
        print("\n  MECE decomposition passed audit — no changes needed.")
        return ps

    # Merge audit results
    print("\n  Merging audit results into decomposition...")
    merge_prompt = MECE_MERGE_USER.format(
        original_json=json.dumps(decomposition, indent=2),
        audit_json=json.dumps(audit_data, indent=2),
    )
    raw = call_claude(client, MECE_MERGE_SYSTEM, merge_prompt)
    merged_data = parse_json_response(raw)

    # Build updated ProblemStatement
    from models import MECESection, SubQuestion

    new_sections = []
    for sec in merged_data.get("sections", []):
        questions = [
            SubQuestion(id=q["id"], question=q["question"])
            for q in sec.get("questions", [])
        ]
        new_sections.append(
            MECESection(
                section_id=sec["section_id"],
                title=sec["title"],
                rationale=sec.get("rationale", ""),
                questions=questions,
            )
        )

    updated_ps = ProblemStatement(
        topic=ps.topic,
        audience=ps.audience,
        smart_statement=merged_data.get("smart_statement", ps.smart_statement),
        sections=new_sections,
        revision_history=ps.revision_history + ["[MECE audit applied]"],
    )

    # Count
    orig_count = sum(len(s.questions) for s in ps.sections)
    new_count = sum(len(s.questions) for s in updated_ps.sections)
    print(f"\n  Questions: {orig_count} → {new_count} (+{new_count - orig_count})")
    print(f"  Buckets: {len(ps.sections)} → {len(updated_ps.sections)}")

    _print_problem_statement(updated_ps)

    # Persist
    ps_path = OUTPUT_DIR / "problem_statement_audited.json"
    ps_path.write_text(updated_ps.model_dump_json(indent=2), encoding="utf-8")

    # Also save raw audit for reference
    audit_path = OUTPUT_DIR / "mece_audit.json"
    audit_path.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")
    print(f"\n  Saved audited PS → {ps_path}")
    print(f"  Saved audit log  → {audit_path}")

    return updated_ps


# ---------------------------------------------------------------------------
# Step 1 — Research
# ---------------------------------------------------------------------------


def step1_research(
    client: anthropic.Anthropic, ps: ProblemStatement
) -> str:
    """Generate research prompts or compile existing research files."""
    print_divider("STEP 1: Research")

    research_dir = OUTPUT_DIR / "research"
    prompts_dir = OUTPUT_DIR / "research_prompts"

    # Check for pre-existing research markdown files
    existing_research = sorted(research_dir.glob("*.md"))
    if existing_research:
        print(f"Found {len(existing_research)} existing research file(s). Compiling...")
        compiled = _compile_existing_research(existing_research)
    else:
        print("No existing research found. Generating research prompts...")
        compiled = _generate_research_prompts(client, ps, prompts_dir)

    # Save compiled research
    compiled_path = OUTPUT_DIR / "research_compiled.md"
    compiled_path.write_text(compiled, encoding="utf-8")
    print(f"\nSaved → {compiled_path}")

    # Step 1 is automated — no human checkpoint
    return compiled


def _compile_existing_research(files: list[Path]) -> str:
    """Read and concatenate existing research markdown files."""
    parts: list[str] = []
    for f in files:
        content = f.read_text(encoding="utf-8")
        parts.append(f"# Research: {f.stem}\n\n{content}")
    return "\n\n---\n\n".join(parts)


def _generate_research_prompts(
    client: anthropic.Anthropic,
    ps: ProblemStatement,
    prompts_dir: Path,
) -> str:
    """Generate research prompts for each MECE section and save them."""
    all_prompts: list[ResearchPrompt] = []

    for sec in ps.sections:
        questions_fmt = "\n".join(
            f"  - [{q.id}] {q.question}" for q in sec.questions
        )
        user_prompt = RESEARCH_PROMPT_USER.format(
            topic=ps.topic,
            audience=ps.audience,
            smart_statement=ps.smart_statement,
            section_id=sec.section_id,
            section_title=sec.title,
            rationale=sec.rationale,
            questions_formatted=questions_fmt,
        )
        print(f"  Generating prompt for section {sec.section_id}: {sec.title}...")
        prompt_text = call_claude(client, RESEARCH_PROMPT_SYSTEM, user_prompt)

        rp = ResearchPrompt(
            section_id=sec.section_id,
            section_title=sec.title,
            prompt=prompt_text,
            questions_covered=[q.id for q in sec.questions],
        )
        all_prompts.append(rp)

        # Save individual prompt
        prompt_path = prompts_dir / f"section_{sec.section_id:02d}.md"
        prompt_path.write_text(prompt_text, encoding="utf-8")

    # Build a compiled placeholder with the prompts
    parts: list[str] = []
    for rp in all_prompts:
        parts.append(
            f"# Section {rp.section_id}: {rp.section_title}\n\n"
            f"## Research Prompt\n\n{rp.prompt}\n\n"
            f"## Findings\n\n"
            f"*[Pending — run the research prompts above with a web-search agent, "
            f"then save results to output/research/section_{rp.section_id:02d}.md "
            f"and re-run with --resume]*"
        )

    print(f"\n  Saved {len(all_prompts)} research prompts to {prompts_dir}/")
    print(
        "  To proceed, run each prompt with a web-search agent and save results\n"
        "  as output/research/section_NN.md, then re-run with --resume."
    )
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Step 2 — Working Document
# ---------------------------------------------------------------------------


def step2_working_document(
    client: anthropic.Anthropic,
    ps: ProblemStatement,
    research: str,
) -> WorkingDocument:
    """Generate the working document from compiled research."""
    print_divider("STEP 2: Working Document")
    print("Generating working document from compiled research...")

    mece_structure = "\n".join(
        f"  Section {s.section_id}: {s.title} — {s.rationale}"
        for s in ps.sections
    )

    user_prompt = WORKING_DOCUMENT_USER.format(
        topic=ps.topic,
        audience=ps.audience,
        smart_statement=ps.smart_statement,
        mece_structure=mece_structure,
        research=research,
    )
    raw = call_claude(client, WORKING_DOCUMENT_SYSTEM, user_prompt)
    data = parse_json_response(raw)

    wd = WorkingDocument(**data)
    _print_working_document_summary(wd)

    feedback = human_checkpoint("Working Document")
    if feedback:
        # For simplicity, regenerate with feedback appended
        print("\nRevising working document with your feedback...")
        revision_prompt = (
            f"{user_prompt}\n\nANALYST FEEDBACK ON PREVIOUS DRAFT:\n{feedback}\n\n"
            f"PREVIOUS DRAFT:\n{json.dumps(data, indent=2)}\n\n"
            "Revise the document to incorporate this feedback. Return the same JSON schema."
        )
        raw = call_claude(client, WORKING_DOCUMENT_SYSTEM, revision_prompt)
        data = parse_json_response(raw)
        wd = WorkingDocument(**data)
        _print_working_document_summary(wd)

    # Persist as markdown
    md_path = OUTPUT_DIR / "working_document.md"
    md_path.write_text(_working_document_to_markdown(wd), encoding="utf-8")
    print(f"\nSaved → {md_path}")

    # Also save JSON for downstream steps
    json_path = OUTPUT_DIR / "working_document.json"
    json_path.write_text(wd.model_dump_json(indent=2), encoding="utf-8")

    return wd


def _print_working_document_summary(wd: WorkingDocument) -> None:
    print(f"\nTITLE: {wd.title}\n")
    print(f"EXECUTIVE SUMMARY:\n  {wd.executive_summary}\n")
    print("SECTIONS:")
    for sec in wd.sections:
        print(f"  {sec.section_id}. {sec.title}")
        for finding in sec.key_findings[:3]:
            print(f"     - {finding}")
    print("\nANALYST VIEWS:")
    for av in wd.analyst_compare_contrast:
        wrapped = textwrap.fill(av.summary, width=68, initial_indent="     ", subsequent_indent="     ")
        print(f"  [{av.analyst_label}]")
        print(wrapped)


def _working_document_to_markdown(wd: WorkingDocument) -> str:
    lines = [
        f"# {wd.title}\n",
        f"## Executive Summary\n\n{wd.executive_summary}\n",
    ]
    for sec in wd.sections:
        lines.append(f"## {sec.section_id}. {sec.title}\n\n{sec.body}\n")
        lines.append("**Key Findings:**\n")
        for f in sec.key_findings:
            lines.append(f"- {f}")
        lines.append("")
    lines.append("## Analyst Compare & Contrast\n")
    for av in wd.analyst_compare_contrast:
        lines.append(f"### {av.analyst_label}\n\n{av.summary}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 3 — Card Decomposition
# ---------------------------------------------------------------------------


def step3_card_decomposition(
    client: anthropic.Anthropic,
    ps: ProblemStatement,
    wd: WorkingDocument,
) -> CardDeck:
    """Decompose the working document into a visual card deck."""
    print_divider("STEP 3: Card Decomposition")
    print("Generating card deck from working document...")

    working_doc_text = _working_document_to_markdown(wd)

    user_prompt = CARD_DECOMPOSITION_USER.format(
        topic=ps.topic,
        audience=ps.audience,
        working_document=working_doc_text,
    )
    raw = call_claude(client, CARD_DECOMPOSITION_SYSTEM, user_prompt)
    data = parse_json_response(raw)

    deck = CardDeck(topic=ps.topic, audience=ps.audience, cards=data["cards"])
    _print_card_summary(deck)

    feedback = human_checkpoint("Card Decomposition")
    if feedback:
        print("\nRevising card deck with your feedback...")
        revision_prompt = (
            f"{user_prompt}\n\nFEEDBACK ON PREVIOUS DECK:\n{feedback}\n\n"
            f"PREVIOUS DECK:\n{json.dumps(data, indent=2)}\n\n"
            "Revise the card deck to incorporate this feedback. Return the same JSON schema."
        )
        raw = call_claude(client, CARD_DECOMPOSITION_SYSTEM, revision_prompt)
        data = parse_json_response(raw)
        deck = CardDeck(topic=ps.topic, audience=ps.audience, cards=data["cards"])
        _print_card_summary(deck)

    # Persist
    spec_path = OUTPUT_DIR / "card_spec.json"
    spec_path.write_text(deck.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nSaved → {spec_path}")
    return deck


def _print_card_summary(deck: CardDeck) -> None:
    print(f"\nCARD DECK — {len(deck.cards)} cards\n")
    current_act = None
    for card in deck.cards:
        if card.act.value != current_act:
            current_act = card.act.value
            print(f"  --- Act {current_act} ---")
        vis_types = ", ".join(sm.visual_type.value for sm in card.sub_messages)
        print(
            f"  [{card.card_id}] {card.card_type.value:15s} | "
            f"{card.key_message[:60]}"
        )
        print(f"           visuals: {vis_types} | rel: {card.relationship.value}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_pipeline(topic: str, audience: str, resume_from: int = -1) -> None:
    """Execute the 4-step pipeline with human checkpoints."""
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in environment or .env file.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    ensure_dirs()

    state = PipelineState(topic=topic, audience=audience, last_completed_step=resume_from)

    # ------------------------------------------------------------------
    # Step 0
    # ------------------------------------------------------------------
    if state.last_completed_step < 0:
        ps = step0_problem_framing(client, topic, audience)
        # Run MECE audit immediately after framing
        ps = step0b_mece_audit(client, ps)
        # Overwrite problem_statement.json with audited version
        ps_path = OUTPUT_DIR / "problem_statement.json"
        ps_path.write_text(ps.model_dump_json(indent=2), encoding="utf-8")
        state.last_completed_step = 0
        save_state(state)
    else:
        # Try audited version first, fall back to original
        ps_path = OUTPUT_DIR / "problem_statement_audited.json"
        if not ps_path.exists():
            ps_path = OUTPUT_DIR / "problem_statement.json"
        if not ps_path.exists():
            print("ERROR: Cannot resume — problem_statement.json not found.")
            sys.exit(1)
        ps = ProblemStatement.model_validate_json(
            ps_path.read_text(encoding="utf-8")
        )
        print(f"Loaded problem statement from {ps_path}")

    # ------------------------------------------------------------------
    # Step 1
    # ------------------------------------------------------------------
    if state.last_completed_step < 1:
        research = step1_research(client, ps)
        state.last_completed_step = 1
        save_state(state)
    else:
        compiled_path = OUTPUT_DIR / "research_compiled.md"
        if not compiled_path.exists():
            print("ERROR: Cannot resume — research_compiled.md not found.")
            sys.exit(1)
        research = compiled_path.read_text(encoding="utf-8")
        print(f"Loaded compiled research from {compiled_path}")

    # ------------------------------------------------------------------
    # Step 2
    # ------------------------------------------------------------------
    if state.last_completed_step < 2:
        wd = step2_working_document(client, ps, research)
        state.last_completed_step = 2
        save_state(state)
    else:
        wd_path = OUTPUT_DIR / "working_document.json"
        if not wd_path.exists():
            print("ERROR: Cannot resume — working_document.json not found.")
            sys.exit(1)
        wd = WorkingDocument.model_validate_json(
            wd_path.read_text(encoding="utf-8")
        )
        print(f"Loaded working document from {wd_path}")

    # ------------------------------------------------------------------
    # Step 3
    # ------------------------------------------------------------------
    if state.last_completed_step < 3:
        deck = step3_card_decomposition(client, ps, wd)
        state.last_completed_step = 3
        save_state(state)
    else:
        print("All steps already completed. Nothing to do.")
        return

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    print_divider("PIPELINE COMPLETE")
    print(f"  Cards generated: {len(deck.cards)}")
    print(f"  Output dir:      {OUTPUT_DIR.resolve()}")
    print(f"\n  Next step: feed card_spec.json into the Presentation Engine.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Story Engine — strategic intelligence briefing pipeline (Steps 0-3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python engine.py --topic "Iran Hormuz crisis" --audience "Indian refinery C-suite"
              python engine.py --topic "Red Sea Houthi escalation" --audience "European LNG buyers"
              python engine.py --resume
        """),
    )
    parser.add_argument("--topic", type=str, help="Intelligence topic to analyse")
    parser.add_argument("--audience", type=str, help="Target audience for the briefing")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last saved checkpoint",
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=[0, 1, 2, 3],
        help="Force start from a specific step (advanced)",
    )

    args = parser.parse_args()

    if args.resume:
        state = load_state()
        if state is None:
            print("ERROR: No saved pipeline state found. Start a new run with --topic and --audience.")
            sys.exit(1)
        print(f"Resuming pipeline for: {state.topic}")
        print(f"Last completed step: {state.last_completed_step}")
        resume_from = state.last_completed_step
        if args.step is not None and args.step <= resume_from:
            resume_from = args.step - 1  # force re-run from this step
        run_pipeline(state.topic, state.audience, resume_from=resume_from)
    else:
        if not args.topic or not args.audience:
            parser.error("--topic and --audience are required (unless using --resume)")
        resume_from = (args.step - 1) if args.step is not None else -1
        run_pipeline(args.topic, args.audience, resume_from=resume_from)


if __name__ == "__main__":
    main()

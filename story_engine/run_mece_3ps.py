#!/usr/bin/env python3
"""
Run Step 0 (improved prompt) + Step 0b (MECE audit) for all 3 problem statements.

Usage:
    python run_mece_3ps.py
    python run_mece_3ps.py --ps 1        # run only PS1
    python run_mece_3ps.py --ps 2 --ps 3 # run PS2 and PS3
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

from prompts import (
    MECE_AUDIT_SYSTEM,
    MECE_AUDIT_USER,
    MECE_MERGE_SYSTEM,
    MECE_MERGE_USER,
    PROBLEM_FRAMING_SYSTEM,
    PROBLEM_FRAMING_USER,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384
ROOT = Path(__file__).parent
OUTPUTS = ROOT.parent / "outputs" / "mece_3ps"

PROBLEM_STATEMENTS = {
    1: {
        "label": "PS1: High-NCI Private (RIL Jamnagar, Nayara Vadinar)",
        "topic": (
            "Iran-Israel Hormuz crisis: Strait mined, Indian basket at $156/bbl, "
            "MRPL shut down, Russia sanctions waiver expiring April 3. "
            "Focus: Reliance Industries (Jamnagar DTA + SEZ, 1.4 mbpd) and "
            "Nayara Energy (Vadinar, 400 kbpd). These are high-complexity, "
            "private-sector refiners with export optionality and integrated "
            "petrochemical capacity."
        ),
        "audience": (
            "RIL and Nayara C-suite (CEO, CFO, Head of Refining, Head of Supply). "
            "These executives can make rapid commercial decisions without government "
            "approval. They have balance-sheet strength, export flexibility, and "
            "petrochemical integration. Their strategic question is how to CAPITALIZE "
            "on the crisis, not just survive it."
        ),
    },
    2: {
        "label": "PS2: High-NCI PSU (IOCL Paradip/Panipat/Gujarat, HMEL Bathinda)",
        "topic": (
            "Iran-Israel Hormuz crisis: Strait mined, Indian basket at $156/bbl, "
            "MRPL shut down, Russia sanctions waiver expiring April 3. "
            "Focus: Indian Oil (Paradip 300 kbpd, Panipat 300 kbpd, Gujarat 274 kbpd) "
            "and HMEL Bathinda (180 kbpd). These are high-complexity PSU refiners "
            "with frozen retail prices, ESMA LPG mandates, and government oversight. "
            "They cannot freely raise prices or optimize exports."
        ),
        "audience": (
            "IOCL and HMEL C-suite plus MoPNG oversight. These executives operate "
            "under government price controls, directed supply obligations, and "
            "ESMA mandates. They face negative margins at $156 basket with frozen "
            "retail prices. Their strategic question is how to SUSTAIN OPERATIONS "
            "without hemorrhaging cash while meeting government mandates."
        ),
    },
    3: {
        "label": "PS3: Low-NCI PSU (HPCL Mumbai, BPCL Mumbai/Kochi, MRPL, CPCL, Bina, NRL)",
        "topic": (
            "Iran-Israel Hormuz crisis: Strait mined, Indian basket at $156/bbl, "
            "MRPL already shut down, Russia sanctions waiver expiring April 3. "
            "Focus: Low-complexity PSU refiners — HPCL Mumbai (150 kbpd), "
            "BPCL Mumbai (120 kbpd), BPCL Kochi (310 kbpd), MRPL Mangalore "
            "(300 kbpd, already shut), CPCL Manali (210 kbpd), IOCL Bina (156 kbpd), "
            "NRL Numaligarh (60 kbpd). These refiners have limited crude diet "
            "flexibility, low Nelson complexity, no export optionality, and face "
            "shutdown risk."
        ),
        "audience": (
            "Leadership of low-complexity PSU refiners plus MoPNG/PPAC crisis cell. "
            "These refiners have the least flexibility — limited crude diet options, "
            "no significant export revenue, and regional supply obligations. MRPL has "
            "already shut. Their strategic question is how to AVOID SHUTDOWN and "
            "maintain minimum regional fuel supply."
        ),
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    """Send a single-turn message to Claude and return the text response."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    for block in response.content:
        if block.type == "text":
            # Check if response was truncated
            if response.stop_reason == "max_tokens":
                print(f"  WARNING: Response truncated at {MAX_TOKENS} tokens. Retrying with extended limit...")
                response2 = client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    messages=[
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": block.text},
                        {"role": "user", "content": "Your response was truncated. Continue EXACTLY where you left off. Output ONLY the remaining JSON — no preamble."},
                    ],
                )
                continuation = ""
                for block2 in response2.content:
                    if block2.type == "text":
                        continuation = block2.text
                        break
                return block.text + continuation
            return block.text
    raise RuntimeError("Claude returned no text content")


def parse_json_response(text: str) -> dict:
    """Extract JSON from a Claude response, stripping markdown fences if present."""
    cleaned = text.strip()
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


# ---------------------------------------------------------------------------
# Step 0: Problem Framing (improved prompt)
# ---------------------------------------------------------------------------


def step0_frame(client: anthropic.Anthropic, topic: str, audience: str) -> dict:
    """Generate MECE decomposition with the improved exhaustiveness prompt."""
    user_prompt = PROBLEM_FRAMING_USER.format(topic=topic, audience=audience)
    raw = call_claude(client, PROBLEM_FRAMING_SYSTEM, user_prompt)
    return parse_json_response(raw)


# ---------------------------------------------------------------------------
# Step 0b: MECE Audit
# ---------------------------------------------------------------------------


def step0b_audit(client: anthropic.Anthropic, framing: dict, audience: str) -> dict:
    """Run adversarial audit on the MECE decomposition."""
    audit_prompt = MECE_AUDIT_USER.format(
        smart_statement=framing.get("smart_statement", ""),
        audience=audience,
        decomposition_json=json.dumps(framing, indent=2),
    )
    raw = call_claude(client, MECE_AUDIT_SYSTEM, audit_prompt)
    return parse_json_response(raw)


# ---------------------------------------------------------------------------
# Step 0c: Merge
# ---------------------------------------------------------------------------


def step0c_merge(client: anthropic.Anthropic, framing: dict, audit: dict) -> dict:
    """Merge audit findings into original decomposition."""
    merge_prompt = MECE_MERGE_USER.format(
        original_json=json.dumps(framing, indent=2),
        audit_json=json.dumps(audit, indent=2),
    )
    raw = call_claude(client, MECE_MERGE_SYSTEM, merge_prompt)
    return parse_json_response(raw)


# ---------------------------------------------------------------------------
# Pretty print
# ---------------------------------------------------------------------------


def print_decomposition(data: dict, label: str) -> None:
    """Print a MECE decomposition nicely."""
    print(f"\n  {label}")
    print(f"  PS: {data.get('smart_statement', '?')[:100]}")
    if data.get("decision_sensitivity"):
        print(f"  Break point: {data['decision_sensitivity'][:100]}")
    total_q = 0
    for sec in data.get("sections", []):
        qs = sec.get("questions", [])
        total_q += len(qs)
        print(f"\n  Bucket {sec['section_id']}: {sec['title']} ({len(qs)} questions)")
        for q in qs:
            print(f"    [{q['id']}] {q['question'][:90]}")
    print(f"\n  TOTAL: {len(data.get('sections', []))} buckets, {total_q} questions")


def print_audit_summary(audit: dict) -> None:
    """Print audit results summary."""
    verdict = audit.get("overall_verdict", "unknown")
    total_added = audit.get("total_questions_added", 0)
    missing_buckets = audit.get("missing_buckets", [])
    duplicates = audit.get("duplicate_flags", [])

    print(f"\n  Audit verdict: {verdict}")
    print(f"  New questions found: {total_added}")
    print(f"  Missing buckets: {len(missing_buckets)}")
    print(f"  Duplicates flagged: {len(duplicates)}")

    for ba in audit.get("bucket_audits", []):
        gaps = [d for d in ba.get("dimensions_found", []) if d.get("status") == "missing"]
        if gaps:
            print(f"\n  Bucket {ba['section_id']}: {ba.get('title', '?')} — {len(gaps)} gaps")
            for g in gaps:
                nq = g.get("new_question", {})
                if nq:
                    print(f"    + [{nq.get('id', '?')}] {nq.get('question', '?')[:80]}")

    for mb in missing_buckets:
        print(f"\n  NEW BUCKET: {mb.get('title', '?')}")
        for q in mb.get("questions", []):
            print(f"    + [{q['id']}] {q['question'][:80]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_ps(client: anthropic.Anthropic, ps_id: int) -> None:
    """Run framing + audit + merge for one problem statement."""
    ps = PROBLEM_STATEMENTS[ps_id]
    ps_dir = OUTPUTS / f"ps{ps_id}"
    ps_dir.mkdir(parents=True, exist_ok=True)

    print_divider(f"PROBLEM STATEMENT {ps_id}: {ps['label']}")

    # Step 0: Frame
    print("  [Step 0] Generating MECE decomposition...")
    t0 = time.time()
    framing = step0_frame(client, ps["topic"], ps["audience"])
    t1 = time.time()
    print(f"  Done in {t1 - t0:.1f}s")

    (ps_dir / "1_framing.json").write_text(json.dumps(framing, indent=2), encoding="utf-8")
    print_decomposition(framing, "INITIAL DECOMPOSITION")

    # Step 0b: Audit
    print(f"\n  [Step 0b] Running adversarial MECE audit...")
    t2 = time.time()
    audit = step0b_audit(client, framing, ps["audience"])
    t3 = time.time()
    print(f"  Done in {t3 - t2:.1f}s")

    (ps_dir / "2_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print_audit_summary(audit)

    # Step 0c: Merge
    verdict = audit.get("overall_verdict", "unknown")
    total_added = audit.get("total_questions_added", 0)

    if verdict == "pass" and total_added == 0:
        print("\n  Audit passed — no merge needed.")
        final = framing
    else:
        print(f"\n  [Step 0c] Merging {total_added} new questions...")
        t4 = time.time()
        final = step0c_merge(client, framing, audit)
        t5 = time.time()
        print(f"  Done in {t5 - t4:.1f}s")

    (ps_dir / "3_final.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    print_decomposition(final, "FINAL AUDITED DECOMPOSITION")

    # Summary comparison
    orig_q = sum(len(s.get("questions", [])) for s in framing.get("sections", []))
    final_q = sum(len(s.get("questions", [])) for s in final.get("sections", []))
    orig_b = len(framing.get("sections", []))
    final_b = len(final.get("sections", []))
    print(f"\n  SUMMARY: {orig_b} buckets/{orig_q} questions -> {final_b} buckets/{final_q} questions")


def main():
    parser = argparse.ArgumentParser(description="Run MECE framing + audit for 3 problem statements")
    parser.add_argument("--ps", type=int, action="append", choices=[1, 2, 3],
                        help="Which PS to run (can repeat). Default: all 3.")
    args = parser.parse_args()

    load_dotenv()
    # Try multiple .env locations
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        for env_path in [
            ROOT.parent / ".env",
            ROOT.parent.parent / "iran-crisis-v2" / ".env",
            ROOT.parent.parent / "iran-crisis" / ".env",
            ROOT.parent.parent / "oil-dashboard" / ".env",
        ]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            if api_key:
                break

    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    ps_ids = args.ps or [1, 2, 3]

    print_divider("MECE FRAMING + AUDIT — 3 PROBLEM STATEMENTS")
    print(f"  Model: {MODEL}")
    print(f"  Running: PS{', PS'.join(str(i) for i in ps_ids)}")
    print(f"  Output: {OUTPUTS.resolve()}")

    t_start = time.time()
    for ps_id in ps_ids:
        run_ps(client, ps_id)
    t_end = time.time()

    print_divider("ALL DONE")
    print(f"  Total time: {t_end - t_start:.0f}s")
    print(f"  Output dir: {OUTPUTS.resolve()}")

    # Write combined summary
    summary_lines = []
    for ps_id in ps_ids:
        final_path = OUTPUTS / f"ps{ps_id}" / "3_final.json"
        if final_path.exists():
            data = json.loads(final_path.read_text(encoding="utf-8"))
            total_q = sum(len(s.get("questions", [])) for s in data.get("sections", []))
            summary_lines.append(
                f"PS{ps_id}: {data.get('smart_statement', '?')[:80]}... "
                f"— {len(data.get('sections', []))} buckets, {total_q} questions"
            )

    summary = "\n".join(summary_lines)
    (OUTPUTS / "summary.txt").write_text(summary, encoding="utf-8")
    print(f"\n{summary}")


if __name__ == "__main__":
    main()

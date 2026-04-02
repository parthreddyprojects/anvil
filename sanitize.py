#!/usr/bin/env python3
"""
Output Sanitizer
================
Replaces company names, people names, and sensitive terms across all output files in a run folder.

Usage:
    python sanitize.py outputs/runs/openai_commoditization --replace "OpenAI=OpenBrain" "Sam Altman=CEO"
    python sanitize.py outputs/runs/indian_psu_hormuz --replace "Indian Oil=IndianCo" "BPCL=PetroCo"
    python sanitize.py outputs/runs/mbb_palantir_disruption --replace "McKinsey=FirmA" "BCG=FirmB" "Bain=FirmC"
    python sanitize.py --list outputs/runs/openai_commoditization    # Show all proper nouns found
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def find_proper_nouns(text):
    """Find likely company/person names in text."""
    # Match capitalized multi-word names
    names = set()
    # Company-like patterns
    for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text):
        name = m.group(1)
        if len(name) > 3 and name not in {"The", "This", "That", "What", "When", "Where", "How", "Why", "For", "And", "But", "Not", "All", "Our", "Its"}:
            names.add(name)
    # ALL-CAPS acronyms
    for m in re.finditer(r'\b([A-Z]{2,6})\b', text):
        acronym = m.group(1)
        if acronym not in {"MECE", "JSON", "HTML", "CSS", "API", "LLM", "GDP", "USD", "INR", "CEO", "CFO", "COO", "CTO", "CPO", "CRO", "IPO", "M&A", "R&D", "AI", "ML", "NRR", "ARR", "GRM", "FY", "Q1", "Q2", "Q3", "Q4", "YoY", "CAGR", "EBITDA", "GAAP", "EV", "PE", "PS"}:
            names.add(acronym)
    return sorted(names)


def sanitize_file(filepath, replacements):
    """Apply replacements to a single file."""
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except Exception:
        return False

    original = text
    for old, new in replacements.items():
        text = text.replace(old, new)
        # Also handle case variations
        text = text.replace(old.lower(), new.lower())
        text = text.replace(old.upper(), new.upper())

    if text != original:
        Path(filepath).write_text(text, encoding="utf-8")
        return True
    return False


def sanitize_run(run_dir, replacements):
    """Sanitize all files in a run directory."""
    run_dir = Path(run_dir)
    if not run_dir.exists():
        print(f"Error: {run_dir} does not exist")
        return

    # File types to sanitize
    extensions = {".html", ".md", ".json", ".txt"}
    files = []
    for ext in extensions:
        files.extend(run_dir.rglob(f"*{ext}"))

    changed = 0
    for f in sorted(files):
        if sanitize_file(f, replacements):
            print(f"  Sanitized: {f.relative_to(run_dir)}")
            changed += 1

    print(f"\n  {changed}/{len(files)} files modified")
    print(f"  Replacements applied: {len(replacements)}")
    for old, new in replacements.items():
        print(f"    {old} -> {new}")


def auto_suggest_replacements(run_dir):
    """Use Haiku to suggest sanitized names for all entities found."""
    run_dir = Path(run_dir)
    all_text = ""
    for f in list(run_dir.rglob("*.md"))[:5]:
        all_text += f.read_text(encoding="utf-8", errors="ignore")[:3000] + "\n"

    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            for line in open(Path(__file__).parent / ".env").readlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
        client = anthropic.Anthropic(api_key=key)
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system="You are a legal sanitizer. Find all company names, person names, and sensitive entity names in the text. For each, suggest a plausible fictional replacement that preserves the industry/role context. Return JSON: {\"replacements\": [{\"original\": \"OpenAI\", \"replacement\": \"OpenBrain\", \"type\": \"company\"}, {\"original\": \"Sam Altman\", \"replacement\": \"the CEO\", \"type\": \"person\"}]}",
            messages=[{"role": "user", "content": f"Find and suggest replacements for all proper nouns (companies, people, specific products) in this text:\n\n{all_text[:8000]}"}],
        )
        result = json.loads(r.content[0].text.strip().replace("```json", "").replace("```", ""))
        return result.get("replacements", [])
    except Exception as e:
        print(f"  Auto-suggest failed: {e}")
        return []


def list_names(run_dir, auto=False):
    """Scan all files and list proper nouns found."""
    run_dir = Path(run_dir)

    if auto:
        print(f"\n  Auto-suggesting replacements using AI...")
        suggestions = auto_suggest_replacements(run_dir)
        if suggestions:
            print(f"\n  Suggested replacements:")
            print(f"  {'Original':<30} {'Replacement':<30} {'Type':<10}")
            print(f"  {'-'*30} {'-'*30} {'-'*10}")
            replace_args = []
            for s in suggestions:
                print(f"  {s['original']:<30} {s['replacement']:<30} {s.get('type', '?'):<10}")
                replace_args.append(f'"{s["original"]}={s["replacement"]}"')

            print(f"\n  To apply these, run:")
            print(f"  python sanitize.py {run_dir} --replace {' '.join(replace_args)}")
            print(f"\n  Or apply automatically:")
            print(f"  python sanitize.py {run_dir} --auto-apply")
        return

    all_names = {}
    for f in run_dir.rglob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for name in find_proper_nouns(text):
            all_names[name] = all_names.get(name, 0) + 1

    for f in run_dir.rglob("*.html"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r'<[^>]+>', ' ', text)
        for name in find_proper_nouns(text):
            all_names[name] = all_names.get(name, 0) + 1

    sorted_names = sorted(all_names.items(), key=lambda x: -x[1])

    print(f"\n  Proper nouns found in {run_dir.name}:")
    print(f"  {'Name':<40} {'Count':>5}")
    print(f"  {'-'*40} {'-'*5}")
    for name, count in sorted_names[:50]:
        print(f"  {name:<40} {count:>5}")

    print(f"\n  Total unique names: {len(sorted_names)}")
    print(f"\n  For AI-suggested replacements, run:")
    print(f"  python sanitize.py {run_dir} --auto")
    print(f"\n  Or manually:")
    print(f'  python sanitize.py {run_dir} --replace "CompanyName=Alias"')


def main():
    parser = argparse.ArgumentParser(description="Sanitize output files")
    parser.add_argument("run_dir", help="Path to run directory")
    parser.add_argument("--replace", nargs="+", help="Replacements as 'old=new' pairs")
    parser.add_argument("--list", action="store_true", help="List proper nouns found (no changes)")
    parser.add_argument("--auto", action="store_true", help="AI suggests replacement names (no changes)")
    parser.add_argument("--auto-apply", action="store_true", help="AI suggests AND applies replacements")
    args = parser.parse_args()

    if args.list:
        list_names(args.run_dir)
        return

    if args.auto:
        list_names(args.run_dir, auto=True)
        return

    if args.auto_apply:
        print(f"\n  Auto-sanitizing {args.run_dir}...")
        suggestions = auto_suggest_replacements(args.run_dir)
        if suggestions:
            replacements = {s["original"]: s["replacement"] for s in suggestions}
            sanitize_run(args.run_dir, replacements)
        else:
            print("  No suggestions generated.")
        return

    if not args.replace:
        print("Error: provide --replace pairs or use --list to scan")
        print("Example: python sanitize.py outputs/runs/openai --replace \"OpenAI=OpenBrain\"")
        return

    replacements = {}
    for r in args.replace:
        if "=" not in r:
            print(f"Error: replacement must be 'old=new', got: {r}")
            return
        old, new = r.split("=", 1)
        replacements[old] = new

    sanitize_run(args.run_dir, replacements)


if __name__ == "__main__":
    main()

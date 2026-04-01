"""
Design Agent — Produces COMPLETE HTML for each card.

Takes a card_spec.json (content-level, from story engine) and produces a
card_html.json with the actual HTML for each card. No intermediate JSON
configs. No template interpretation. The builder just wraps cards in a shell.

Usage:
    python agent.py --spec card_spec.json --output card_html.json
    python agent.py --spec card_spec.json --output card_html.json --model claude-sonnet-4-6
    python agent.py --spec card_spec.json --output card_html.json --dry-run
    python agent.py --spec card_spec.json --output card_html.json --card c7
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic

# Add this directory to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from design_prompts import build_design_prompt


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------

def extract_html(raw_text: str) -> str:
    """
    Extract the HTML card div from Claude's response.
    Strips markdown fences, leading/trailing whitespace, and any
    non-HTML commentary.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (```html or ```)
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
        # Remove closing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Find the outermost <div class="card" ...> ... </div>
    start = text.find('<div class="card"')
    if start == -1:
        # Try single quotes
        start = text.find("<div class='card'")
    if start == -1:
        # Last resort: try any div start
        start = text.find("<div")

    if start > 0:
        text = text[start:]

    # Find the matching closing </div> for the outermost div
    # Simple approach: find the last </div>
    last_close = text.rfind("</div>")
    if last_close != -1:
        text = text[:last_close + 6]

    return text.strip()


def validate_card_html(html: str, card_id: str) -> list[str]:
    """
    Quick validation checks on the generated HTML.
    Returns a list of warning strings (empty = all good).
    """
    warnings = []

    if f'id="{card_id}"' not in html and f"id='{card_id}'" not in html:
        warnings.append(f"Missing id=\"{card_id}\"")

    if 'class="card"' not in html and "class='card'" not in html:
        warnings.append("Missing class=\"card\"")

    if "card-inner" not in html:
        warnings.append("Missing card-inner wrapper")

    # Check for unclosed tags (very basic)
    open_divs = html.count("<div")
    close_divs = html.count("</div>")
    if open_divs != close_divs:
        warnings.append(f"Div count mismatch: {open_divs} opens vs {close_divs} closes")

    return warnings


# ---------------------------------------------------------------------------
# Core design function
# ---------------------------------------------------------------------------

def design_card(
    client: anthropic.Anthropic,
    card: dict,
    model: str = DEFAULT_MODEL,
    verbose: bool = False,
) -> dict:
    """
    Take a content-level card spec and return a dict with card_id and html.

    Calls Claude with a design prompt specific to the card type, extracts
    the HTML response, validates it, and returns the result.

    Parameters
    ----------
    client : anthropic.Anthropic
        Initialized Anthropic client.
    card : dict
        A single card from the story engine's card_spec.json.
    model : str
        Claude model to use.
    verbose : bool
        Print the raw response for debugging.

    Returns
    -------
    dict
        {"card_id": "c1", "card_type": "hero", "html": "<div class='card'..."}
    """
    card_type = card.get("card_type", "unknown")
    card_id = card.get("card_id", "c0")

    system_prompt, user_prompt = build_design_prompt(card, card_type)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw_text = response.content[0].text.strip()

            if verbose:
                print(f"\n    [DEBUG] Raw response for {card_id} ({len(raw_text)} chars):")
                print(f"    {raw_text[:300]}...")

            # Extract just the HTML
            html = extract_html(raw_text)

            # Validate
            warnings = validate_card_html(html, card_id)
            if warnings:
                for w in warnings:
                    print(f"    [WARN] {card_id}: {w}")

            return {
                "card_id": card_id,
                "card_type": card_type,
                "html": html,
            }

        except anthropic.APIError as e:
            if attempt < MAX_RETRIES:
                print(f"    [RETRY {attempt}/{MAX_RETRIES}] API error for {card_id}: {e}")
                time.sleep(RETRY_DELAY * attempt)
            else:
                print(f"    [ERROR] API call failed for {card_id} after {MAX_RETRIES} attempts: {e}")
                return {
                    "card_id": card_id,
                    "card_type": card_type,
                    "html": f'<div class="card" id="{card_id}"><div class="card-inner"><p class="label red">Error generating card</p><h3 class="card-title">{card_id} — {card_type}</h3><p class="card-sub">API error: {str(e)[:100]}</p></div></div>',
                    "_error": str(e),
                }

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"    [RETRY {attempt}/{MAX_RETRIES}] Error for {card_id}: {e}")
                time.sleep(RETRY_DELAY * attempt)
            else:
                print(f"    [ERROR] Failed for {card_id} after {MAX_RETRIES} attempts: {e}")
                return {
                    "card_id": card_id,
                    "card_type": card_type,
                    "html": f'<div class="card" id="{card_id}"><div class="card-inner"><p class="label red">Error generating card</p><h3 class="card-title">{card_id} — {card_type}</h3><p class="card-sub">Error: {str(e)[:100]}</p></div></div>',
                    "_error": str(e),
                }


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_spec(
    spec: dict,
    client: anthropic.Anthropic,
    model: str = DEFAULT_MODEL,
    verbose: bool = False,
) -> dict:
    """
    Process an entire card_spec.json, generating HTML for each card.

    Returns
    -------
    dict
        {"cards": [{"card_id": "c1", "card_type": "hero", "html": "..."}], "_design_agent": {...}}
    """
    cards = spec.get("cards", [])
    total = len(cards)
    results = []
    errors = 0

    print(f"  Processing {total} cards with {model}...\n")

    for i, card in enumerate(cards):
        card_id = card.get("card_id", f"c{i + 1}")
        card_type = card.get("card_type", "unknown")
        title = card.get("title", "")[:50]

        print(f"  [{i + 1}/{total}] {card_id} ({card_type}): {title}")

        start = time.time()
        result = design_card(client, card, model=model, verbose=verbose)
        elapsed = time.time() - start

        has_error = "_error" in result
        status = "ERROR" if has_error else f"OK ({len(result['html']):,} chars)"
        if has_error:
            errors += 1

        print(f"           {status} ({elapsed:.1f}s)")
        results.append(result)

    output = {
        "cards": results,
        "_design_agent": {
            "model": model,
            "cards_processed": total,
            "errors": errors,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }

    return output


# ---------------------------------------------------------------------------
# Dry-run mode (no API calls)
# ---------------------------------------------------------------------------

def dry_run_spec(spec: dict) -> dict:
    """
    Process the spec without calling Claude — returns placeholder HTML cards.
    Useful for testing the pipeline end-to-end.
    """
    cards = spec.get("cards", [])
    results = []

    for i, card in enumerate(cards):
        card_type = card.get("card_type", "unknown")
        card_id = card.get("card_id", f"c{i + 1}")
        title = card.get("title", "Untitled")
        print(f"  [DRY-RUN] {card_id} ({card_type}): {title[:50]}")

        # Produce a skeleton HTML card
        label_class = "red" if card_type in ("hero", "checklist") else ""
        html = f'''<div class="card" id="{card_id}">
<div class="card-inner">
<p class="label {label_class}" style="margin-bottom:12px">{card_type.upper().replace("_", " ")}</p>
<h3 class="card-title">{title}</h3>
<p class="card-sub">Dry-run placeholder — run without --dry-run to generate real HTML via Claude.</p>
<div class="insight">Card type: {card_type} | Card ID: {card_id}</div>
</div>
</div>'''

        results.append({
            "card_id": card_id,
            "card_type": card_type,
            "html": html,
            "_dry_run": True,
        })

    return {
        "cards": results,
        "_design_agent": {
            "model": "dry-run",
            "cards_processed": len(cards),
            "errors": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Design Agent — card_spec.json -> card_html.json (complete HTML per card)"
    )
    parser.add_argument(
        "--spec", "-s",
        required=True,
        help="Path to card_spec.json from the Story Engine",
    )
    parser.add_argument(
        "--output", "-o",
        default="card_html.json",
        help="Output path for the card HTML JSON (default: card_html.json)",
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API calls; produce placeholder HTML for testing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print raw Claude responses for debugging",
    )
    parser.add_argument(
        "--card",
        type=str,
        default=None,
        help="Process only this card_id (useful for iterating on a single card)",
    )

    args = parser.parse_args()

    # ── Validate input ──
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: Spec file not found: {spec_path}")
        sys.exit(1)

    # ── Load spec ──
    print()
    print("  DESIGN AGENT (HTML mode)")
    print(f"  {'=' * 50}")
    print(f"  Input:  {spec_path}")
    print(f"  Output: {args.output}")
    print(f"  Model:  {args.model}")
    if args.dry_run:
        print("  Mode:   DRY RUN (no API calls)")
    if args.card:
        print(f"  Filter: card_id = {args.card}")
    print()

    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    # ── Filter to single card if requested ──
    if args.card:
        original_cards = spec.get("cards", [])
        filtered = [c for c in original_cards if c.get("card_id") == args.card]
        if not filtered:
            available = [c.get("card_id", "?") for c in original_cards]
            print(f"  ERROR: card_id '{args.card}' not found.")
            print(f"  Available: {', '.join(available)}")
            sys.exit(1)
        spec["cards"] = filtered

    # ── Process ──
    if args.dry_run:
        output = dry_run_spec(spec)
    else:
        # Initialize Anthropic client (reads ANTHROPIC_API_KEY from env)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("  ERROR: ANTHROPIC_API_KEY environment variable not set.")
            print("  Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
            sys.exit(1)

        client = anthropic.Anthropic(api_key=api_key)
        output = process_spec(spec, client, model=args.model, verbose=args.verbose)

    # ── Write output ──
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # ── Summary ──
    meta = output.get("_design_agent", {})
    total = meta.get("cards_processed", 0)
    errors = meta.get("errors", 0)

    total_html_chars = sum(len(c.get("html", "")) for c in output.get("cards", []))

    print()
    print(f"  {'=' * 50}")
    print(f"  COMPLETE: {total} cards processed, {errors} errors")
    print(f"  Total HTML: {total_html_chars:,} characters")
    print(f"  Output:   {output_path}")
    print()

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

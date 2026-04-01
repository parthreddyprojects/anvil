"""
Presentation Engine — CLI entry point.

Takes a card_html.json (from the Design Agent) and produces a complete
HTML briefing by concatenating all card HTML blocks into a shell with
CDN links, inline CSS, progress bar, and scroll script.

Usage:
  python engine.py --spec card_html.json --output briefing.html
  python engine.py --spec card_html.json --output briefing.html --critique
  python engine.py --spec card_html.json --output briefing.html --critique --rounds 3
"""

import argparse
import os
import sys

# Add parent to path so we can import from this package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from builder import build_briefing
from critique import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Presentation Engine — card_html.json -> HTML briefing"
    )
    parser.add_argument(
        "--spec", "-s",
        required=True,
        help="Path to card_html.json from the Design Agent"
    )
    parser.add_argument(
        "--output", "-o",
        default="briefing.html",
        help="Output HTML file path (default: briefing.html)"
    )
    parser.add_argument(
        "--title", "-t",
        default=None,
        help="Briefing title (default: extracted from hero card)"
    )
    parser.add_argument(
        "--critique",
        action="store_true",
        help="Run the critique pipeline after building"
    )
    parser.add_argument(
        "--rounds", "-r",
        type=int,
        default=3,
        help="Number of Gate 1 critique rounds (default: 3)"
    )
    parser.add_argument(
        "--gate", "-g",
        choices=["1", "2", "all"],
        default="all",
        help="Which critique gate to run (default: all)"
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Auto-apply critique fixes via Claude Sonnet API"
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.spec):
        print(f"ERROR: Spec file not found: {args.spec}")
        sys.exit(1)

    # ── Step 1: Build ──
    print(f"\n  PRESENTATION ENGINE")
    print(f"  {'='*40}")
    print(f"  Spec:   {args.spec}")
    print(f"  Output: {args.output}")
    print()

    try:
        output_path = build_briefing(args.spec, args.output, title=args.title)
    except Exception as e:
        print(f"ERROR: Build failed: {e}")
        sys.exit(1)

    # ── Step 2: Critique (optional) ──
    if args.critique:
        print(f"\n  {'='*40}")
        print(f"  CRITIQUE PIPELINE")
        print(f"  {'='*40}")
        run_pipeline(
            html_path=output_path,
            gate=args.gate,
            rounds=args.rounds,
            auto_fix=args.auto_fix
        )

    print(f"\n  Done. Output: {output_path}")


if __name__ == "__main__":
    main()

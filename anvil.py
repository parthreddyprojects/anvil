#!/usr/bin/env python3
"""
ANVIL — Strategic Problem-Solving Engine
=========================================
Claude Code interface. Two modes:

  Autopilot:  anvil.py run --topic "..." --audience "..." [--inputs <folder>]
  Guided:     anvil.py guided --topic "..." --audience "..."

Step-by-step (for Claude orchestration):
  anvil.py step <N> --run <dir>           Run a single step
  anvil.py status --run <dir>             Show current state
  anvil.py inject --run <dir> --folder <path>   Add research files
  anvil.py show <what> --run <dir>        Show outputs (mece, research, synthesis, hypotheses, document)
  anvil.py revise <step> --run <dir> --feedback "..."   Re-run step with feedback
  anvil.py open --run <dir>               Open final output in browser
"""

import argparse
import json
import os
import sys
import io
import shutil
import time
import webbrowser
from pathlib import Path
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent
OUTPUTS = ROOT / "outputs" / "runs"

# ── ANVIL COLOR SYSTEM ──
# From logo spec: amber #F5A623, dim #9B6A14, bright #FFD080, white #EFEFEF, bg #0C0C0C
A = "\033[38;2;245;166;35m"       # amber (primary)
AD = "\033[38;2;155;106;20m"      # dim amber (borders, secondary)
AB = "\033[38;2;255;208;128m"     # bright amber (highlights)
AW = "\033[38;2;239;239;239m"     # white (wordmark, emphasis)
AF = "\033[38;2;245;166;35m\033[1m"  # forge (bold amber)
DK = "\033[38;2;58;58;58m"        # dark grey (structural, box chars)
DM = "\033[2m"                     # dim
B = "\033[1m"                      # bold
R = "\033[0m"                      # reset
RED = "\033[38;2;239;68;68m"
GRN = "\033[38;2;34;197;94m"
BLU = "\033[38;2;96;165;250m"
WARN = "\033[38;2;251;191;36m"     # warning amber-yellow

# All steps use amber — no multicolor
STEP_COLORS = {i: A for i in range(8)}

ANVIL_BANNER = f"""
  {A}╔══════════════════════════════════════╗
  ║  ▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄    ║
  ║  █   A N V I L                █    ║
  ║  ▀▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▀    ║
  ║       ╲▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄╱             ║
  ║        ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀              ║
  ║  strategic problem engine  v0.1      ║
  ╚══════════════════════════════════════╝{R}
"""

ANVIL_MINI = f"  {DK}[{R} {A}▄▀▀▄ █▄▄█ ╲▄▄╱{R} {DK}]{R} {AW}\033[1mANVIL{R}"


def _flow_diagram(state=None, active_step=None):
    """Pipeline as ASCII flow. Single amber color throughout."""
    step = active_step if active_step is not None else (state.get("step", -1) if state else -1)
    done = state.get("done", []) if state else []

    labels = ["PROBLEM", "  MECE ", "RESRCH ", " W.DOC ", " SYNTH ", "  HYPO ", " FINAL ", "CHARTS "]

    def _n(i):
        if i == step:
            return f"▸{labels[i]}◂"
        elif i in done:
            return f" {labels[i]} "
        else:
            return f" {'·' * len(labels[i])} "

    top = f"  {_n(0)}───{_n(1)}───{_n(2)}───{_n(3)}───┐"
    mid = f"  {' ' * len(top.replace(chr(27), '').split('┐')[0])}│"
    bot = f"  {_n(7)}───{_n(6)}───{_n(5)}───{_n(4)}───┘"

    # Calculate mid padding manually
    mid = f"  {' ' * 63}│"

    print()
    print(f"  {A}{_n(0)}───{_n(1)}───{_n(2)}───{_n(3)}───┐{R}")
    print(f"  {A}{' ' * 63}│{R}")
    print(f"  {A}{_n(7)}───{_n(6)}───{_n(5)}───{_n(4)}───┘{R}")

    # ── Status panel below the flow ──
    if state:
        topic = state.get("topic", "")
        audience = state.get("audience", "")
        spend = state.get("total_spend", 0)
        created = state.get("created", "")

        # Step description
        step_desc = {
            -1: ("Ready", "Waiting for a problem statement."),
            0: ("Problem Statement", "Claude works with you to sharpen the core question — neutral framing, right scope, explicit decision-maker. This is the foundation."),
            1: ("MECE Decomposition", "Anvil scans 120+ snippets and 12+ articles, maps the full landscape, then breaks your problem into exhaustive research buckets."),
            2: ("Deep Research", "Web search per bucket — real sources, real articles, real data. Each bucket gets its own targeted investigation."),
            3: ("Working Document", "All research compiled into a structured working document — the raw material for synthesis."),
            4: ("Synthesis", "Extracting findings from research, detecting cross-cutting patterns, deriving inferences. What the data actually says."),
            5: ("Hypotheses", "Generating testable answers to your PS. Each hypothesis is stress-tested by a contrarian reviewer and scored for diagnosticity."),
            6: ("Final Document", "Writing the 3-5 page strategic brief. Headlines ARE the story — read them in sequence for the full narrative."),
            7: ("Appendix Charts", "Proof slides — data relationship drives chart type, design principles strip the noise. Each chart makes one point obvious in 3 seconds."),
            8: ("Complete", "All steps done. Open the output to review."),
        }
        step_name, step_what = step_desc.get(step, ("Unknown", ""))

        print(f"  {A}{'─' * 55}{R}")

        # Current phase
        print(f"  {A}▸ {step_name}{R}")
        if step_what:
            print(f"  {A}  {step_what}{R}")
        print()

        # PS + Audience (full, not truncated)
        if topic:
            print(f"  {A}PS: {topic}{R}")
        if audience:
            print(f"  {A}Audience: {audience}{R}")
        print()

        # Stats row — all amber
        stats_parts = []
        if created:
            stats_parts.append(created)

        landscape_path = Path(state.get("landscape_path", "")) if state.get("landscape_path") else None
        if landscape_path and landscape_path.exists():
            try:
                ld = json.load(open(landscape_path, encoding="utf-8"))
                stats_parts.append(f"{len(ld.get('snippets', []))} snippets")
                stats_parts.append(f"{len(ld.get('articles', []))} articles")
                stats_parts.append(f"{len(ld.get('events', []))} events")
            except Exception:
                pass

        mece_path = state.get("mece_path", "")
        if mece_path and Path(mece_path).exists():
            try:
                md = json.load(open(mece_path, encoding="utf-8"))
                n_buckets = len(md.get("sections", []))
                n_questions = sum(len(s.get("questions", [])) for s in md.get("sections", []))
                stats_parts.append(f"{n_buckets} buckets")
                stats_parts.append(f"{n_questions} questions")
            except Exception:
                pass

        if spend:
            stats_parts.append(f"${spend:.2f}")

        if stats_parts:
            print(f"  {A}{'  ·  '.join(stats_parts)}{R}")

        print(f"  {A}{'─' * 55}{R}")

    print()


def _flow_explainer():
    """Brief explainer of how the pipeline works — shown on first run."""
    print(f"""
  {AD}─────────────────────────────────────────────────────────{R}

  {AW}\033[1mHow Anvil works:{R}

  {A}1.{R} {AB}PROBLEM{R}     You describe what you're trying to solve.
  {AD}                Claude helps you sharpen it into a clean PS —{R}
  {AD}                neutral framing, right scope, explicit decision-maker.{R}

  {A}2.{R} {AB}MECE{R}        Anvil scans the web (120+ snippets, 12+ articles),
  {AD}                identifies the full landscape, then decomposes your{R}
  {AD}                problem into mutually exclusive, collectively exhaustive{R}
  {AD}                research buckets. Nothing gets missed.{R}

  {A}3.{R} {AB}RESEARCH{R}    Deep web research per bucket — real sources,
  {AD}                real articles, real data. Not LLM knowledge.{R}

  {A}4.{R} {AB}SYNTHESIS{R}   Findings → cross-cutting patterns → inferences.
  {AD}                What the data says, not what you expected.{R}

  {A}5.{R} {AB}HYPOTHESES{R}  Testable answers to your PS — each one
  {AD}                stress-tested by a contrarian reviewer.{R}

  {A}6.{R} {AB}DOCUMENT{R}    A 3-5 page strategic brief. Headlines ARE the story.
  {AD}                Read the titles in sequence = full narrative.{R}

  {A}7.{R} {AB}CHARTS{R}      Proof slides — data relationship drives chart type,
  {AD}                design principles strip everything but the story.{R}
  {AD}                Each chart makes one point obvious in 3 seconds.{R}

  {AD}─────────────────────────────────────────────────────────{R}
  {DK}  Autopilot: runs end-to-end, you watch & narrate{R}
  {DK}  Guided: Claude pauses at each step, you steer{R}
  {DK}  Either mode: inject data, revise, re-run anytime{R}
  {AD}─────────────────────────────────────────────────────────{R}
""")


# ── PS CRAFTING INSTRUCTIONS FOR CLAUDE ──
PS_CRAFTING_GUIDE = """
## How to Craft a Problem Statement with the User

You are an engagement manager in the first client meeting. Your job is to pull the REAL question out of the user — not accept whatever they first say.

### The Process:

1. **Listen** — Let them describe what's on their mind. Don't interrupt.

2. **Identify the core tension** — Every good PS has a tension: protect vs. grow, speed vs. quality, short-term vs. long-term. Find it.

3. **Challenge the framing** — Push back gently:
   - "You said 'protect' — do you mean protect, or do you mean optimize? Those are different problems with different answers."
   - "You mentioned 30 days — is that a real deadline or an assumption?"
   - "Who actually decides this? You said the board, but is the CEO the real decision-maker?"
   - "Is this about the company or about the industry? Your PS sounds company-specific but the question might be bigger."

4. **Check for one-sided framing** — If the PS only captures threats OR opportunities, push for both:
   - "This is framed defensively. What if the crisis is actually an opportunity for you? Should the PS be open to that?"
   - "You're asking how to capture upside — but what's the downside risk? Should the PS account for scenarios where this doesn't work?"

5. **Test with the 'so what'** — Ask: "If I gave you the perfect answer to this question, would it actually help you make a decision?" If not, the PS is wrong.

6. **Write it neutral** — The final PS should:
   - Use "optimize" or "position" not "protect" or "defend"
   - Name WHO, WHAT domain, WHAT timeframe
   - Be 1-2 sentences max
   - Leave room for the research to discover what matters
   - NOT prescribe the answer ("should they cut costs" prescribes cutting costs)

7. **Confirm explicitly** — Read it back: "Here's what I think you're really asking: [PS]. Does this capture it? Anything missing?"

8. **Don't move on until the user says yes.** The PS is the foundation. If it's wrong, everything downstream is wasted work.

### What you need from the user (minimum):
- **Who** is this for? (company, decision-maker, audience)
- **What** is the core question? (one sentence, broad)
- **What timeframe?** (and is it a real deadline or assumed?)
- **Any constraints?** (budget, regulatory, political, sacred cows)

### What you can infer (don't ask if obvious):
- Industry context (you know the industry)
- Competitor landscape (you can research this)
- Success criteria (derive from the question)
- Scope (derive from the timeframe and who)

### Red flags in a PS:
- Contains "should" — prescribes the answer type
- Contains "protect/defend/respond" — one-sided framing
- More than 2 sentences — too specific, you've answered before researching
- Names a specific solution — "should they acquire X" is not a PS, it's a hypothesis
- No timeframe — impossible to scope the research
- No decision-maker — who acts on this?
"""

STEP_NAMES = {
    0: "Problem Statement",
    1: "Issue Tree (MECE)",
    2: "Deep Research",
    3: "Working Document",
    4: "Synthesis",
    5: "Hypotheses",
    6: "Final Document",
    7: "Appendix Charts",
}


def _run_dir_from_topic(topic):
    """Generate a run directory name from the topic."""
    slug = topic[:50].lower()
    for ch in " /\\:*?\"<>|.,;!@#$%^&(){}[]'":
        slug = slug.replace(ch, "_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_")
    return OUTPUTS / slug


def _find_run(run_arg):
    """Find a run directory from partial name or full path."""
    if run_arg is None:
        # Find most recent
        runs = sorted(OUTPUTS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True) if OUTPUTS.exists() else []
        if runs:
            return runs[0]
        return None
    p = Path(run_arg)
    if p.exists():
        return p
    # Try as subdirectory of outputs/runs/
    p2 = OUTPUTS / run_arg
    if p2.exists():
        return p2
    # Partial match
    if OUTPUTS.exists():
        for d in OUTPUTS.iterdir():
            if run_arg.lower() in d.name.lower():
                return d
    return None


def _load_state(run_dir):
    sf = run_dir / "state.json"
    if sf.exists():
        return json.load(open(sf, encoding="utf-8"))
    return None


def _narrate(msg, style="info"):
    """Print with anvil styling."""
    prefix = {
        "info":  f"{A}  ▸ ",
        "step":  f"{AF}  ◆ ",
        "done":  f"{GRN}  ✓ ",
        "warn":  f"{RED}  ⚠ ",
        "data":  f"{AD}    ",
        "head":  f"\n  {AW}\033[1m",
        "dim":   f"{DK}    ",
        "forge": f"{AB}  ⚒ ",
    }
    p = prefix.get(style, f"{A}  ")
    print(f"{p}{msg}{R}")


def _progress_bar(state):
    """Show step progress with per-step colors."""
    step = state.get("step", 0)
    done = state.get("done", [])
    total = len(STEP_NAMES)
    completed = len(done)
    pct = int((completed / total) * 100) if total > 0 else 0

    # Progress fill
    bar_width = 36
    filled = int(bar_width * completed / total)
    bar = f"{A}{'█' * filled}{DK}{'░' * (bar_width - filled)}{R}"

    print(f"\n  {DK}┌{'─' * 46}┐{R}")
    print(f"  {DK}│{R}  {bar}  {AB}{pct}%{R}  {DK}│{R}")
    print(f"  {DK}├{'─' * 46}┤{R}")

    for n, name in STEP_NAMES.items():
        sc = STEP_COLORS.get(n, A)
        if n in done:
            icon = f"{GRN}✓{R}"
            label = f"{DK}{name}{R}"
        elif n == step:
            icon = f"{sc}▶{R}"
            label = f"{sc}\033[1m{name}{R}"
        else:
            icon = f"{DK}○{R}"
            label = f"{DK}{name}{R}"
        print(f"  {DK}│{R}  {icon}  {n}. {label}")

    print(f"  {DK}└{'─' * 46}┘{R}\n")


def cmd_status(args):
    """Show the current state of a run."""
    run_dir = _find_run(args.run)
    if not run_dir:
        _narrate("No run found. Start one with: anvil.py run --topic \"...\"", "warn")
        return

    state = _load_state(run_dir)
    if not state:
        _narrate(f"No state.json in {run_dir}", "warn")
        return

    print(ANVIL_BANNER)
    _flow_diagram(state)


def cmd_show(args):
    """Show a specific output from a run."""
    run_dir = _find_run(args.run)
    if not run_dir:
        _narrate("No run found.", "warn")
        return

    what = args.what
    file_map = {
        "mece": run_dir / "mece" / "decomposition.json",
        "tree": run_dir / "tree.html",
        "research": run_dir / "research" / "debrief.md",
        "working": run_dir / "working_doc" / "working_document.md",
        "synthesis": run_dir / "synthesis" / "synthesis.md",
        "hypotheses": run_dir / "hypotheses" / "hypotheses.json",
        "document": run_dir / "final_document.html",
        "appendix": run_dir / "appendix.html",
        "output": run_dir / "output.html",
        "landscape": run_dir / "landscape_scan" / "landscape_summary.md",
    }

    f = file_map.get(what)
    if not f or not f.exists():
        _narrate(f"'{what}' not found. Available: {', '.join(k for k, v in file_map.items() if v.exists())}", "warn")
        return

    if f.suffix == ".html":
        webbrowser.open(f"file:///{f.resolve()}")
        _narrate(f"Opened {what} in browser", "done")
    elif f.suffix == ".json":
        data = json.load(open(f, encoding="utf-8"))
        if what == "mece":
            _narrate("MECE DECOMPOSITION", "head")
            for s in data.get("sections", []):
                _narrate(f"{s['section_id']}. {s['title']}", "step")
                for q in s.get("questions", [])[:3]:
                    _narrate(f"  {q['id']}. {q['question'][:80]}", "data")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False)[:5000])
    else:
        content = f.read_text(encoding="utf-8")
        print(content[:8000])


def cmd_init(args):
    """Set up Anvil for Claude Code — installs slash command and CLAUDE.md."""
    print(ANVIL_BANNER)

    home = Path.home()
    anvil_root = Path(__file__).parent.resolve()

    # 1. Create ~/.claude/commands/ if needed
    global_cmd_dir = home / ".claude" / "commands"
    global_cmd_dir.mkdir(parents=True, exist_ok=True)

    # 2. Copy the /anvil slash command
    src_cmd = anvil_root / ".claude" / "commands" / "anvil.md"
    dst_cmd = global_cmd_dir / "anvil.md"

    if src_cmd.exists():
        # Update paths in the command file to point to this install location
        cmd_content = src_cmd.read_text(encoding="utf-8")
        cmd_content = cmd_content.replace(
            "C:\\Users\\Lenovo\\briefing-engine",
            str(anvil_root)
        )
        dst_cmd.write_text(cmd_content, encoding="utf-8")
        _narrate(f"Installed /anvil command -> {dst_cmd}", "done")
    else:
        _narrate("Command template not found — skipping slash command", "warn")

    # 3. Create project-level .claude/commands/ too
    project_cmd_dir = anvil_root / ".claude" / "commands"
    project_cmd_dir.mkdir(parents=True, exist_ok=True)

    # 4. Set up CLAUDE.md in the project if not present
    claude_md = anvil_root / "CLAUDE.md"
    if claude_md.exists():
        _narrate(f"CLAUDE.md already exists at {claude_md}", "done")
    else:
        _narrate("CLAUDE.md not found — you may need to create one", "warn")

    # 5. Check for API key
    env_file = anvil_root / ".env"
    if env_file.exists() and "ANTHROPIC_API_KEY" in env_file.read_text(encoding="utf-8"):
        _narrate("API key found in .env", "done")
    else:
        _narrate("No API key found. Set ANTHROPIC_API_KEY in .env or environment", "warn")
        print(f"\n  {A}  echo ANTHROPIC_API_KEY=sk-ant-... > {env_file}{R}\n")

    # 6. Create outputs directory
    (anvil_root / "outputs" / "runs").mkdir(parents=True, exist_ok=True)
    _narrate("Output directory ready", "done")

    # 7. Create telemetry directory
    telemetry_dir = home / ".anvil" / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    # Done
    print(f"""
  {AD}─────────────────────────────────────────────────────────{R}

  {GRN}Anvil is ready.{R}

  {AW}To use in Claude Code:{R}
  {A}  1. Open Claude Code in this directory{R}
  {A}  2. Type {AB}/anvil{R}
  {A}  3. Claude becomes your engagement manager{R}

  {AW}To run directly:{R}
  {A}  anvil run --topic "..." --audience "..."{R}
  {A}  anvil list{R}
  {A}  anvil status{R}
  {A}  anvil open{R}

  {AD}─────────────────────────────────────────────────────────{R}
""")


def cmd_run(args):
    """Run the full pipeline in autopilot mode."""
    print(ANVIL_BANNER)
    _flow_diagram(active_step=-1)  # all dark — nothing started yet
    _flow_explainer()
    _narrate("AUTOPILOT MODE", "head")
    _narrate(f"Topic: {args.topic[:100]}", "info")
    _narrate(f"Audience: {args.audience[:80]}", "info")

    if args.inputs:
        _narrate(f"Research inputs: {args.inputs}", "info")

    # Build the command
    cmd_parts = [
        sys.executable, str(ROOT / "pipeline.py"),
        "--topic", args.topic,
        "--audience", args.audience,
        "--autopilot",
    ]

    # Pipe empty stdin for the interactive prompts
    import subprocess
    proc = subprocess.Popen(
        cmd_parts,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    proc.stdin.write("\n\n\n")
    proc.stdin.close()

    # Stream output with anvil coloring — re-paint everything in our palette
    import re as _re
    _ansi_strip = lambda s: _re.sub(r'\033\[[^m]*m', '', s)

    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        clean = _ansi_strip(line).strip()
        if not clean:
            continue

        # Re-color based on content
        if "Landscape scan complete" in clean or "complete" in clean.lower() and "step" not in clean.lower():
            _narrate(clean, "done")
        elif "TIER 1" in clean or "TIER 2" in clean:
            _narrate(clean, "forge")
        elif "[LLM" in clean:
            # Extract the key info from LLM log lines
            if "spend:" in clean:
                spend_match = _re.search(r'spend: \$([0-9.]+)', clean)
                model_match = _re.search(r'model: (\S+)', clean)
                time_match = _re.search(r'(\d+\.\d+)s', clean)
                if spend_match:
                    parts = []
                    if model_match:
                        m = model_match.group(1).replace("claude-", "")
                        parts.append(f"{DK}{m}{R}")
                    if time_match:
                        parts.append(f"{AD}{time_match.group(1)}s{R}")
                    parts.append(f"{A}${spend_match.group(1)}{R}")
                    print(f"  {DK}    ⟡{R} {' · '.join(parts)}")
                    continue
            _narrate(clean[:80], "dim")
        elif any(k in clean for k in ["MECE", "Bucket", "bucket", "Core buckets", "Auxiliary"]):
            _narrate(clean, "step")
        elif "Error" in clean or "error" in clean or "failed" in clean.lower():
            _narrate(clean, "warn")
        elif any(k in clean for k in ["Problem Statement", "BASIC QUESTION", "CONTEXT:", "CRITERIA", "SCOPE:", "STAKEHOLDERS", "BREAK POINT", "KEY ASSUMPTIONS"]):
            _narrate(clean[:120], "info")
        elif clean.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.")):
            # Numbered items (buckets, criteria, etc.)
            print(f"  {A}  {clean}{R}")
        elif "snippets" in clean or "articles" in clean or "events" in clean:
            _narrate(clean, "data")
        elif "Searching" in clean or "Fetching" in clean or "Generating" in clean or "Summarizing" in clean:
            _narrate(clean, "data")
        elif "Step" in clean and ("done" in clean.lower() or "complete" in clean.lower()):
            _narrate(clean, "done")
        else:
            print(f"  {DK}  {clean[:120]}{R}")

    proc.wait()

    if proc.returncode == 0:
        _narrate("Pipeline complete.", "done")
        # Find and open the output
        run_dir = sorted(OUTPUTS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[0] if OUTPUTS.exists() else None
        if run_dir:
            output = run_dir / "output.html"
            if output.exists():
                webbrowser.open(f"file:///{output.resolve()}")
                _narrate(f"Opened: {output}", "done")
    else:
        _narrate(f"Pipeline exited with code {proc.returncode}", "warn")


def cmd_step(args):
    """Run a single pipeline step."""
    run_dir = _find_run(args.run)
    if not run_dir:
        _narrate("No run found.", "warn")
        return

    state = _load_state(run_dir)
    if not state:
        _narrate("No state.json found.", "warn")
        return

    step_num = int(args.step_num)
    step_name = STEP_NAMES.get(step_num, f"Step {step_num}")

    _narrate(f"Running step {step_num}: {step_name}", "step")

    # Set state to this step
    state["step"] = step_num
    state["done"] = [i for i in state.get("done", []) if i < step_num]
    json.dump(state, open(run_dir / "state.json", "w", encoding="utf-8"), indent=2)

    # Run pipeline with resume
    import subprocess
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "pipeline.py"), "--resume", str(run_dir), "--autopilot"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    proc.stdin.write("\n\n\n")
    proc.stdin.close()

    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print(f"{AD}  {line}{R}")

    proc.wait()
    _narrate(f"Step {step_num} {'complete' if proc.returncode == 0 else 'failed'}", "done" if proc.returncode == 0 else "warn")


def cmd_inject(args):
    """Inject research files from a folder into a run."""
    run_dir = _find_run(args.run)
    if not run_dir:
        _narrate("No run found.", "warn")
        return

    src = Path(args.folder)
    if not src.exists():
        _narrate(f"Folder not found: {src}", "warn")
        return

    dest = run_dir / "inputs" / "research"
    dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() in (".pdf", ".md", ".txt", ".docx", ".csv", ".json", ".html"):
            shutil.copy2(f, dest / f.name)
            count += 1
            _narrate(f"Copied: {f.name}", "info")

    _narrate(f"Injected {count} files into {dest}", "done")


def cmd_open(args):
    """Open the final output in a browser."""
    run_dir = _find_run(args.run)
    if not run_dir:
        _narrate("No run found.", "warn")
        return

    output = run_dir / "output.html"
    if output.exists():
        webbrowser.open(f"file:///{output.resolve()}")
        _narrate(f"Opened: {output}", "done")
    else:
        _narrate("No output.html found. Run may not be complete.", "warn")


def cmd_sanitize(args):
    """Sanitize outputs — replace company/person names for sharing."""
    run_dir = _find_run(args.run)
    if not run_dir:
        _narrate("No run found.", "warn")
        return

    import subprocess
    cmd_parts = [sys.executable, str(ROOT / "sanitize.py"), str(run_dir)]

    if args.auto:
        cmd_parts.append("--auto-apply")
        _narrate("Auto-sanitizing with AI-suggested replacements...", "step")
    elif args.replacements:
        cmd_parts.append("--replace")
        cmd_parts.extend(args.replacements)
        _narrate(f"Applying {len(args.replacements)} replacements...", "step")
    else:
        cmd_parts.append("--list")
        _narrate("Scanning for proper nouns to sanitize...", "step")

    proc = subprocess.run(cmd_parts, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    if proc.stdout:
        print(f"{AD}{proc.stdout}{R}")
    if proc.returncode == 0:
        _narrate("Sanitization complete.", "done")
    else:
        _narrate(f"Sanitizer error: {proc.stderr[:200]}", "warn")


def cmd_list(args):
    """List all runs."""
    print(ANVIL_BANNER)
    if not OUTPUTS.exists():
        _narrate("No runs yet.", "info")
        return

    runs = sorted(OUTPUTS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for d in runs[:15]:
        state = _load_state(d)
        if state:
            step = state.get("step", "?")
            done = state.get("done", [])
            complete = len(done) == 8
            status = f"{GRN}DONE{R}" if complete else f"{A}step {step}{R}"
            topic = state.get("topic", "?")[:60]
            _narrate(f"{status}  {d.name[:45]}  {DM}{topic}{R}", "info")


def main():
    parser = argparse.ArgumentParser(description="ANVIL — Strategic Problem-Solving Engine")
    sub = parser.add_subparsers(dest="cmd")

    # run (autopilot)
    p_run = sub.add_parser("run", help="Run full pipeline in autopilot")
    p_run.add_argument("--topic", required=True)
    p_run.add_argument("--audience", default="Senior leadership")
    p_run.add_argument("--inputs", help="Folder with research files to inject")

    # status
    p_status = sub.add_parser("status", help="Show run status")
    p_status.add_argument("--run", default=None)

    # show
    p_show = sub.add_parser("show", help="Show specific output")
    p_show.add_argument("what", choices=["mece", "tree", "research", "working", "synthesis", "hypotheses", "document", "appendix", "output", "landscape"])
    p_show.add_argument("--run", default=None)

    # step
    p_step = sub.add_parser("step", help="Run a single step")
    p_step.add_argument("step_num", type=int)
    p_step.add_argument("--run", required=True)

    # inject
    p_inject = sub.add_parser("inject", help="Inject research files")
    p_inject.add_argument("--run", required=True)
    p_inject.add_argument("--folder", required=True)

    # open
    p_open = sub.add_parser("open", help="Open output in browser")
    p_open.add_argument("--run", default=None)

    # sanitize
    p_san = sub.add_parser("sanitize", help="Sanitize outputs for sharing")
    p_san.add_argument("--run", required=True)
    p_san.add_argument("--auto", action="store_true", help="AI-suggested replacements")
    p_san.add_argument("--replacements", nargs="*", help="Manual replacements: 'Company=Alias'")

    # list
    p_list = sub.add_parser("list", help="List all runs")

    # init — set up Claude Code integration
    p_init = sub.add_parser("init", help="Set up Anvil for Claude Code")

    args = parser.parse_args()

    cmds = {
        "run": cmd_run,
        "status": cmd_status,
        "show": cmd_show,
        "step": cmd_step,
        "inject": cmd_inject,
        "sanitize": cmd_sanitize,
        "open": cmd_open,
        "list": cmd_list,
        "init": cmd_init,
    }

    if args.cmd in cmds:
        cmds[args.cmd](args)
    else:
        print(ANVIL_BANNER)
        _flow_explainer()
        print(f"  {A}Get started:{R}")
        print(f"    {AB}anvil init{R}          Set up Claude Code integration")
        print(f"    {AB}anvil run{R}           Run a problem in autopilot")
        print(f"    {AB}anvil list{R}          Show all runs")
        print(f"    {AB}anvil --help{R}        All commands")
        print()


if __name__ == "__main__":
    main()

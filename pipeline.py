#!/usr/bin/env python3
"""
Strategic Problem-Solving Pipeline
===================================
One command. Human reviews at checkpoints. Everything else automated.

Usage:
    python pipeline.py --topic "..." --audience "..."
    python pipeline.py --topic "..." --audience "..." --autopilot
    python pipeline.py --resume outputs/runs/my_run

Modes:
    Interactive (default):  5 human checkpoints, can inject data, go back, revise
    Autopilot (--autopilot): End-to-end, no stops. Give it a problem, get a document.

Human commands at checkpoints:
    approve          Move to next step
    skip             Move on without changes
    feedback: X      Revise with your feedback
    back             Go to previous checkpoint
    add: X           Inject data or hypothesis
    answer 3.5: X    Answer a specific sub-question
    edit             Open file in editor, press enter when done
    quit             Save progress and exit (resume later)

Research input (A/B/C):
    A                Proceed with public knowledge
    B                Upload research files (drop in inputs/research/)
    C                Save checklist & quit to gather data, resume later

Human can also drop files into:
    inputs/research/     PDFs, docs, data for research step
    inputs/hypothesis/   Additional hypotheses or evidence
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import time
import webbrowser
import html as html_mod
from pathlib import Path
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
OUTPUTS = ROOT / "outputs"
VAULT = ROOT / "vault"

TODAY = date.today()
TODAY_STR = TODAY.strftime("%B %d, %Y")

try:
    from telemetry import log_run_start, log_step_complete, log_run_complete, log_error
except ImportError:
    def log_run_start(*a, **k): pass
    def log_step_complete(*a, **k): pass
    def log_run_complete(*a, **k): pass
    def log_error(*a, **k): pass

sys.path.insert(0, str(ROOT / "story_engine"))

# ---------------------------------------------------------------------------
# Terminal UI
# ---------------------------------------------------------------------------

class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    R = "\033[0m"
    # Anvil amber palette (true color)
    AMBER = "\033[38;2;245;166;35m"
    AMBER_DIM = "\033[38;2;155;106;20m"
    AMBER_BRIGHT = "\033[38;2;255;208;128m"
    AMBER_BG = "\033[48;2;20;16;8m"
    FORGE = "\033[38;2;245;166;35m\033[1m"  # bold amber


STEPS = [
    {"num": 0, "name": "Problem Statement", "human": True},
    {"num": 1, "name": "Issue Tree", "human": True},
    {"num": 2, "name": "Research", "human": False},
    {"num": 3, "name": "Working Document", "human": False},
    {"num": 4, "name": "Synthesis", "human": True},
    {"num": 5, "name": "Hypotheses", "human": True},
    {"num": 6, "name": "Final Document", "human": True},
    {"num": 7, "name": "Appendix", "human": True},
]


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def progress_bar(current):
    print(f"\n{C.DIM}{'_'*60}{C.R}")
    if _run_dir:
        print(f"  {C.DIM}Run: {_run_dir}{C.R}")
    for s in STEPS:
        n, name, human = s["num"], s["name"], s["human"]
        tag = "" if human else f" {C.DIM}(auto){C.R}"
        if n < current:
            print(f"  {C.GREEN}[done]{C.R} {n}. {C.DIM}{name}{C.R}{tag}")
        elif n == current:
            print(f"  {C.YELLOW}[ >> ]{C.R} {n}. {C.BOLD}{name}{C.R}{tag}")
        else:
            print(f"  {C.DIM}[    ] {n}. {name}{tag}{C.R}")
    print(f"{C.DIM}{'_'*60}{C.R}\n")


def show_commands(extra=None):
    cmds = [
        ("approve", "accept and continue"),
        ("skip", "continue without changes"),
        ("feedback: X", "revise with your input"),
        ("back", "go to previous step"),
        ("add: X", "inject data or hypothesis"),
        ("view", "open output file to read"),
        ("edit", "open file, edit, then reload"),
        ("quit", "save and exit"),
    ]
    if extra:
        cmds.extend(extra)
    print(f"  {C.DIM}Commands:{C.R}")
    for cmd, desc in cmds:
        print(f"    {C.BOLD}{cmd:16}{C.R} {C.DIM}{desc}{C.R}")
    print()


def prompt_human() -> str:
    try:
        return input(f"  {C.YELLOW}>>> {C.R}").strip()
    except (EOFError, KeyboardInterrupt):
        return "quit"


def _get_editable_file(step_num):
    """Return the file path to edit for a given step."""
    if not _run_dir:
        return None
    run = Path(_run_dir)
    step_files = {
        0: run / "mece" / "decomposition.json",
        1: run / "tree.html",
        4: run / "synthesis" / "synthesis.md",
        5: run / "hypotheses" / "hypotheses.json",
        6: run / "final_document.html",
        7: run / "appendix.html",
    }
    f = step_files.get(step_num)
    return str(f) if f and f.exists() else None


def checkpoint(step_num, summary, html_path=None, extra_cmds=None, autopilot=False):
    """Show output, wait for human. Returns (action, detail)."""
    progress_bar(step_num)
    name = STEPS[step_num]["name"]
    print(f"  {C.CYAN}{C.BOLD}CHECKPOINT: Step {step_num} -- {name}{C.R}")
    print(f"  {C.DIM}{'_'*50}{C.R}\n")
    print(summary)
    print()
    if html_path and os.path.exists(html_path):
        print(f"  {C.BLUE}Opened in browser: {Path(html_path).name}{C.R}\n")
        if not autopilot:
            webbrowser.open(f"file:///{os.path.abspath(html_path).replace(os.sep, '/')}")

    if autopilot:
        print(f"  {C.DIM}[autopilot] auto-approved{C.R}\n")
        return "approve", ""

    while True:
        show_commands(extra_cmds)
        resp = prompt_human()

        if resp.lower() in ("approve", "skip", "quit", "back"):
            return resp.lower(), ""
        elif resp.lower() in ("edit", "view", "open"):
            edit_file = html_path or _get_editable_file(step_num)
            if edit_file:
                print(f"  {C.BLUE}Opening: {edit_file}{C.R}\n")
                if os.name == "nt":
                    os.startfile(edit_file)
                else:
                    editor = os.environ.get("EDITOR", "nano")
                    os.system(f'{editor} "{edit_file}"')
                if resp.lower() == "edit":
                    print(f"  {C.DIM}Make your changes, save, then press Enter.{C.R}")
                    try:
                        input(f"  {C.YELLOW}Press Enter when done editing... {C.R}")
                    except (EOFError, KeyboardInterrupt):
                        pass
                    print(f"  {C.GREEN}File saved.{C.R}\n")
                    return "edit", edit_file
                # view/open — just opens, stays at checkpoint
            else:
                print(f"  {C.YELLOW}No file for this step.{C.R}\n")
        elif resp.lower().startswith("feedback:"):
            return "feedback", resp[9:].strip()
        elif resp.lower().startswith("add:"):
            return "add", resp[4:].strip()
        elif resp.lower().startswith("answer "):
            return "answer", resp
        else:
            print(f"  {C.RED}Unknown command. Try: approve / feedback: X / quit{C.R}\n")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class State:
    def __init__(self, run_dir: Path):
        self.dir = run_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "state.json"
        self.data = self._load()

    def _load(self):
        if self.file.exists():
            return json.load(open(self.file, encoding="utf-8"))
        return {"step": 0, "done": [], "topic": "", "audience": "", "created": TODAY_STR, "human_inputs": []}

    def save(self):
        tmp = self.file.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            import os
            os.replace(str(tmp), str(self.file))
        except Exception as e:
            print(f"  WARNING: Failed to save state: {e}")
            if tmp.exists():
                try: tmp.unlink()
                except: pass
        self.update_dashboard()

    @property
    def step(self): return self.data.get("step", 0)

    @step.setter
    def step(self, v):
        self.data["step"] = v
        self.save()

    def complete(self, n):
        if n not in self.data["done"]:
            self.data["done"].append(n)
        self.data["step"] = n + 1
        self.save()

    def set(self, k, v):
        self.data[k] = v
        self.save()

    def get(self, k, d=None):
        return self.data.get(k, d)

    def update_dashboard(self):
        """Write current state into dashboard.html for live browser view."""
        try:
            dashboard_path = ROOT / "dashboard.html"
            if not dashboard_path.exists():
                return
            html = dashboard_path.read_text(encoding="utf-8")

            # Gather stats
            stats = {
                "step": self.data.get("step", 0),
                "done": self.data.get("done", []),
                "topic": self.data.get("topic", ""),
                "audience": self.data.get("audience", ""),
                "created": self.data.get("created", ""),
                "run_dir": str(self.dir.name) if hasattr(self, 'dir') else "",
                "updated_at": datetime.now().isoformat(),
            }

            # Mode
            mode = self.data.get("mode", "issue-driven")
            stats["mode"] = mode
            if mode == "hypothesis-driven":
                stats["user_hypothesis"] = self.data.get("user_hypothesis", "")[:200]
                stats["locked_governing"] = self.data.get("locked_governing", "")[:200]

            # Add enriched stats from files
            mece_path = self.data.get("mece_path", "")
            if mece_path and Path(mece_path).exists():
                try:
                    with open(mece_path, encoding="utf-8") as f:
                        md = json.load(f)
                    stats["buckets"] = len(md.get("sections", []))
                    stats["questions"] = sum(len(s.get("questions", [])) for s in md.get("sections", []))
                    # Break point
                    bp = md.get("decision_sensitivity", "")
                    if bp:
                        stats["break_point"] = bp[:200]
                except Exception:
                    pass

            ls_path = self.data.get("landscape_path", "")
            if ls_path and Path(ls_path).exists():
                try:
                    with open(ls_path, encoding="utf-8") as f:
                        ld = json.load(f)
                    stats["snippets"] = len(ld.get("snippets", []))
                    landscape_articles = len(ld.get("articles", []))
                    # Count per-bucket articles from research files
                    research_dir = self.dir / "research" if hasattr(self, 'dir') else None
                    bucket_articles = 0
                    if research_dir and research_dir.exists():
                        for bf in research_dir.glob("bucket_*.md"):
                            try:
                                for line in bf.read_text(encoding="utf-8").split("\n")[:10]:
                                    if line.startswith("Full articles:"):
                                        bucket_articles += int(line.split(":")[1].strip())
                                        break
                            except Exception:
                                pass
                    stats["articles"] = landscape_articles + bucket_articles
                    stats["step_0_summary"] = f"{stats.get('buckets',0)} buckets, {stats.get('questions',0)} questions, {stats['snippets']} snippets scanned"
                    if bucket_articles:
                        stats["step_2_summary"] = f"{bucket_articles} articles fetched across {stats.get('buckets',0)} buckets + {landscape_articles} from landscape scan"
                except Exception:
                    pass

            # Synthesis stats
            syn_path = self.data.get("synthesis_path", "")
            if syn_path and Path(syn_path).exists():
                try:
                    with open(syn_path, encoding="utf-8") as f:
                        syn = json.load(f)
                    findings_count = sum(len(b.get("findings", [])) for b in syn.get("findings", {}).get("buckets", []))
                    patterns_count = len(syn.get("patterns", {}).get("patterns", []))
                    inferences_count = len(syn.get("inferences", {}).get("inferences", []))
                    stats["findings"] = findings_count
                    stats["patterns"] = patterns_count
                    stats["step_4_summary"] = f"{findings_count} findings, {patterns_count} patterns, {inferences_count} inferences"
                except Exception:
                    pass

            # Hypothesis stats
            hyp_path = self.data.get("hyp_path", "")
            if hyp_path and Path(hyp_path).exists():
                try:
                    with open(hyp_path, encoding="utf-8") as f:
                        hyp = json.load(f)
                    all_h = hyp.get("hypotheses", [])
                    active = [h for h in all_h if h.get("status") != "killed"]
                    killed = len(hyp.get("graveyard", []))
                    stats["hypotheses_total"] = len(all_h)
                    stats["hypotheses_active"] = len(active)
                    stats["killed"] = killed
                    gov = hyp.get("governing_hypothesis", "")
                    if gov:
                        stats["governing"] = gov[:250]
                    stats["step_5_summary"] = f"{len(active)} active, {killed} killed, governing hypothesis set"
                except Exception:
                    pass

            # Appendix stats
            slides_path = self.dir / "appendix" / "slides.json" if hasattr(self, 'dir') else None
            if slides_path and slides_path.exists():
                try:
                    with open(slides_path, encoding="utf-8") as f:
                        sl = json.load(f)
                    stats["appendix_slides"] = len(sl.get("slides", []))
                    stats["step_7_summary"] = f"{stats['appendix_slides']} proof slides generated"
                except Exception:
                    pass

            # Compute spend + LLM calls
            with _token_lock:
                s_in = _total_input_tokens - _total_input_tokens_haiku
                s_out = _total_output_tokens - _total_output_tokens_haiku
                spend = (s_in * 3 + s_out * 15 + _total_input_tokens_haiku * 0.8 + _total_output_tokens_haiku * 4) / 1_000_000
                stats["llm_calls"] = _llm_call_count
            if spend > 0:
                stats["spend"] = f"{spend:.2f}"

            # Write state to separate JS file (dashboard loads via <script src>)
            state_js = f"var ANVIL_STATE = {json.dumps(stats, ensure_ascii=False)};"
            state_js_path = ROOT / "dashboard_state.js"
            state_js_path.write_text(state_js, encoding="utf-8")

            # Also inject inline for backwards compat
            import re
            html = re.sub(
                r'var ANVIL_STATE = .*',
                state_js,
                html
            )
            dashboard_path.write_text(html, encoding="utf-8")
        except Exception:
            pass  # Dashboard update is non-critical

    def add_input(self, step, kind, content):
        self.data["human_inputs"].append({"step": step, "type": kind, "content": content, "time": datetime.now().isoformat()})
        self.save()


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

_client = None
_run_dir = None

def get_client():
    global _client
    if _client:
        return _client
    import anthropic
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        print(f"\n  {C.YELLOW}Anthropic API key not found.{C.R}")
        print(f"  {C.DIM}Get one at: https://console.anthropic.com/settings/keys{C.R}\n")
        try:
            key = input(f"  {C.YELLOW}Enter your ANTHROPIC_API_KEY: {C.R}").strip()
        except (EOFError, KeyboardInterrupt):
            key = ""
        if not key:
            print(f"  {C.RED}No API key provided. Cannot proceed.{C.R}")
            sys.exit(1)
        # Save to .env so they don't have to enter it again
        env_path = ROOT / ".env"
        if env_path.exists():
            existing = env_path.read_text(encoding="utf-8")
            if "ANTHROPIC_API_KEY" not in existing:
                env_path.write_text(existing.rstrip() + f"\nANTHROPIC_API_KEY={key}\n", encoding="utf-8")
        else:
            env_path.write_text(f"ANTHROPIC_API_KEY={key}\n", encoding="utf-8")
        print(f"  {C.GREEN}Saved to .env — you won't need to enter it again.{C.R}\n")
    _client = anthropic.Anthropic(api_key=key)
    return _client


SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"
_llm_call_count = 0
_total_input_tokens = 0
_total_output_tokens = 0
_total_input_tokens_haiku = 0
_total_output_tokens_haiku = 0
_token_lock = __import__("threading").Lock()
MAX_BUDGET_USD = 10.0  # hard cost ceiling — abort if total spend exceeds this
BLOCKED_DOMAINS = {"reuters.com", "ft.com", "wsj.com", "bloomberg.com", "nytimes.com", "economist.com", "barrons.com", "seekingalpha.com"}

def llm(system, user, model="claude-sonnet-4-6", max_tokens=16384):
    global _llm_call_count, _total_input_tokens, _total_output_tokens, _total_input_tokens_haiku, _total_output_tokens_haiku

    with _token_lock:
        _llm_call_count += 1
        call_num = _llm_call_count
        # Budget guard — per-model pricing: Sonnet $3/$15, Haiku $0.80/$4
        sonnet_in = _total_input_tokens - _total_input_tokens_haiku
        sonnet_out = _total_output_tokens - _total_output_tokens_haiku
        est_cost = (sonnet_in * 3 + sonnet_out * 15 + _total_input_tokens_haiku * 0.8 + _total_output_tokens_haiku * 4) / 1_000_000
        if est_cost > MAX_BUDGET_USD:
            print(f"  {C.RED}BUDGET GUARD: Estimated spend ${est_cost:.2f} exceeds ${MAX_BUDGET_USD:.2f} limit. Aborting.{C.R}")
            raise RuntimeError(f"Budget exceeded: ${est_cost:.2f} > ${MAX_BUDGET_USD:.2f}")

    # Show what we're doing
    sys_preview = system[:80].replace("\n", " ").strip()
    input_chars = len(system) + len(user)
    print(f"  {C.DIM}[LLM #{call_num}] {sys_preview}...{C.R}")
    print(f"  {C.DIM}         -> {input_chars:,} chars in | model: {model} | spend: ${est_cost:.2f}{C.R}")

    client = get_client()
    t0 = time.time()
    for attempt in range(5):
        try:
            # Use streaming to avoid timeout on large calls
            output_text = ""
            in_tok = 0
            out_tok = 0
            with client.messages.stream(model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}]) as stream:
                for text in stream.text_stream:
                    output_text += text
                response = stream.get_final_message()
                in_tok = response.usage.input_tokens if hasattr(response, 'usage') else 0
                out_tok = response.usage.output_tokens if hasattr(response, 'usage') else 0
            elapsed = time.time() - t0
            with _token_lock:
                if isinstance(in_tok, int):
                    _total_input_tokens += in_tok
                    if "haiku" in model:
                        _total_input_tokens_haiku += in_tok
                if isinstance(out_tok, int):
                    _total_output_tokens += out_tok
                    if "haiku" in model:
                        _total_output_tokens_haiku += out_tok
            with _token_lock:
                s_in = _total_input_tokens - _total_input_tokens_haiku
                s_out = _total_output_tokens - _total_output_tokens_haiku
                cur_cost = (s_in * 3 + s_out * 15 + _total_input_tokens_haiku * 0.8 + _total_output_tokens_haiku * 4) / 1_000_000
            print(f"  {C.DIM}         <- {len(output_text):,} chars out | {in_tok} in / {out_tok} out tokens | {elapsed:.1f}s | total: ${cur_cost:.2f}{C.R}")
            return output_text
        except Exception as e:
            if "overloaded" in str(e).lower() or "529" in str(e):
                wait = 15 * (attempt + 1)
                print(f"  {C.YELLOW}         [wait] API busy, retrying in {wait}s (attempt {attempt+1}/5)...{C.R}")
                time.sleep(wait)
            else:
                elapsed = time.time() - t0
                print(f"  {C.RED}         [X] Error after {elapsed:.1f}s: {str(e)[:100]}{C.R}")
                raise
    raise Exception("API overloaded after 5 retries")


def llm_json(system, user, max_retries=4, **kw):
    for attempt in range(max_retries + 1):
        raw = llm(system, user, **kw)
        t = raw.strip()

        # Strip markdown fences
        if t.startswith("```"):
            t = t.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        # Handle empty response
        if not t:
            if attempt < max_retries:
                wait = 10 * (attempt + 1)
                print(f"  {C.YELLOW}  Empty response, waiting {wait}s then retrying ({attempt+1}/{max_retries})...{C.R}")
                time.sleep(wait)
                continue
            print(f"  {C.RED}  Empty response after {max_retries+1} attempts{C.R}")
            raise ValueError("LLM returned empty response")

        try:
            return json.loads(t)
        except json.JSONDecodeError as e:
            # Try to extract JSON from mixed text (LLM sometimes adds prose before/after JSON)
            import re as _json_re
            json_match = _json_re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', t)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

            # Check if it's a truncation (incomplete JSON) vs garbage
            has_json_start = t.startswith("{") or t.startswith("[")

            if has_json_start:
                # Truncated JSON — try continuation
                print(f"  {C.YELLOW}  JSON truncated, requesting continuation...{C.R}")
                try:
                    client = get_client()
                    cont_text = ""
                    with client.messages.stream(
                        model=kw.get("model", "claude-sonnet-4-6"),
                        max_tokens=kw.get("max_tokens", 16384),
                        system=system,
                        messages=[
                            {"role": "user", "content": user},
                            {"role": "assistant", "content": raw},
                            {"role": "user", "content": "Your JSON was truncated. Continue EXACTLY where you left off. Output ONLY the remaining JSON -- no preamble, no explanation."},
                        ],
                    ) as cont_stream:
                        for chunk in cont_stream.text_stream:
                            cont_text += chunk
                    cont_text = cont_text.strip()
                    combined = t + cont_text
                    if "```" in combined:
                        combined = combined.replace("```json", "").replace("```", "").strip()
                    return json.loads(combined)
                except json.JSONDecodeError:
                    if attempt < max_retries:
                        wait = 10 * (attempt + 1)
                        print(f"  {C.YELLOW}  Continuation failed, waiting {wait}s then retrying ({attempt+1}/{max_retries})...{C.R}")
                        time.sleep(wait)
                        continue
                except Exception as e2:
                    if attempt < max_retries:
                        wait = 10 * (attempt + 1)
                        print(f"  {C.YELLOW}  Continuation error: {e2}, waiting {wait}s then retrying ({attempt+1}/{max_retries})...{C.R}")
                        time.sleep(wait)
                        continue
            else:
                # Not JSON at all — retry
                if attempt < max_retries:
                    wait = 10 * (attempt + 1)
                    print(f"  {C.YELLOW}  Response not JSON, waiting {wait}s then retrying ({attempt+1}/{max_retries})...{C.R}")
                    time.sleep(wait)
                    continue

            # Final failure
            print(f"  {C.RED}  JSON parse failed after all attempts{C.R}")
            print(f"  {C.DIM}  First 300 chars: {t[:300]}{C.R}")
            print(f"  {C.DIM}  Last 300 chars: {t[-300:]}{C.R}")
            raise e


# ---------------------------------------------------------------------------
# Current events scanning
# ---------------------------------------------------------------------------

# _scan_current_events removed — replaced by two-tier _broad_research_scan


# ---------------------------------------------------------------------------
# Input folder scanning
# ---------------------------------------------------------------------------

def scan_inputs(run_dir, subfolder):
    """Check for human-dropped files in inputs/<subfolder>/."""
    input_dir = run_dir / "inputs" / subfolder
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        return []
    files = [f for f in input_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
    if files:
        print(f"  {C.GREEN}Found {len(files)} file(s) in inputs/{subfolder}/{C.R}")
        for f in files:
            print(f"    {C.DIM}{f.name} ({f.stat().st_size:,} bytes){C.R}")
    return files


def extract_from_files(files):
    """Use LLM to extract relevant data from dropped files."""
    extracted = []
    for f in files:
        suffix = f.suffix.lower()
        if suffix in (".txt", ".md", ".csv", ".json"):
            content = f.read_text(encoding="utf-8", errors="ignore")[:10000]
        elif suffix in (".pdf",):
            content = f"[PDF file: {f.name}, {f.stat().st_size:,} bytes -- extraction requires pdfplumber]"
        else:
            content = f"[File: {f.name}, {f.stat().st_size:,} bytes -- binary, skipped]"

        if content and not content.startswith("["):
            summary = llm(
                "Extract key facts, numbers, and data points from this document. Return a bullet list of findings. Be concise.",
                f"File: {f.name}\n\n{content}"
            )
            extracted.append({"file": f.name, "findings": summary})
            print(f"    {C.GREEN}Extracted from {f.name}{C.R}")
    return extracted


# ---------------------------------------------------------------------------
# Load vaults
# ---------------------------------------------------------------------------

def load_vault(name):
    path = VAULT / f"{name}.json"
    if path.exists():
        return json.load(open(path, encoding="utf-8"))
    return {}

CHART_VAULT = load_vault("chart_vault")
DOC_VAULT = load_vault("final_doc_vault")


# ---------------------------------------------------------------------------
# STEP 0: Problem Statement
# ---------------------------------------------------------------------------

def step0(state, autopilot=False, hypothesis_mode=False):
    progress_bar(0)

    # If topic is already set (from --topic flag), skip interactive prompts
    ps_text = state.get("topic", "")
    context = ""

    if ps_text:
        # Topic provided via --topic: show it, don't re-ask
        print(f"  {C.BOLD}Problem statement loaded from arguments.{C.R}\n")
    else:
        # Interactive: ask for input
        print(f"  {C.BOLD}Let's define the problem.{C.R}\n")
        print(f"  {C.CYAN}What's the problem or question you're trying to answer?{C.R}")
        print(f"  {C.DIM}Type naturally. One sentence or a few. Press Enter when done.{C.R}\n")
        try:
            user_ps = input(f"  {C.YELLOW}> {C.R}").strip()
            if user_ps:
                ps_text = user_ps
        except (EOFError, KeyboardInterrupt):
            pass

        print(f"\n  {C.CYAN}Any context I should know? (background, constraints, data){C.R}")
        print(f"  {C.DIM}Press Enter to skip.{C.R}\n")
        try:
            context = input(f"  {C.YELLOW}> {C.R}").strip()
        except (EOFError, KeyboardInterrupt):
            context = ""

    # Confirm back
    print(f"\n  {C.DIM}{'_'*50}{C.R}")
    print(f"  {C.BOLD}Got it:{C.R}")
    print(f"  Problem:  {ps_text[:200]}")
    if context:
        print(f"  Context:  {context[:200]}")
    print()

    # Ask user to choose mode (unless --autopilot was passed on command line)
    if not autopilot:
        print(f"  {C.BOLD}How would you like to run this?{C.R}\n")
        print(f"    {C.BOLD}1{C.R}  Interactive — review each step, inject data, steer the analysis")
        print(f"    {C.BOLD}2{C.R}  Autopilot — I'll grab a coffee, run everything end-to-end")
        print()
        try:
            mode = input(f"  {C.YELLOW}Choose [1/2]: {C.R}").strip()
        except (EOFError, KeyboardInterrupt):
            mode = "1"
        if mode == "2":
            autopilot = True

    # Pipeline disclaimer
    mode_name = "HYPOTHESIS-DRIVEN" if hypothesis_mode else "ISSUE-DRIVEN"
    pace_name = "AUTOPILOT" if autopilot else "GUIDED"

    if hypothesis_mode:
        pipeline_line = f"PS → Landscape → Challenge → Decompose → Deep Test → Brief → Charts"
        if autopilot:
            print(f"""
  {C.BOLD}{'='*55}{C.R}
  {C.YELLOW}{C.BOLD}{mode_name} — {pace_name}{C.R}
  {C.BOLD}{'='*55}{C.R}

  {C.BOLD}Pipeline:{C.R}
  {C.AMBER}{pipeline_line}{C.R}

  {C.BOLD}What will happen:{C.R}
    {C.GREEN}1.{C.R} Problem statement — challenge framing, lock decision sensitivity
    {C.GREEN}2.{C.R} Landscape scan — read the web before testing
    {C.GREEN}3.{C.R} Challenge your Day 1 answer using landscape findings
    {C.GREEN}4.{C.R} Decompose into necessary conditions
    {C.GREEN}5.{C.R} Deep targeted search on EVERY leaf — more queries, full articles
    {C.GREEN}6.{C.R} Stress test, kill propagation, iterate until stable
    {C.GREEN}7.{C.R} Final brief + appendix from survivors

  {C.BOLD}What to know:{C.R}
    {C.DIM}• Skips MECE, broad research, working doc, synthesis{C.R}
    {C.DIM}• Your hypothesis gets stress-tested, not rubber-stamped{C.R}
    {C.DIM}• Deep search on ALL leaves, not just uncertain ones{C.R}

  {C.BOLD}Estimated:{C.R} ~10 min  |  ~$1-2 API cost
  {C.BOLD}{'='*55}{C.R}
""")
        else:
            print(f"""
  {C.BOLD}{'='*55}{C.R}
  {C.CYAN}{C.BOLD}{mode_name} — {pace_name}{C.R}
  {C.BOLD}{'='*55}{C.R}

  {C.BOLD}Pipeline:{C.R}
  {C.AMBER}{pipeline_line}{C.R}

  {C.BOLD}You steer at every checkpoint:{C.R}
    {C.CYAN}1.{C.R} Problem statement — iterate until framing is sharp
    {C.CYAN}2.{C.R} Hypothesis challenge — accept, revise, or reject the sharpened version
    {C.CYAN}3.{C.R} Hypothesis tree — review decomposition, add your own conditions
    {C.CYAN}4.{C.R} Deep search results — review evidence, inject internal data
    {C.CYAN}5.{C.R} Final brief — sharpen with specific feedback
    {C.CYAN}6.{C.R} Appendix — review proof charts

  {C.BOLD}What to know:{C.R}
    {C.DIM}• Challenge step ALWAYS runs — Claude pushes back on your hypothesis{C.R}
    {C.DIM}• You review the sharpened hypothesis before decomposition{C.R}
    {C.DIM}• Deep search on ALL leaves, not just uncertain ones{C.R}

  {C.BOLD}Estimated:{C.R} ~10-15 min  |  ~$1-2 API cost
  {C.BOLD}{'='*55}{C.R}
""")
    elif autopilot:
        print(f"""
  {C.BOLD}{'='*55}{C.R}
  {C.YELLOW}{C.BOLD}{mode_name} — {pace_name}{C.R}
  {C.BOLD}{'='*55}{C.R}

  {C.BOLD}Pipeline:{C.R}
  {C.AMBER}PS → MECE → Research → Working Doc → Synthesis → Hypothesis Tree → Brief → Charts{C.R}

  {C.BOLD}What will happen:{C.R}
    {C.GREEN}1.{C.R} Problem statement — challenge framing, lock decision sensitivity
    {C.GREEN}2.{C.R} MECE decomposition — 4-10 buckets, 5-8 questions each
    {C.GREEN}3.{C.R} Deep research — ~120 queries, ~50 articles from live web search
    {C.GREEN}4.{C.R} Working document + research debrief
    {C.GREEN}5.{C.R} Synthesis — findings → patterns → inferences across all buckets
    {C.GREEN}6.{C.R} Hypothesis tree — decompose into necessary conditions, test at
       leaves (GREEN/AMBER/RED), kill propagation, iterate until stable
    {C.GREEN}7.{C.R} Final brief — 3-5 pages, sourced claims, decisions with deadlines
    {C.GREEN}8.{C.R} Appendix — proof charts, one claim = one chart

  {C.BOLD}What to know:{C.R}
    {C.DIM}• Research: live web search + full article fetch (not LLM knowledge){C.R}
    {C.DIM}• Hypothesis testing: iterative tree with targeted gap research{C.R}
    {C.DIM}• Proprietary data not included unless you inject files{C.R}
    {C.DIM}• No human review in autopilot — use guided mode to steer{C.R}

  {C.BOLD}Estimated:{C.R} ~20 min  |  ~$2-3 API cost  |  ~45 LLM calls
  {C.BOLD}{'='*55}{C.R}
""")
    else:
        print(f"""
  {C.BOLD}{'='*55}{C.R}
  {C.CYAN}{C.BOLD}{mode_name} — {pace_name}{C.R}
  {C.BOLD}{'='*55}{C.R}

  {C.BOLD}Pipeline:{C.R}
  {C.AMBER}PS → MECE → Research → Working Doc → Synthesis → Hypothesis Tree → Brief → Charts{C.R}

  {C.BOLD}You steer at every checkpoint:{C.R}
    {C.CYAN}1.{C.R} Problem statement — iterate with Claude until framing is sharp
    {C.CYAN}2.{C.R} MECE decomposition — add/remove buckets, flag overlap
    {C.CYAN}3.{C.R} Research — inject proprietary data, internal reports
    {C.CYAN}4.{C.R} Research debrief — correct numbers, add context
    {C.CYAN}5.{C.R} Synthesis — spot connections Claude missed
    {C.CYAN}6.{C.R} Hypothesis tree — add your own hypotheses, provide kill evidence,
       upgrade AMBER verdicts with internal data
    {C.CYAN}7.{C.R} Final brief — sharpen with specific feedback
    {C.CYAN}8.{C.R} Appendix — review proof charts

  {C.BOLD}What to know:{C.R}
    {C.DIM}• Claude pauses after each step — you review and approve{C.R}
    {C.DIM}• Inject files at step 3 for HIGH confidence evidence{C.R}
    {C.DIM}• Your input upgrades AMBER leaves to GREEN in the hypothesis tree{C.R}
    {C.DIM}• Feedback at any step actually changes the output{C.R}

  {C.BOLD}Estimated:{C.R} ~20-30 min  |  ~$2-3 API cost  |  ~45 LLM calls
  {C.BOLD}{'='*55}{C.R}
""")

    # Step 1: Problem Statement Worksheet (6-component framework)
    print(f"  {C.GREEN}Building Problem Statement Worksheet (v2 — two-step PS preservation)...{C.R}\n")

    # Build the basic_question FIRST — before the full worksheet — to ensure the user's framing is preserved
    preserved_question = llm(
        f"""The user gave you a raw problem statement. Your ONLY job: clean it up into a well-formed question.

RULES — FOLLOW EXACTLY:
1. KEEP the user's verb: if they said "what actions must" → you write "What actions must". If they said "what should X do" → you write "What should X do".
2. KEEP every dimension they mentioned: if they said "business model, talent, partnerships" → all three appear in your output.
3. You may ADD a timeframe if missing, ADD the audience if missing, FIX grammar.
4. You may NOT change the verb, drop dimensions, or rephrase into a different question.
5. Maximum 1-2 sentences.

FORBIDDEN REWRITES:
- "What actions must X take" → "How should X position itself" (WRONG — changed verb)
- "What actions must X take" → "How will Y reshape X" (WRONG — changed subject and made it passive)
- "restructure business model, talent, partnerships" → "maximize commercial value" (WRONG — dropped dimensions)

USER'S RAW INPUT: {ps_text}

Return ONLY the cleaned question, nothing else.""",
        f"Clean up: {ps_text}",
        model=SONNET, max_tokens=256
    )
    # Strip quotes if the LLM wrapped it
    preserved_question = preserved_question.strip().strip('"').strip("'")
    print(f"  {C.DIM}Preserved question: {preserved_question[:150]}{C.R}")

    smart = llm_json(
        f"""You are a senior engagement manager completing the Problem Statement Worksheet.
Today is {TODAY_STR}.

The human has given you a raw problem statement and optional context. Your job is to complete ALL 6 components of the Problem Statement Worksheet.

CRITICAL: The basic_question has ALREADY BEEN WRITTEN for you. Use it EXACTLY as provided. Do NOT rewrite it.

basic_question (USE THIS EXACTLY): "{preserved_question}"

═══════════════════════════════════════════════════════
PROBLEM STATEMENT WORKSHEET (6 COMPONENTS)
═══════════════════════════════════════════════════════

1. BASIC QUESTION TO BE RESOLVED
   ALREADY PROVIDED ABOVE. Copy it into the basic_question field VERBATIM. Do NOT modify it.

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

TIPS:
- Think "opportunity" not just "problem" — expansive, not reductive mindset
- The first cut will be imperfect — get to paper quickly and iterate
- There is interplay between all elements — refining one forces you to refine others
- Capture hypotheses as they emerge but don't follow them yet

Return JSON:
{{"basic_question": "SMART question...",
"context": "situation and complication...",
"criteria_for_success": ["quantitative measure 1", "qualitative measure 2", "..."],
"scope": {{"in_scope": ["..."], "out_of_scope": ["..."]}},
"constraints": ["constraint 1", "constraint 2", "..."],
"stakeholders": {{"decision_makers": ["..."], "supporters": ["..."], "potential_blockers": ["..."]}},
"decision_sensitivity": "The recommendation reverses if...",
"key_assumptions": ["...", "..."]}}""",
        f"RAW PROBLEM STATEMENT:\n{ps_text}\n\nCONTEXT:\n{context if context else 'None provided.'}\n\nComplete the Problem Statement Worksheet."
    )

    smart_ps = smart.get("basic_question", ps_text)
    sens = smart.get("decision_sensitivity", "")
    ctx = smart.get("context", "")
    criteria = smart.get("criteria_for_success", [])
    scope = smart.get("scope", {})
    constraints = smart.get("constraints", [])
    stakeholders = smart.get("stakeholders", {})
    assumptions = smart.get("key_assumptions", [])

    # Save the full worksheet
    mece_dir = state.dir / "mece"
    mece_dir.mkdir(exist_ok=True)
    json.dump(smart, open(mece_dir / "0_problem_worksheet.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Show the worksheet
    print(f"  {C.BOLD}{'='*55}{C.R}")
    print(f"  {C.BOLD}  PROBLEM STATEMENT WORKSHEET{C.R}")
    print(f"  {C.BOLD}{'='*55}{C.R}\n")

    print(f"  {C.BOLD}1. BASIC QUESTION (SMART):{C.R}")
    print(f"  {C.CYAN}{smart_ps}{C.R}\n")

    print(f"  {C.BOLD}2. CONTEXT:{C.R}")
    print(f"  {C.DIM}{ctx[:300]}{C.R}\n")

    if criteria:
        print(f"  {C.BOLD}3. CRITERIA FOR SUCCESS:{C.R}")
        for c in criteria[:5]:
            print(f"    {C.DIM}- {c}{C.R}")
        print()

    if scope:
        print(f"  {C.BOLD}4. SCOPE:{C.R}")
        for s_item in scope.get("in_scope", [])[:3]:
            print(f"    {C.GREEN}+ {s_item}{C.R}")
        for s_item in scope.get("out_of_scope", [])[:3]:
            print(f"    {C.RED}- {s_item}{C.R}")
        print()

    if constraints:
        print(f"  {C.BOLD}5. CONSTRAINTS:{C.R}")
        for con in constraints[:4]:
            print(f"    {C.DIM}- {con}{C.R}")
        print()

    if stakeholders:
        print(f"  {C.BOLD}6. STAKEHOLDERS:{C.R}")
        for dm in stakeholders.get("decision_makers", [])[:2]:
            print(f"    {C.GREEN}Decision: {dm}{C.R}")
        for bl in stakeholders.get("potential_blockers", [])[:2]:
            print(f"    {C.YELLOW}Blocker:  {bl}{C.R}")
        print()

    print(f"  {C.BOLD}BREAK POINT:{C.R} {sens[:200]}")

    if assumptions:
        print(f"\n  {C.BOLD}KEY ASSUMPTIONS:{C.R}")
        for a in assumptions:
            print(f"    {C.DIM}- {a}{C.R}")
    print()

    # ── Engagement Manager Challenge (guided mode only) ──
    # In guided mode, challenge the framing before proceeding.
    # In autopilot, skip — the PS worksheet already handles neutral framing.
    if not autopilot:
        # Generate a challenge / framing critique
        challenge = llm(
            f"""You are a senior engagement manager reviewing a problem statement before committing a team to research it. Today is {TODAY_STR}.

Your job: find weaknesses in this framing and challenge them. Be direct and specific.

IMPORTANT: Do NOT suggest rewriting the problem statement. Do NOT propose a "sharpened version." Your job is to CHALLENGE, not rewrite. The user will decide if changes are needed.

THINGS THAT ARE FINE — DO NOT FLAG THESE AS ISSUES:
- "What actions must X take" — this is action-oriented, GOOD framing
- Naming specific dimensions (business model, talent, partnerships) — this is well-scoped, NOT premature specificity
- "Restructure" as a verb — this is the user's framing, respect it

THINGS THAT ARE ACTUAL PROBLEMS — ONLY FLAG THESE:
1. Truly one-sided: ONLY mentions threats, zero space for opportunities (e.g., "protect against" with no room for "or exploit")
2. Names a specific SOLUTION (e.g., "should we acquire Company X") — this is different from naming dimensions to analyze
3. Missing timeframe
4. Missing decision-maker — who specifically acts on this?
5. Weak break point — is the decision sensitivity specific enough to flip the answer?

Do NOT suggest making the question more exploratory or open-ended. Specific, action-oriented questions produce better analysis than vague ones.

If the framing is strong, say so in one sentence. Don't manufacture problems.

Keep your response to 2-4 sentences. Direct. No pleasantries. No rewrite suggestions.""",
            f"PROBLEM STATEMENT: {smart_ps}\nDECISION SENSITIVITY: {sens}\nAUDIENCE: {state.get('audience', '')}",
            model=SONNET
        )

        print(f"  {C.BOLD}{'='*55}{C.R}")
        print(f"  {C.BOLD}  ENGAGEMENT MANAGER REVIEW{C.R}")
        print(f"  {C.BOLD}{'='*55}{C.R}\n")
        print(f"  {C.CYAN}{challenge.strip()}{C.R}\n")

        print(f"  {C.BOLD}Options:{C.R}")
        print(f"    {C.GREEN}approve{C.R}  — proceed with this framing")
        print(f"    {C.YELLOW}revise: <your changes>{C.R}  — revise the problem statement")
        print(f"    {C.DIM}Type a new problem statement to replace it entirely{C.R}\n")

        try:
            response = input(f"  {C.YELLOW}> {C.R}").strip()
        except (EOFError, KeyboardInterrupt):
            response = "approve"

        if response.lower() not in ("approve", "ok", "yes", "y", "good", ""):
            # User wants to revise — re-run the worksheet with their input
            if response.lower().startswith("revise:"):
                revision = response[7:].strip()
            else:
                revision = response

            print(f"\n  {C.GREEN}Revising problem statement with your input...{C.R}")
            smart = llm_json(
                f"""The user has reviewed the Problem Statement Worksheet and wants to revise it. Today is {TODAY_STR}.

ORIGINAL WORKSHEET:
{json.dumps(smart, indent=2, ensure_ascii=False)}

USER'S REVISION REQUEST: {revision}

Revise the worksheet to incorporate the user's feedback. Keep the 6-component structure. Update the basic_question, decision_sensitivity, and any other affected fields.

Return the COMPLETE revised JSON (same format as above).""",
                f"Revise the worksheet based on: {revision}",
                model=SONNET
            )

            smart_ps = smart.get("basic_question", ps_text)
            sens = smart.get("decision_sensitivity", "")
            ctx = smart.get("context", "")
            json.dump(smart, open(mece_dir / "0_problem_worksheet.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

            print(f"\n  {C.BOLD}Revised question:{C.R}")
            print(f"  {C.CYAN}{smart_ps}{C.R}")
            print(f"\n  {C.BOLD}Break point:{C.R} {sens[:200]}\n")
        else:
            print(f"  {C.GREEN}Proceeding with current framing.{C.R}\n")

    # ── USER DATA INJECTION (before landscape scan) ──
    # In guided mode: ask user if they have data. In autopilot: silently check inputs/ folder.
    user_data_context = ""
    input_dir = state.dir / "inputs" / "research"
    input_dir.mkdir(parents=True, exist_ok=True)

    if not autopilot:
        # Guided mode: ask user if they have data to inject
        print(f"  {C.BOLD}Do you have internal data for this analysis?{C.R}")
        print(f"    {C.BOLD}A{C.R}  No — proceed with public sources only")
        print(f"    {C.BOLD}B{C.R}  Yes — I'll drop files in: {C.BLUE}{input_dir}{C.R}")
        print(f"    {C.BOLD}C{C.R}  Yes — I'll paste key data points here")
        print()
        try:
            data_choice = input(f"  {C.YELLOW}Choose [A/B/C]: {C.R}").strip().upper()
        except (EOFError, KeyboardInterrupt):
            data_choice = "A"

        if data_choice == "B":
            print(f"\n  {C.DIM}Drop files in: {input_dir}{C.R}")
            print(f"  {C.DIM}Supported: .txt, .md, .csv, .json, .pdf{C.R}")
            print(f"  {C.DIM}Press Enter when done.{C.R}")
            try:
                input(f"  {C.YELLOW}[Enter when files are ready] {C.R}")
            except (EOFError, KeyboardInterrupt):
                pass
            files = scan_inputs(state.dir, "research")
            if files:
                print(f"  {C.GREEN}Extracting from {len(files)} file(s)...{C.R}")
                extracted = extract_from_files(files)
                if extracted:
                    user_data_context = "\n\nUSER-PROVIDED DATA (HIGH confidence — treat as primary source):\n"
                    user_data_context += "\n".join(f"From {d['file']}:\n{d['findings']}" for d in extracted)
                    state.set("user_data_injected", True)
                    print(f"  {C.GREEN}{len(extracted)} file(s) extracted — will inform landscape scan, challenge, and testing.{C.R}\n")
        elif data_choice == "C":
            print(f"\n  {C.DIM}Paste your data points (type 'done' on a new line when finished):{C.R}")
            lines = []
            while True:
                try:
                    line = input(f"  {C.YELLOW}> {C.R}")
                except (EOFError, KeyboardInterrupt):
                    break
                if line.strip().lower() == "done":
                    break
                lines.append(line)
            if lines:
                pasted = "\n".join(lines)
                user_data_context = f"\n\nUSER-PROVIDED DATA (HIGH confidence — treat as primary source):\n{pasted}"
                state.set("user_data_injected", True)
                # Also save to file for resume
                (input_dir / "user_pasted_data.txt").write_text(pasted, encoding="utf-8")
                print(f"  {C.GREEN}Data captured — will inform landscape scan, challenge, and testing.{C.R}\n")
        else:
            print(f"  {C.GREEN}Proceeding with public sources only.{C.R}\n")

    # Save user data context for downstream steps
    if user_data_context:
        (state.dir / "inputs" / "user_data_context.md").write_text(user_data_context, encoding="utf-8")
        state.set("user_data_path", str(state.dir / "inputs" / "user_data_context.md"))

    # Step 1.5: Broad Research Scan — read the landscape BEFORE generating MECE
    # Cache-aware: skip if landscape data already exists
    cached_landscape_path = state.dir / "landscape_scan" / "landscape.json"
    if cached_landscape_path.exists():
        print(f"  {C.GREEN}Landscape scan already cached — loading...{C.R}")
        landscape = json.load(open(cached_landscape_path, encoding="utf-8"))
    else:
        print(f"  {C.GREEN}Broad research scan — reading the landscape before decomposition...{C.R}")
        landscape = _broad_research_scan(smart_ps, ctx + user_data_context, state)
    current_events = landscape.get("events", [])
    landscape_summary = landscape.get("summary", "")

    if landscape_summary:
        print(f"  {C.BOLD}LANDSCAPE SCAN:{C.R}")
        # Show first 500 chars
        preview = landscape_summary[:500]
        print(f"  {C.DIM}{preview}{'...' if len(landscape_summary) > 500 else ''}{C.R}")
        print(f"  {C.DIM}({len(landscape.get('articles', []))} articles read, {len(current_events)} events found){C.R}")
        print()
    else:
        print(f"  {C.DIM}No landscape data found{C.R}\n")

    # ── HYPOTHESIS-DRIVEN MODE: early exit after landscape scan ──
    if hypothesis_mode:
        # Return minimal mece with just the PS fields — no sections, no MECE
        minimal_mece = {
            "smart_statement": smart_ps,
            "decision_sensitivity": sens,
            "original_input": ps_text,
            "sections": [],  # no MECE buckets in hypothesis-driven mode
        }
        if context:
            minimal_mece["context"] = context

        mece_dir = state.dir / "mece"
        mece_dir.mkdir(exist_ok=True)
        json.dump(minimal_mece, open(mece_dir / "decomposition.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        state.set("mece_path", str(mece_dir / "decomposition.json"))

        summary = f"""  {C.BOLD}Basic Question:{C.R}
  {C.CYAN}{smart_ps[:400]}{C.R}

  {C.BOLD}Break point:{C.R} {sens[:200]}

  {C.YELLOW}{C.BOLD}HYPOTHESIS-DRIVEN MODE{C.R}
  {C.DIM}Skipping MECE decomposition — going straight to hypothesis testing.{C.R}"""

        return summary, minimal_mece, autopilot

    # Step 2: Generate MECE — informed by the landscape scan
    # Step 2a: Generate JUST the bucket titles
    print(f"  {C.GREEN}Identifying research buckets...{C.R}\n")

    # Build landscape context for MECE generation
    landscape_block = ""
    if landscape_summary:
        landscape_block = f"\nLANDSCAPE SCAN (from reading 15-20 articles about this topic BEFORE decomposition):\n{landscape_summary[:4000]}\n\nYour MECE buckets MUST reflect what the articles actually cover. If the articles mention something important (competitors struggling, regulatory changes, market shifts) that you wouldn't have thought of, create a bucket for it.\n"
    elif current_events:
        landscape_block = "\nCURRENT EVENTS:\n" + "\n".join(
            f"- [{e.get('date','')}] {e.get('title','')}: {e.get('snippet','')}"
            for e in current_events[:10]
        ) + "\n"

    # Load issue tree vault for examples
    issue_vault = load_vault("issue_tree_vault")
    vault_examples = ""
    if issue_vault.get("examples"):
        vault_examples = "\n\nREFERENCE EXAMPLES FROM VAULT:\n"
        for ex in issue_vault["examples"][:5]:
            vault_examples += f"\nProblem: \"{ex['problem']}\"\nMECE cut: {ex.get('mece_cut', '')}\nBuckets:\n"
            for i, b in enumerate(ex["buckets"], 1):
                vault_examples += f"  {i}. \"{b}\"\n"

    # Load issue tree vault
    issue_vault = load_vault("issue_tree_vault")
    vault_text = ""
    if issue_vault:
        # Show decomposition methods
        vault_text = "\n\nDECOMPOSITION METHODS (choose the best fit for this problem):\n"
        for m in issue_vault.get("decomposition_methods", []):
            vault_text += f"\n{m['method']}: {m['when']}\n"
            for ex in m.get("examples", [])[:1]:
                branches = ex.get("branches", [])
                vault_text += f"  Example: {' / '.join(branches)}\n"
        # Show full examples
        vault_text += "\n\nEXAMPLES OF GOOD ISSUE TREES:\n"
        for ex in issue_vault.get("full_examples", [])[:6]:
            vault_text += f"\nProblem: \"{ex['problem']}\"\n"
            for i, b in enumerate(ex["buckets"], 1):
                vault_text += f"  {i}. \"{b}\"\n"
            vault_text += f"  Why MECE: {ex.get('why_mece', '')}\n"

    buckets = llm_json(
        """You are building an ISSUE TREE.

STEP 1 — Choose your decomposition method:
Read the problem. Pick the method that fits best:
- ALGEBRAIC: if there's a number to explain (profit, revenue, cost), decompose the equation
- PROCESS: if there's a sequence of steps, decompose the flow
- CAUSAL: if different actors or forces are driving the problem
- SEGMENTATION: if the problem differs across natural segments
- SITUATION ASSESSMENT: if you need to understand a situation before deciding what to do

STEP 2 — Write 4-6 MECE buckets:
- Each bucket is an OPEN QUESTION, max 8 words
- Plain English. No jargon.
- Questions ask about FACTS — what is, how much, how fast, who, where
- NEVER about actions — no "should", "must", "how to"
- Buckets must be about THIS specific problem, not generic business

STEP 3 — AUXILIARY FORCES:
Read the LANDSCAPE SCAN below. It contains what is actually happening in the world right now. Ask: "What external forces, competitor actions, regulatory shifts, or market dynamics from the landscape scan could MATERIALLY CHANGE the answer to this problem — even though the problem statement doesn't mention them?"

Add 1-2 buckets for these auxiliary forces. These are things the decision-maker might not have asked about but NEEDS to know.

Examples of auxiliary forces:
- Competitors are failing, creating an opportunity the problem statement didn't anticipate
- A regulation is about to change that constrains the solution space
- A technology shift is happening faster than assumed
- A supplier/partner is in trouble, creating knock-on effects

STEP 4 — MECE check:
- Does answering bucket 1 give ANY information that belongs in bucket 2? If yes, overlap. Fix it.
- Is there ANY important question about this problem that falls OUTSIDE all buckets? If yes, gap. Add it.

State which decomposition method you chose and why.

Return JSON: {"method": "algebraic|process|causal|segmentation|situation_assessment", "method_rationale": "why this method fits", "buckets": [{"id": 1, "title": "...", "rationale": "..."}]}""",
        "PROBLEM: {ps}\nCONTEXT: {ctx}\n{landscape}{vault}".format(ps=smart_ps, ctx=ctx, landscape=landscape_block, vault=vault_text)
    )

    bucket_list = buckets.get("buckets", [])
    print(f"  {C.BOLD}Core buckets:{C.R}")
    for b in bucket_list:
        print(f"    {b['id']}. {b['title']}")

    # Step 2a.2: Auxiliary forces check — separate call, can't be ignored
    if landscape_summary:
        print(f"\n  {C.GREEN}Checking for auxiliary forces the core buckets missed...{C.R}")
        existing = "\n".join(f"- {b['title']}" for b in bucket_list)
        try:
            aux = llm_json(
                """You are reviewing an issue tree decomposition. The core buckets cover the INTERNAL dimensions of the problem. But the landscape scan reveals external forces that could materially change the answer.

Your job: identify 1-3 EXTERNAL forces from the landscape scan that are NOT covered by the existing buckets but could significantly impact the decision.

For each, write a bucket title (max 8 words, open question about facts).

Examples of auxiliary forces:
- Competitors are failing, creating market share opportunity
- A regulation just changed, constraining options
- A key supplier declared force majeure, changing the supply picture
- Government is under political pressure, affecting pricing freedom
- A parallel crisis in another market is affecting this one

If all major external forces are already covered, return empty. Do NOT add buckets that overlap with existing ones.

Return JSON: {"auxiliary_buckets": [{"id": 7, "title": "...", "rationale": "why this matters for the decision", "landscape_evidence": "what specific article/event triggered this"}]}""",
                "PROBLEM: {ps}\n\nEXISTING BUCKETS:\n{existing}\n\nLANDSCAPE SCAN:\n{landscape}".format(
                    ps=smart_ps, existing=existing, landscape=landscape_summary[:5000]
                ),
                model=SONNET
            )
            aux_buckets = aux.get("auxiliary_buckets", [])
            if aux_buckets:
                next_id = max(b["id"] for b in bucket_list) + 1
                for ab in aux_buckets:
                    ab["id"] = next_id
                    next_id += 1
                    bucket_list.append(ab)
                    print(f"    {C.YELLOW}+ {ab['id']}. {ab['title']} (auxiliary){C.R}")
                    if ab.get("landscape_evidence"):
                        print(f"      {C.DIM}Evidence: {ab['landscape_evidence'][:80]}{C.R}")
            else:
                print(f"    {C.DIM}No auxiliary forces needed{C.R}")
        except Exception:
            print(f"    {C.DIM}Auxiliary check skipped{C.R}")

    # ── MECE overlap validation ──
    if len(bucket_list) > 2:
        print(f"  {C.GREEN}Validating MECE — checking for bucket overlap...{C.R}")
        try:
            bucket_titles_for_check = "\n".join(f"{b['id']}. {b['title']}" for b in bucket_list)
            overlap_check = llm_json(
                """Check these buckets for MECE violations. For each PAIR of buckets, ask: "Could a single finding legitimately belong in both?" If yes, they overlap.

Flag overlapping pairs. For each, explain the overlap and suggest how to fix it (merge, split differently, or sharpen the boundary).

Also check: is there a major dimension of the problem NOT covered by any bucket? If yes, flag the gap.

Return JSON: {"overlaps": [{"bucket_a": 1, "bucket_b": 3, "overlap": "both cover competitive dynamics", "fix": "merge into one or split by..."}], "gaps": ["missing dimension: ..."], "is_mece": true/false}""",
                f"PROBLEM: {smart_ps}\n\nBUCKETS:\n{bucket_titles_for_check}",
                model=HAIKU
            )
            overlaps = overlap_check.get("overlaps", [])
            gaps = overlap_check.get("gaps", [])
            if overlaps:
                print(f"    {C.YELLOW}MECE WARNING: {len(overlaps)} overlapping pair(s) detected:{C.R}")
                for ov in overlaps:
                    print(f"      {C.YELLOW}Buckets {ov.get('bucket_a')} & {ov.get('bucket_b')}: {ov.get('overlap', '')[:80]}{C.R}")
                    print(f"        {C.DIM}Fix: {ov.get('fix', '')[:80]}{C.R}")
            if gaps:
                print(f"    {C.YELLOW}Coverage gaps: {len(gaps)}{C.R}")
                for g in gaps:
                    print(f"      {C.DIM}{g[:100]}{C.R}")
            if not overlaps and not gaps:
                print(f"    {C.GREEN}MECE validated — no overlaps or gaps{C.R}")
        except Exception:
            print(f"    {C.DIM}MECE check skipped{C.R}")

    print()

    # Step 2b: Generate sub-questions per bucket (parallel)
    print(f"  {C.GREEN}Generating sub-questions per bucket...{C.R}")

    def _gen_questions(b):
        bid = b["id"]
        title = b["title"]
        qs = llm_json(
            f"""Generate 5-8 specific research questions that answer: "{title}"

Generate 5-8 specific questions that would answer this. Each question asks about a FACT, NUMBER, or COMPARISON — never an action.

RULES:
- Short, plain language. No jargon.
- Each question can be answered with data, not opinions.
- BANNED words: "should", "must", "how to", "what steps", "prioritize", "strategy"
- GOOD: "How much revenue comes from per-seat pricing?"
- BAD: "What pricing strategy should be adopted?"

Return JSON: {{"questions": [{{"id": "{bid}.1", "question": "..."}}]}}""",
            "PROBLEM: {ps}\nBUCKET: {title}\nRATIONALE: {rat}".format(
                ps=smart_ps, title=title, rat=b.get("rationale", "")
            ),
            model=HAIKU, max_tokens=2048
        )
        return bid, title, qs.get("questions", [])

    sections = []
    with ThreadPoolExecutor(max_workers=min(len(bucket_list), 6)) as executor:
        futures = {executor.submit(_gen_questions, b): b for b in bucket_list}
        results_map = {}
        for future in as_completed(futures):
            b = futures[future]
            try:
                bid, title, questions = future.result()
                results_map[bid] = {"section_id": bid, "title": title, "rationale": b.get("rationale", ""), "questions": questions}
                print(f"    {C.GREEN}Bucket {bid}: {len(questions)} questions{C.R}")
            except Exception as e:
                print(f"    {C.RED}Bucket {b['id']} failed: {e}{C.R}")

    sections = [results_map[bid] for bid in sorted(results_map.keys())]

    result = {"smart_statement": smart_ps, "decision_sensitivity": sens, "sections": sections}
    result["original_input"] = ps_text
    if context:
        result["context"] = context

    # Save
    mece_dir = state.dir / "mece"
    mece_dir.mkdir(exist_ok=True)
    json.dump(result, open(mece_dir / "decomposition.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    state.set("mece_path", str(mece_dir / "decomposition.json"))

    # No separate audit needed — bucket titles enforced at generation, sub-questions on Haiku are simple
    result["smart_statement"] = smart_ps
    result["decision_sensitivity"] = sens
    result["original_input"] = ps_text
    if context:
        result["context"] = context
    print(f"  {C.GREEN}Audit + fix complete.{C.R}")

    json.dump(result, open(mece_dir / "decomposition.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    state.set("mece_path", str(mece_dir / "decomposition.json"))

    # Show buckets
    sections = result.get("sections", [])
    n_q = sum(len(s.get("questions", [])) for s in sections)
    bucket_lines = []
    for s in sections:
        title = s["title"].split(":")[0].strip() if ":" in s["title"] else s["title"]
        n = len(s.get("questions", []))
        bucket_lines.append(f"    {C.BOLD}{s['section_id']}.{C.R} {title} {C.DIM}({n}q){C.R}")

    summary = f"""  {C.BOLD}Basic Question:{C.R}
  {C.CYAN}{smart_ps[:400]}{C.R}

  {C.BOLD}Break point:{C.R} {sens[:200]}

  {C.BOLD}Decomposition ({len(sections)} buckets, {n_q} questions):{C.R}
{chr(10).join(bucket_lines)}"""

    return summary, result, autopilot


# ---------------------------------------------------------------------------
# STEP 1: Issue Tree
# ---------------------------------------------------------------------------

def step1(state, mece):
    sections = mece.get("sections", [])
    lines = []
    for s in sections:
        title = s["title"].split(":")[0].strip() if ":" in s["title"] else s["title"]
        n = len(s.get("questions", []))
        lines.append(f"    {C.BOLD}{s['section_id']}.{C.R} {title} {C.DIM}({n}q){C.R}")

    summary = f"  {C.BOLD}MECE Buckets ({len(sections)}):{C.R}\n" + "\n".join(lines)

    # Generate tree HTML
    tree_html = generate_tree_html(mece)
    tree_path = state.dir / "tree.html"
    tree_path.write_text(tree_html, encoding="utf-8")

    return summary, str(tree_path)


def generate_tree_html(mece):
    e = html_mod.escape
    ps = e(mece.get("smart_statement", "")[:200])
    branches = ""
    for s in mece.get("sections", []):
        sid = s["section_id"]
        title = s["title"].split(":")[0].strip() if ":" in s["title"] else s["title"]
        qs = ""
        for q in s.get("questions", []):
            qt = q["question"][:80]
            qs += f'<div class="leaf" title="{e(q["question"])}"><span class="lid">{q["id"]}</span>{e(qt)}</div>\n'
        branches += f'<div class="branch"><div class="bnode"><span class="bnum">{sid}</span>{e(title)}</div><div class="leaves">{qs}</div></div>\n'

    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Issue Tree</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Inter',sans-serif;padding:40px 24px;overflow-x:auto}}
.tree{{display:flex;align-items:flex-start;min-width:max-content}}
.root{{flex-shrink:0;width:220px;background:#0a0a0a;color:#fff;padding:16px;border-radius:8px;font:400 11px/1.5 'Inter'}}
.root strong{{color:#ff3b3b;font:700 9px/1 'JetBrains Mono';letter-spacing:1px;text-transform:uppercase;display:block;margin-bottom:6px}}
.conn{{width:32px;display:flex;align-items:center}}.conn::after{{content:'';width:100%;height:2px;background:#d1d5db}}
.branches{{display:flex;flex-direction:column;gap:3px;position:relative}}.branches::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:#d1d5db}}
.branch{{display:flex;align-items:flex-start;position:relative}}.branch::before{{content:'';position:absolute;left:0;top:15px;width:12px;height:2px;background:#d1d5db}}
.bnode{{flex-shrink:0;margin-left:12px;padding:6px 12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:5px;font:600 11px/1.4 'Inter';color:#1e40af;cursor:default;white-space:nowrap}}
.bnum{{font:800 10px/1 'JetBrains Mono';color:#2563eb;margin-right:4px}}
.leaves{{display:flex;flex-direction:column;gap:2px;margin-left:0;position:relative}}.leaves::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:#e5e7eb}}
.leaf{{margin-left:12px;padding:4px 10px;background:#f9fafb;border:1px solid #f0f0f0;border-radius:4px;font:400 10px/1.4 'Inter';color:#555;white-space:nowrap;max-width:340px;overflow:hidden;text-overflow:ellipsis;position:relative}}
.leaf::before{{content:'';position:absolute;left:-12px;top:11px;width:12px;height:2px;background:#e5e7eb}}
.leaf:hover{{background:#fef3c7;white-space:normal;max-width:500px;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
.lid{{font:700 9px/1 'JetBrains Mono';color:#2563eb;margin-right:3px}}
</style></head><body>
<div class="tree"><div class="root"><strong>Problem Statement</strong>{ps}</div><div class="conn"></div><div class="branches">{branches}</div></div>
</body></html>'''


# ---------------------------------------------------------------------------
# STEP 1.5: 80/20 Tiering
# ---------------------------------------------------------------------------

def tier_questions(state, mece):
    """Score every sub-question against the decision sensitivity break point. Tier 1/2/3."""
    print(f"  {C.GREEN}Applying 80/20 prioritization...{C.R}")

    ps = mece.get("smart_statement", "")
    sens = mece.get("decision_sensitivity", "")
    sections = mece.get("sections", [])

    mece_for_prompt = json.dumps(
        [{"section_id": s["section_id"], "title": s["title"], "questions": s.get("questions", [])} for s in sections],
        indent=2, ensure_ascii=False
    )

    tiered = llm_json(
        f"""You are a senior engagement manager prioritizing research effort. Today is {TODAY_STR}.

PROBLEM STATEMENT: {ps}
DECISION SENSITIVITY (break point): {sens}

For EVERY sub-question across all buckets, assign a tier:

TIER 1 — MUST RESEARCH (20% of questions that drive 80% of the answer)
  Rule: Answering this question could FLIP the recommendation. If we get this wrong, the entire analysis is wrong.
  Research depth: Deep. Multiple sources. Specific numbers required.

TIER 2 — SHOULD RESEARCH (important context, won't flip the answer alone)
  Rule: This question adds important nuance or confidence, but getting it wrong won't reverse the recommendation.
  Research depth: Standard. 2-3 sentences. General magnitudes sufficient.

TIER 3 — EXTRAPOLATE (can be inferred from Tier 1/2 findings)
  Rule: The answer to this question can be reasonably derived from Tier 1 or Tier 2 answers without independent research.
  Research depth: One sentence. State what Tier 1/2 finding it extrapolates from.

THE TEST: For each question, ask: "If the answer to this question were the OPPOSITE of what I expect, would the recommendation change?" If YES -> Tier 1. If MAYBE -> Tier 2. If NO -> Tier 3.

Return JSON:
{{"tiers": [
  {{"question_id": "1.1", "tier": 1, "reason": "..."}}
],
"summary": {{"tier_1": 0, "tier_2": 0, "tier_3": 0}}}}""",
        f"MECE DECOMPOSITION:\n{mece_for_prompt}\n\nTier every question.",
        model=HAIKU, max_tokens=8192
    )

    # Merge tiers back into mece
    tiers_list = tiered.get("tiers", [])
    if not isinstance(tiers_list, list):
        tiers_list = []
    tier_map = {}
    for t in tiers_list:
        if isinstance(t, dict) and "question_id" in t:
            tier_map[t["question_id"]] = t
    for s in sections:
        for q in s.get("questions", []):
            t = tier_map.get(q["id"], {})
            q["tier"] = t.get("tier", 2) if isinstance(t, dict) else 2
            q["tier_reason"] = t.get("reason", "") if isinstance(t, dict) else ""

    # Save
    tier_dir = state.dir / "tiers"
    tier_dir.mkdir(exist_ok=True)
    json.dump(tiered, open(tier_dir / "tiers.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    state.set("tiers_path", str(tier_dir / "tiers.json"))

    summary = tiered.get("summary", {})
    t1 = summary.get("tier_1", 0)
    t2 = summary.get("tier_2", 0)
    t3 = summary.get("tier_3", 0)
    print(f"  {C.GREEN}Tiering: {t1} Tier 1 (deep), {t2} Tier 2 (standard), {t3} Tier 3 (extrapolate){C.R}")

    return tiered


# ---------------------------------------------------------------------------
# STEP 2: Research
# ---------------------------------------------------------------------------

def step2_research_brief(state, mece):
    """Generate the research brief — per-bucket, parallelized."""
    print(f"  {C.GREEN}Generating research requirements...{C.R}")

    ps = mece.get("smart_statement", "")
    sections = mece.get("sections", [])
    research_dir = state.dir / "research"
    research_dir.mkdir(exist_ok=True)

    audience = state.get("audience", "")

    # Step 1: Quick Haiku call to infer client context (small, fast)
    print(f"    {C.DIM}Inferring client context...{C.R}")
    client_info = llm_json(
        "Infer the client organization from the problem statement and audience. Return JSON.",
        f"PROBLEM STATEMENT: {ps}\nAUDIENCE: {audience}\n\nReturn JSON: {{\"client_context\": \"description of client and what internal data systems they likely have\", \"client_name\": \"inferred name\"}}",
        model=HAIKU, max_tokens=1024
    )
    client_ctx = client_info.get("client_context", "")

    # Step 2: Per-bucket research requirements (parallel Haiku calls)
    def _brief_one_bucket(s):
        sid = s["section_id"]
        title = s["title"]
        questions = json.dumps(s.get("questions", []), indent=2, ensure_ascii=False)
        bucket_brief = llm_json(
            f"""You are a research director. Today is {TODAY_STR}.
CLIENT: {client_ctx}

For this ONE bucket, identify what data/evidence is needed to answer the sub-questions.

For each item:
- SOURCE TYPE: PUBLIC (reports, databases, filings) | PROPRIETARY (internal company data) | EXPERT (interviews, specialist) | FIELD (primary research)
- PRIORITY: MUST-HAVE (blocks analysis) | NICE-TO-HAVE (improves precision)
- For PROPRIETARY: name the team/system that has it, exact format needed
- For PUBLIC: name specific databases, reports, URLs
- client_ask: specific request to client team (e.g., "Can your finance team provide...")

Return JSON:
{{"bucket_id": {sid}, "bucket_title": "{title}", "items": [
  {{"id": "R{sid}.1", "question_id": "...", "data_needed": "...", "source_type": "PUBLIC", "priority": "MUST-HAVE", "suggested_sources": "...", "why_needed": "...", "client_ask": "..."}}
]}}""",
            f"PROBLEM STATEMENT: {ps}\n\nBUCKET {sid}: {title}\nQUESTIONS:\n{questions}\n\nGenerate research requirements for this bucket. Be concise — max 5 items.",
            model=HAIKU, max_tokens=4096
        )
        return sid, bucket_brief

    print(f"    {C.DIM}Generating requirements for {len(sections)} buckets in parallel...{C.R}")
    bucket_briefs = {}
    with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
        futures = {executor.submit(_brief_one_bucket, s): s for s in sections}
        for future in as_completed(futures):
            s = futures[future]
            try:
                sid, bb = future.result()
                bucket_briefs[sid] = bb
                n_items = len(bb.get("items", []))
                print(f"      {C.GREEN}Bucket {sid}: {n_items} items{C.R}")
            except Exception as e:
                print(f"      {C.RED}Bucket {s['section_id']} failed: {e}{C.R}")

    # Assemble the full brief
    brief = {
        "client_context": client_ctx,
        "research_requirements": [bucket_briefs[sid] for sid in sorted(bucket_briefs.keys())]
    }

    # Save
    json.dump(brief, open(research_dir / "research_brief.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    state.set("research_brief_path", str(research_dir / "research_brief.json"))

    # Write human-readable checklist
    client_ctx = brief.get("client_context", "")
    checklist_lines = [f"# Research Requirements\n", f"**Problem Statement:** {ps}\n", f"**Generated:** {TODAY_STR}\n"]
    if client_ctx:
        checklist_lines.append(f"**Client Context:** {client_ctx}\n")
    total_must = 0
    total_nice = 0
    total_proprietary = 0
    for bucket in brief.get("research_requirements", []):
        checklist_lines.append(f"\n## Bucket {bucket['bucket_id']}: {bucket.get('bucket_title', '')}\n")
        for item in bucket.get("items", []):
            pri = item.get("priority", "?")
            src = item.get("source_type", "?")
            marker = "[ ]"
            if pri == "MUST-HAVE":
                total_must += 1
            else:
                total_nice += 1
            if src in ("PROPRIETARY", "EXPERT", "FIELD"):
                total_proprietary += 1
            checklist_lines.append(f"- {marker} **{item['id']}** [{pri}] [{src}]: {item['data_needed']}")
            if item.get("client_ask"):
                checklist_lines.append(f"  - **Ask:** {item['client_ask']}")
            checklist_lines.append(f"  - Sources: {item.get('suggested_sources', 'N/A')}")
            checklist_lines.append(f"  - Why: {item.get('why_needed', '')}")

    checklist_lines.insert(3 + (1 if client_ctx else 0), f"**Total: {total_must} must-have, {total_nice} nice-to-have, {total_proprietary} need client data**\n")
    checklist_path = research_dir / "research_checklist.md"
    checklist_path.write_text("\n".join(checklist_lines), encoding="utf-8")

    print(f"  {C.GREEN}Research brief: {total_must} must-have, {total_nice} nice-to-have items{C.R}")
    return brief, total_must, total_nice


def _broad_research_scan(problem_statement, context, state):
    """Two-tier landscape scan: snippets first (fast), then targeted article depth (smart)."""
    try:
        from ddgs import DDGS
    except ImportError:
        return {"summary": "", "articles": [], "events": []}

    import requests as _req
    import re as _re


    fetch_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    def _fetch_one(url):
        try:
            resp = _req.get(url, timeout=15, headers=fetch_headers)
            if resp.status_code == 200:
                text = _re.sub(r'<script.*?</script>', '', resp.text, flags=_re.DOTALL)
                text = _re.sub(r'<style.*?</style>', '', text, flags=_re.DOTALL)
                text = _re.sub(r'<nav.*?</nav>', '', text, flags=_re.DOTALL)
                text = _re.sub(r'<[^>]+>', ' ', text)
                text = _re.sub(r'\s+', ' ', text).strip()
                if len(text) > 200:
                    return f"[From {url[:60]}]:\n{text[:5000]}"
        except Exception:
            pass
        return None

    # ============================================================
    # TIER 1: Fast snippet sweep — wide net, no article fetching
    # ============================================================
    print(f"    {C.DIM}TIER 1: Fast snippet sweep...{C.R}")

    queries_result = llm_json(
        """Generate 12 broad web search queries to understand the FULL LANDSCAPE of this problem before decomposing it.

Cover these angles:
- What is happening right now (breaking news, recent events)
- What other stakeholders in this ecosystem are doing — AT LEAST 2 queries about other players (competitors, suppliers, customers, partners, regulators, adjacent industries) who are affected by or responding to the same situation
- What analysts, experts, or commentators are saying
- What the financial or operational impact is
- What regulatory, legal, or policy dimensions exist
- What historical precedent exists for similar situations
- Who BENEFITS and who LOSES — search for second-order effects and unintended consequences

IMPORTANT: The best issue tree decompositions come from understanding the FULL ecosystem around a problem, not just the focal entity. Every problem exists in a web of actors — search for what is happening to ALL of them.

Return JSON: {"queries": ["query 1", ...]}""",
        f"PROBLEM: {problem_statement}\nCONTEXT: {context}",
        model=HAIKU, max_tokens=1024
    )
    queries = queries_result.get("queries", [problem_statement[:80]])

    all_snippets = []
    all_urls = []
    seen_urls = set()
    events = []

    with DDGS() as ddgs:
        for q in queries[:12]:
            time.sleep(1.0)
            try:
                for r in ddgs.news(q, max_results=5, timelimit="m"):
                    all_snippets.append(f"[{r.get('date', '')[:10]}] {r.get('title', '')}: {r.get('body', '')[:300]}")
                    events.append({"title": r.get("title", ""), "date": r.get("date", "")[:10], "snippet": r.get("body", "")[:200], "source": r.get("source", "")})
            except Exception:
                pass
            try:
                for r in ddgs.text(q, max_results=5, timelimit="y"):
                    all_snippets.append(f"{r.get('title', '')}: {r.get('body', '')[:300]}")
                    url = r.get("href", "")
                    if url and url.startswith("http") and url not in seen_urls and not any(d in url for d in BLOCKED_DOMAINS):
                        seen_urls.add(url)
                        all_urls.append(url)
            except Exception:
                pass

    print(f"    {C.DIM}{len(all_snippets)} snippets collected. Summarizing...{C.R}")

    # Tier 1 summary — Haiku on snippets only (fast + cheap)
    snippets_text = "\n".join(f"- {s}" for s in all_snippets[:60])
    tier1_summary = llm(
        f"""You have {len(all_snippets)} search snippets about a strategic problem. Write a 1-page landscape overview.

Focus on:
1. What is happening right now (key events, dates, facts)
2. Who are the main players and what is each doing
3. Who else is affected — who benefits, who loses, who is vulnerable
4. What surprised you or contradicts conventional wisdom

Then at the end, list 4-6 ANGLES THAT NEED DEPTH — specific topics where the snippets hint at something important but don't have enough detail. These will be used to target deeper article research.

Format the angles section as:
## ANGLES NEEDING DEPTH
1. [angle]: [why it matters, what's missing]
2. ...

Write as facts, not opinions.""",
        f"PROBLEM: {problem_statement}\n\nSNIPPETS ({len(all_snippets)}):\n{snippets_text}",
        model=HAIKU, max_tokens=4096
    )

    print(f"    {C.GREEN}Tier 1 complete. Identifying depth targets...{C.R}")

    # ============================================================
    # TIER 2: Targeted depth — fetch articles for angles that matter
    # ============================================================
    print(f"    {C.DIM}TIER 2: Targeted article depth...{C.R}")

    depth_queries = llm_json(
        """You have a landscape overview with angles that need deeper research. Generate 5-6 TARGETED search queries to find detailed articles on those specific angles.

Each query should be specific enough to find in-depth articles, not generic news. Include entity names, technical terms, or specific aspects.

Return JSON: {"depth_queries": ["query 1", ...]}""",
        f"PROBLEM: {problem_statement}\n\nLANDSCAPE OVERVIEW:\n{tier1_summary}",
        model=HAIKU, max_tokens=512
    )
    dq = depth_queries.get("depth_queries", [])

    # Search for depth articles
    depth_urls = []
    with DDGS() as ddgs2:
        for q in dq[:6]:
            time.sleep(1.0)
            try:
                for r in ddgs2.text(q, max_results=5, timelimit="y"):
                    url = r.get("href", "")
                    if url and url.startswith("http") and url not in seen_urls and not any(d in url for d in BLOCKED_DOMAINS):
                        seen_urls.add(url)
                        depth_urls.append(url)
            except Exception:
                pass
            try:
                for r in ddgs2.news(q, max_results=3, timelimit="m"):
                    all_snippets.append(f"[{r.get('date', '')[:10]}] {r.get('title', '')}: {r.get('body', '')[:300]}")
                    events.append({"title": r.get("title", ""), "date": r.get("date", "")[:10], "snippet": r.get("body", "")[:200], "source": r.get("source", "")})
            except Exception:
                pass

    # Parallel fetch — only the depth articles
    print(f"    {C.DIM}Fetching {min(len(depth_urls), 15)} targeted articles...{C.R}")
    full_articles = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_fetch_one, u) for u in depth_urls[:15]]
        for f in as_completed(futures):
            result = f.result()
            if result and len(full_articles) < 12:
                full_articles.append(result)

    print(f"    {C.DIM}{len(full_articles)} articles fetched. Final synthesis...{C.R}")

    # Final synthesis — Sonnet combines Tier 1 overview + Tier 2 depth articles
    articles_text = "\n\n".join(full_articles[:12])
    summary = llm(
        f"""You have two inputs:
1. A landscape overview (from search snippets) — gives you the broad picture
2. {len(full_articles)} in-depth articles on specific angles — gives you the detail

Combine them into a 2-3 page LANDSCAPE SUMMARY.

Focus on:
1. What is actually happening right now (facts, events, dates)
2. Who are ALL the key players and what is each doing
3. Who else is affected — who is VULNERABLE, who BENEFITS, what gaps or opportunities are opening
4. What second-order effects exist that the decision-maker might not see
5. What surprised you — things that contradict conventional wisdom

This summary will be used to GENERATE the issue tree decomposition, so highlight every distinct angle that deserves its own research bucket. Be specific — name entities, cite numbers, give dates.

Write as facts with sources, not opinions.""",
        f"PROBLEM: {problem_statement}\n\nLANDSCAPE OVERVIEW (from snippets):\n{tier1_summary}\n\nIN-DEPTH ARTICLES ({len(full_articles)}):\n{articles_text}"
    )

    # Save
    scan_dir = state.dir / "landscape_scan"
    scan_dir.mkdir(exist_ok=True)
    scan_data = {"summary": summary, "articles": full_articles, "snippets": all_snippets, "events": events, "queries": queries, "depth_queries": dq, "tier1_summary": tier1_summary}
    json.dump(scan_data, open(scan_dir / "landscape.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    Path(scan_dir / "landscape_summary.md").write_text(f"# Landscape Scan\n\n{summary}", encoding="utf-8")
    state.set("landscape_path", str(scan_dir / "landscape.json"))
    state.set("current_events_path", str(scan_dir / "landscape.json"))

    print(f"    {C.GREEN}Landscape scan complete: {len(all_snippets)} snippets, {len(full_articles)} depth articles{C.R}")
    return scan_data


def _web_search_all_buckets(topic, sections, current_events=None):
    """Phase 1: Do ALL web searches for ALL buckets SEQUENTIALLY. Returns search data per bucket."""
    try:
        from ddgs import DDGS
    except ImportError:
        return {}

    import requests as _req
    import re as _re

    search_data = {}
    _total_queries = 0
    _empty_queries = 0

    for s in sections:
        sid = s["section_id"]
        title = s["title"]
        all_questions = "\n".join(f"- {q['id']}: {q['question']}" for q in s.get("questions", []))

        print(f"      Searching bucket {sid}: {title[:40]}...")

        # Generate search queries — target open, technical sources
        try:
            search_queries = llm_json(
                """Generate 10 search queries to find OPEN, FETCHABLE sources with real data.

TARGET THESE SOURCE TYPES (they don't block scrapers):
- Government data: EIA, IEA, PPAC, OPEC, central banks, census, SEC EDGAR
- Industry bodies: IATA, API, FIPI, trade associations
- Think tanks: Brookings, CSIS, IISD, Carnegie, McKinsey Global Institute
- Company investor relations: annual reports, 10-K, earnings transcripts on open sites
- Wikipedia for baseline facts
- Industry blogs, analysis sites (oilprice.com, rigzone.com, techcrunch.com, etc.)
- Academic/research: SSRN, NBER, arXiv
- Open news: AP News, BBC, Al Jazeera, CNBC, India Times

AVOID: reuters.com, ft.com, wsj.com, bloomberg.com, nytimes.com (all paywalled)

Return JSON: {"queries": ["query 1", "query 2"]}""",
                f"TOPIC: {topic}\nBUCKET: {title}\n\nQUESTIONS:\n{all_questions}",
                model=HAIKU, max_tokens=1024
            )
            queries = search_queries.get("queries", [])
        except Exception:
            queries = [f"{topic} {title} site:wikipedia.org", f"{topic} {title} data report"]

        # Deep queries — additional specific searches
        try:
            dq = llm_json(
                "Generate 5 more search queries for detailed data. Return JSON: {\"queries\": [\"query\"]}",
                f"TOPIC: {topic}\nBUCKET: {title}",
                model=HAIKU, max_tokens=1024
            )
            all_queries = queries + dq.get("queries", [])
        except Exception:
            all_queries = queries

        # Search — sequential, throttled
        snippets = []
        article_urls = []
        seen_urls = set()

        with DDGS() as ddgs:
            for q in all_queries[:10]:
                _total_queries += 1
                time.sleep(1.5)
                got_results = False
                try:
                    news = list(ddgs.news(q, max_results=3, timelimit="m"))
                    for r in news:
                        snippets.append(f"[{r.get('date', '')[:10]}] {r.get('title', '')}: {r.get('body', '')[:300]} (source: {r.get('source', '')})")
                        got_results = True
                except Exception:
                    pass
                try:
                    web = list(ddgs.text(q, max_results=3, timelimit="y"))
                    for r in web:
                        snippets.append(f"{r.get('title', '')}: {r.get('body', '')[:300]} (source: {r.get('href', '')})")
                        url = r.get("href", "")
                        if url and url.startswith("http") and url not in seen_urls:
                            seen_urls.add(url)
                            article_urls.append(url)
                        got_results = True
                except Exception:
                    pass
                if not got_results:
                    _empty_queries += 1

        # Fetch full articles — skip paywalled sites

        fetchable_urls = [u for u in article_urls if not any(d in u for d in BLOCKED_DOMAINS)]
        # Put blocked URLs at the end as fallback
        all_fetch_urls = fetchable_urls + [u for u in article_urls if u not in fetchable_urls]

        full_articles = []
        fetch_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        for url in all_fetch_urls[:10]:  # Try 10 URLs to get 5 articles
            if len(full_articles) >= 5:
                break
            try:
                time.sleep(1)
                resp = _req.get(url, timeout=20, headers=fetch_headers, allow_redirects=True)
                if resp.status_code == 200:
                    text = _re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=_re.DOTALL)
                    text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
                    text = _re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=_re.DOTALL)
                    text = _re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=_re.DOTALL)
                    text = _re.sub(r'<[^>]+>', ' ', text)
                    text = _re.sub(r'\s+', ' ', text).strip()
                    # Take from start — nav/header already stripped by HTML tag removal above
                    if len(text) > 200:
                        text = text[:5000]
                        full_articles.append(f"[Article from {url[:80]}]:\n{text}")
            except Exception:
                pass

        # If <3 articles, do a rescue search targeting open sources
        if len(full_articles) < 3:
            rescue_queries = [
                f"{topic} {title} site:wikipedia.org",
                f"{topic} {title} site:gov.in OR site:eia.gov OR site:iea.org",
                f"{topic} {title} analysis blog",
            ]
            with DDGS() as ddgs:
                for q in rescue_queries:
                    if len(full_articles) >= 3:
                        break
                    time.sleep(1.5)
                    try:
                        web = list(ddgs.text(q, max_results=3))
                        for r in web:
                            url = r.get("href", "")
                            if url and url not in seen_urls and not any(d in url for d in BLOCKED_DOMAINS):
                                seen_urls.add(url)
                                try:
                                    time.sleep(1)
                                    resp = _req.get(url, timeout=15, headers=fetch_headers)
                                    if resp.status_code == 200:
                                        text = _re.sub(r'<script.*?</script>', '', resp.text, flags=_re.DOTALL)
                                        text = _re.sub(r'<style.*?</style>', '', text, flags=_re.DOTALL)
                                        text = _re.sub(r'<[^>]+>', ' ', text)
                                        text = _re.sub(r'\s+', ' ', text).strip()
                                        if len(text) > 200:
                                            text = text[:5000]
                                            full_articles.append(f"[Article from {url[:80]}]:\n{text}")
                                except Exception:
                                    pass
                    except Exception:
                        pass

        print(f"      Bucket {sid}: {len(snippets)} snippets, {len(full_articles)} articles")

        search_data[sid] = {
            "queries": all_queries,
            "snippets": snippets,
            "full_articles": full_articles,
        }

    # Warn if search failure rate is high
    if _total_queries > 0 and _empty_queries > 0:
        fail_rate = _empty_queries / _total_queries
        if fail_rate > 0.3:
            print(f"  {C.YELLOW}WARNING: {_empty_queries}/{_total_queries} search queries returned zero results ({fail_rate:.0%}).{C.R}")
            print(f"  {C.YELLOW}  Web search may be rate-limited. Findings may have significant gaps.{C.R}")
            # Store flag so downstream steps can lower confidence
            search_data["_search_failure_rate"] = fail_rate

    return search_data


def _synthesize_one_bucket(topic, s, search_data, human_data, research_dir, current_events=None):
    """Phase 2: Synthesize research for one bucket from pre-fetched search data. Called in parallel."""
    sid = s["section_id"]
    title = s["title"]
    all_questions = "\n".join(f"- {q['id']}: {q['question']}" for q in s.get("questions", []))

    data = search_data.get(sid, {})
    snippets = data.get("snippets", [])
    full_articles = data.get("full_articles", [])
    queries = data.get("queries", [])

    snippets_text = "\n".join(f"- {sn}" for sn in snippets[:30]) if snippets else "(No web results found)"
    articles_text = "\n\n".join(full_articles) if full_articles else ""

    events_text = ""
    if current_events:
        events_text = "\n\nCURRENT EVENTS:\n" + "\n".join(f"- [{e.get('date','')}] {e.get('title','')}: {e.get('snippet','')}" for e in current_events[:8])

    human_text = ""
    if human_data:
        human_text = "\n\nHUMAN-PROVIDED DATA:\n" + "\n".join(f"From {d['file']}:\n{d['findings']}" for d in human_data)

    # Single synthesis call with ALL data — snippets + full articles + events
    result = llm(
        f"""You are a research analyst. Answer the questions below using the web search data provided.

TWO TYPES OF INFORMATION — use both, label clearly:

HARD FACTS (from search snippets and full articles below):
- Numbers, dates, events, quotes
- MUST cite source: "(per Reuters, March 2026)", "(per company 10-K FY25)"
- Prefer data from FULL ARTICLES over snippets — articles have more detail

ANALYTICAL REASONING (from your knowledge):
- Patterns, principles, causal logic, industry frameworks
- Tag with [LLM reasoning] at the end of each reasoning statement
- NEVER present reasoning as sourced fact

RESEARCH DEPTH:
- Tier 1 questions: detailed, multiple sourced data points + reasoning. 4-6 sentences.
- Tier 2 questions: standard, best available source. 2-3 sentences.
- Tier 3 questions: extrapolate from Tier 1/2. 1 sentence.

When no source answers a question, do NOT write "DATA GAP" as a label. Instead, state what is known and note the uncertainty naturally: "Exact volumes are not publicly disclosed, but industry estimates suggest..." or "This data point requires company-specific reporting that is not publicly available." Write like a consultant, not a process log.""",
        f"TOPIC: {topic}\nBUCKET: {title}\n\nQUESTIONS:\n{all_questions}\n\nWEB SEARCH SNIPPETS ({len(snippets)}):\n{snippets_text}\n\nFULL ARTICLES ({len(full_articles)}):\n{articles_text}{events_text}{human_text}\n\nAnswer each question. Cite sources."
    )

    brief_path = research_dir / f"bucket_{sid:02d}.md"
    brief_path.write_text(f"# Bucket {sid}: {title}\n\nSearch queries: {len(queries)}\nSnippets: {len(snippets)}\nFull articles: {len(full_articles)}\n\n{result}", encoding="utf-8")
    return sid, result


def step2_execute_research(state, mece, brief, human_data=None):
    """Execute research using live web search + article fetch + any human-provided data. Parallel across buckets."""
    sections = mece.get("sections", [])
    research_dir = state.dir / "research"
    research_dir.mkdir(exist_ok=True)
    topic = state.get("topic", "")

    print(f"  {C.DIM}Running {len(sections)} buckets in parallel...{C.R}")
    all_briefs = {}
    with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
        futures = {
            executor.submit(_research_one_bucket, topic, s, brief, human_data, research_dir): s
            for s in sections
        }
        for future in as_completed(futures):
            s = futures[future]
            try:
                sid, result = future.result()
                all_briefs[sid] = result
                print(f"    {C.GREEN}Bucket {sid} done{C.R}")
            except Exception as e:
                print(f"    {C.RED}Bucket {s['section_id']} failed: {e}{C.R}")

    # Compile in order
    compiled = "\n\n---\n\n".join(all_briefs[sid] for sid in sorted(all_briefs.keys()))
    (research_dir / "compiled.md").write_text(compiled, encoding="utf-8")
    state.set("research_path", str(research_dir / "compiled.md"))
    print(f"  {C.GREEN}Research done: {len(all_briefs)} briefs (parallel){C.R}")
    return compiled, all_briefs


def research_input_prompt(state, brief, total_must, total_nice, autopilot=False):
    """Show research options and get human choice. Returns (choice, selected_items)."""
    research_dir = state.dir / "research"
    input_dir = state.dir / "inputs" / "research"
    input_dir.mkdir(parents=True, exist_ok=True)

    # Count proprietary items
    proprietary_items = []
    for bucket in brief.get("research_requirements", []):
        for item in bucket.get("items", []):
            if item.get("source_type") in ("PROPRIETARY", "EXPERT", "FIELD"):
                proprietary_items.append(item)

    client_ctx = brief.get("client_context", "")

    print(f"\n  {C.BOLD}RESEARCH INPUT{C.R}")
    print(f"  {C.DIM}{'_'*50}{C.R}\n")
    if client_ctx:
        print(f"  {C.DIM}Client: {client_ctx[:150]}{C.R}\n")
    print(f"  The analysis requires {C.BOLD}{total_must} must-have{C.R} and {total_nice} nice-to-have research items.")
    if proprietary_items:
        print(f"  {C.YELLOW}{len(proprietary_items)} items need data from you or your client.{C.R}")
    print(f"  Research checklist saved to: {C.BLUE}{research_dir / 'research_checklist.md'}{C.R}\n")

    if autopilot:
        print(f"  {C.DIM}[autopilot] proceeding with public knowledge{C.R}\n")
        return "A", []

    print(f"  How would you like to proceed?\n")
    print(f"    {C.BOLD}A{C.R}  Proceed with public knowledge")
    print(f"       {C.DIM}Fastest. Proprietary data flagged as LOW confidence.{C.R}")
    print(f"    {C.BOLD}B{C.R}  I have research to upload (covers everything)")
    print(f"       {C.DIM}Drop files in: {input_dir}{C.R}")
    if proprietary_items:
        print(f"    {C.BOLD}D{C.R}  I can provide some items (selective)")
        print(f"       {C.DIM}Review what's needed, provide what you have, skip the rest{C.R}")
    print(f"    {C.BOLD}C{C.R}  Let me go gather this (save & quit)")
    print(f"       {C.DIM}Review the checklist, gather data, resume later with --resume{C.R}")
    print()

    valid = ["A", "B", "C"] + (["D"] if proprietary_items else [])
    while True:
        try:
            choice = input(f"  {C.YELLOW}Choose [{'/'.join(valid)}]: {C.R}").strip().upper()
        except (EOFError, KeyboardInterrupt):
            choice = "C"
        if choice in valid:
            break
        print(f"  {C.RED}Please enter {'/'.join(valid)}{C.R}")

    if choice != "D":
        return choice, []

    # ── Selective input: show proprietary items, let user pick ──
    print(f"\n  {C.BOLD}DATA YOU CAN PROVIDE{C.R}")
    print(f"  {C.DIM}{'_'*50}{C.R}\n")
    print(f"  {C.DIM}For each item: type the data directly, 'skip' to use public knowledge,{C.R}")
    print(f"  {C.DIM}or 'file' if you've dropped a file covering this item.{C.R}\n")

    provided = []
    for item in proprietary_items:
        pri_tag = f"{C.RED}MUST-HAVE{C.R}" if item.get("priority") == "MUST-HAVE" else f"{C.DIM}NICE-TO-HAVE{C.R}"
        print(f"  {C.BOLD}{item['id']}{C.R} [{pri_tag}]")
        if item.get("client_ask"):
            print(f"  {C.CYAN}{item['client_ask']}{C.R}")
        else:
            print(f"  {item['data_needed']}")
        print()

        try:
            resp = input(f"  {C.YELLOW}{item['id']} > {C.R}").strip()
        except (EOFError, KeyboardInterrupt):
            resp = "skip"

        if resp.lower() == "skip" or not resp:
            print(f"  {C.DIM}Skipped — will use public knowledge{C.R}\n")
        elif resp.lower() == "file":
            print(f"  {C.GREEN}Will extract from uploaded files{C.R}\n")
            provided.append({"id": item["id"], "source": "file"})
        else:
            print(f"  {C.GREEN}Got it{C.R}\n")
            provided.append({"id": item["id"], "source": "direct", "data": resp})

    # Save provided data
    if provided:
        json.dump(provided, open(research_dir / "human_inputs.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    n_provided = len(provided)
    n_skipped = len(proprietary_items) - n_provided
    print(f"\n  {C.GREEN}Provided: {n_provided}, Skipped: {n_skipped}{C.R}")
    print(f"  {C.DIM}Proceeding with your data + public knowledge for the rest{C.R}\n")

    return "D", provided


# ---------------------------------------------------------------------------
# STEP 3: Working Document
# ---------------------------------------------------------------------------

def _working_doc_one_bucket(topic, audience, s, research_by_bucket, research, state_dir, human_context):
    """Generate working document for a single bucket. Called in parallel."""
    sid = s["section_id"]
    title = s["title"]
    questions = "\n".join(f"- {q['id']}: {q['question']}" for q in s.get("questions", []))

    # Use per-bucket research if available
    if research_by_bucket and sid in research_by_bucket:
        bucket_research = research_by_bucket[sid]
    else:
        bucket_file = state_dir / "research" / f"bucket_{sid:02d}.md"
        if bucket_file.exists():
            bucket_research = bucket_file.read_text(encoding="utf-8")
        else:
            bucket_research = research[:8000]

    answer = llm(
        "You are a senior analyst writing a strategic working document. For each question: give a BOTTOM LINE (1-2 sentences), then supporting detail. Where data is unavailable, state what is known and note the uncertainty naturally — do not use labels like 'DATA GAP' or 'confidence: HIGH'. Write like a consultant presenting to a client, not an internal process log. CRITICAL: Preserve all '(per source, date)' citations and '[LLM reasoning]' tags from the research. Never strip source attributions.",
        f"TOPIC: {topic}\nAUDIENCE: {audience}\n\nBUCKET: {title}\n\nQUESTIONS:\n{questions}\n\nRESEARCH:\n{bucket_research}{human_context}\n\nAnswer every question."
    )
    wd_dir = state_dir / "working_doc"
    (wd_dir / f"bucket_{sid:02d}.md").write_text(f"# {title}\n\n{answer}", encoding="utf-8")
    return sid, title, answer


def step3(state, mece, research, research_by_bucket=None):
    print(f"  {C.GREEN}Generating working document...{C.R}")

    sections = mece.get("sections", [])
    wd_dir = state.dir / "working_doc"
    wd_dir.mkdir(exist_ok=True)

    # Include human inputs from state
    human_answers = [h for h in state.data.get("human_inputs", []) if h["type"] == "answer"]
    human_context = ""
    if human_answers:
        human_context = "\n\nHUMAN-PROVIDED ANSWERS (treat as HIGH confidence):\n" + "\n".join(f"- {h['content']}" for h in human_answers)

    topic = state.get("topic", "")
    audience = state.get("audience", "")

    print(f"  {C.DIM}Running {len(sections)} buckets in parallel...{C.R}")
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
        futures = {
            executor.submit(_working_doc_one_bucket, topic, audience, s, research_by_bucket, research, state.dir, human_context): s
            for s in sections
        }
        for future in as_completed(futures):
            s = futures[future]
            try:
                sid, title, answer = future.result()
                results[sid] = (title, answer)
                print(f"    {C.GREEN}Bucket {sid} done{C.R}")
            except Exception as e:
                print(f"    {C.RED}Bucket {s['section_id']} failed: {e}{C.R}")

    # Compile in order
    wd_parts = [f"## Bucket {sid}: {results[sid][0]}\n\n{results[sid][1]}" for sid in sorted(results.keys())]
    full_wd = f"# Working Document\n\n**Topic:** {topic}\n**Date:** {TODAY_STR}\n\n" + "\n\n---\n\n".join(wd_parts)
    wd_path = wd_dir / "working_document.md"
    wd_path.write_text(full_wd, encoding="utf-8")
    state.set("wd_path", str(wd_path))
    print(f"  {C.GREEN}Working document done: {len(full_wd):,} chars (parallel){C.R}")
    return full_wd


# ---------------------------------------------------------------------------
# STEP 4: Synthesis (Findings -> Patterns -> "So What" Inferences)
# ---------------------------------------------------------------------------

def step4_synthesis(state, mece, working_doc, feedback=None):
    """Bottom-up synthesis: extract findings, cluster, find patterns, derive inferences."""
    print(f"  {C.GREEN}Running structured synthesis...{C.R}")

    ps = mece.get("smart_statement", "")
    sections = mece.get("sections", [])
    syn_dir = state.dir / "synthesis"
    syn_dir.mkdir(exist_ok=True)

    # ── SUB-STEP 1: Extract top findings per bucket (parallel) ──
    print(f"    {C.DIM}Extracting key findings per bucket (parallel)...{C.R}")
    wd_dir = state.dir / "working_doc"

    def _extract_findings_one(s):
        sid = s["section_id"]
        title = s["title"]
        bucket_wd_path = wd_dir / f"bucket_{sid:02d}.md"
        bucket_text = bucket_wd_path.read_text(encoding="utf-8") if bucket_wd_path.exists() else working_doc[:8000]

        tier_info = ""
        tier_1_qs = [q for q in s.get("questions", []) if q.get("tier") == 1]
        if tier_1_qs:
            tier_info = f"\n\nTIER 1 QUESTIONS (highest priority — findings from these matter most):\n" + "\n".join(f"- {q['id']}: {q['question']}" for q in tier_1_qs)

        bucket_findings = llm_json(
            f"""Extract the key facts from this research. Today is {TODAY_STR}.

Pull out the 3-5 facts from this bucket that matter most for the decision.

WRITE LIKE YOU ARE TALKING to a CEO. Simple words. Short sentences. No jargon.

EVERY FACT MUST HAVE:
- A number (how much, how many, what percentage)
- A time period (when — "in FY25", "as of March 2026", "over the last 3 years")
- A comparison (vs. what — last year, competitors, industry average)

BAD: "The company has significant supplier concentration risk"
GOOD: "77% of inputs come from one region (FY25, per annual report) — industry average is 45%"

BAD: "Margins have been compressing as market conditions normalized"
GOOD: "Gross margin fell from 65% to 48% over FY23-FY25 (per quarterly earnings)"

PRESERVE ALL SOURCE TAGS:
- Keep "(per source, date)" citations from web search
- Keep "[LLM reasoning]" tags from analytical reasoning
- These must flow through to every downstream document. Never strip them.

Return JSON:
{{"bucket_id": {sid}, "bucket_title": "{title}", "findings": [
  {{"id": "F{sid}.1", "finding": "...", "confidence": "HIGH", "source_question": "...", "tier": 1}}
]}}""",
            f"PROBLEM STATEMENT: {ps}\n\nBUCKET: {title}\n\nWORKING DOCUMENT FOR THIS BUCKET:\n{bucket_text}{tier_info}\n\nExtract the key facts. Simple language, anchored with numbers, time periods, and comparisons.",
            model=SONNET, max_tokens=2048
        )
        return sid, bucket_findings

    findings = {"buckets": []}
    with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
        futures = {executor.submit(_extract_findings_one, s): s for s in sections}
        bucket_results = {}
        for future in as_completed(futures):
            s = futures[future]
            try:
                sid, bf = future.result()
                bucket_results[sid] = bf
                n = len(bf.get("findings", []))
                print(f"      {C.GREEN}Bucket {sid}: {n} findings{C.R}")
            except Exception as e:
                print(f"      {C.RED}Bucket {s['section_id']} failed: {e}{C.R}")
    # Compile in order
    for sid in sorted(bucket_results.keys()):
        findings["buckets"].append(bucket_results[sid])

    json.dump(findings, open(syn_dir / "1_findings.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Count findings
    all_findings = []
    for b in findings.get("buckets", []):
        all_findings.extend(b.get("findings", []))
    print(f"    {C.GREEN}Extracted {len(all_findings)} findings across {len(findings.get('buckets', []))} buckets{C.R}")

    # ── SUB-STEP 2: Cross-bucket pattern detection ──
    print(f"    {C.DIM}Finding cross-bucket patterns...{C.R}")
    patterns = llm_json(
        f"""Find PATTERNS across these research findings — themes that appear across multiple buckets.

A pattern is NOT a summary. It is a RELATIONSHIP between findings from DIFFERENT buckets that reveals something non-obvious.

CRITICAL: Preserve all "(per source, date)" citations and "[LLM reasoning]" tags in your pattern statements. Every number must carry its source.

PATTERN TYPES TO LOOK FOR:
1. CONVERGENCE — Multiple independent findings from different buckets point the same direction.
   Example: "Bucket 2 shows customer churn up 3x, Bucket 4 shows NPS dropped 20 points, Bucket 6 shows support tickets doubled -> three independent signals all say the same thing: product quality has crossed a threshold where customers are actively leaving."

2. TENSION — Two findings from different buckets contradict each other or create a dilemma.
   Example: "Bucket 1 shows the market opportunity is $2B and growing 30% YoY, but Bucket 5 shows the company's unit economics are negative at current scale -> the bigger the opportunity, the faster the cash burn."

3. SURPRISE — A finding that breaks the expected pattern or conventional wisdom.
   Example: "Despite declining revenue, Bucket 3 shows the company's enterprise segment grew 45% — the consumer business is masking a strong B2B story."

4. BINDING CONSTRAINT — One finding that limits or dominates everything else.
   Example: "Bucket 7 shows only 4 months of runway at current burn rate -> regardless of strategy, product roadmap, or market opportunity, all decisions are subordinate to this cash constraint."

5. SECOND-ORDER CASCADE — Finding A in one bucket triggers consequence B in another.
   Example: "If the main supplier exits (Bucket 3), lead times extend from 2 to 8 weeks (Bucket 5), which triggers penalty clauses with 3 key customers (Bucket 2)."

For each pattern:
- Name it (3-5 words)
- State the pattern clearly (2-3 sentences). EVERY claim in the statement must include the specific number, time period, and source from the underlying findings. Do NOT generalize or abstract away from the data — the pattern statement should read like a chain of cited facts leading to a conclusion.
- List which finding IDs support it (e.g., F1.2, F3.4, F5.1)
- Rate its importance for the decision: CRITICAL / IMPORTANT / NOTABLE

BAD pattern statement: "Multiple signals show the company is losing competitive position"
GOOD pattern statement: "Market share fell from 34% to 28% over FY23-FY25 (F1.2, per industry tracker), while R&D spend dropped to 3.5% of revenue vs. peer median of 8% (F4.1, per annual reports), and customer NPS declined 18 points YoY (F6.3, per internal survey) — three independent signals confirming accelerating competitive erosion."

Find 5-8 patterns. Prioritize CRITICAL ones.

Return JSON:
{{"patterns": [
  {{"id": "P1", "type": "convergence|tension|surprise|binding_constraint|cascade",
    "name": "...", "statement": "...",
    "supporting_findings": ["F1.2", "F3.4", "F5.1"],
    "importance": "CRITICAL|IMPORTANT|NOTABLE"}}
]}}""",
        f"PROBLEM STATEMENT: {ps}\n\n{('USER FEEDBACK (you MUST address this — it overrides your prior analysis):\n' + feedback + '\n\n') if feedback else ''}FINDINGS:\n{json.dumps(findings, indent=2, ensure_ascii=False)}\n\nFind cross-bucket patterns."
    )
    json.dump(patterns, open(syn_dir / "2_patterns.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"    {C.GREEN}Found {len(patterns.get('patterns', []))} patterns{C.R}")

    # ── SUB-STEP 3: "So What" inferences ──
    print(f"    {C.DIM}Deriving 'so what' inferences...{C.R}")
    inferences = llm_json(
        f"""For each pattern, derive the "SO WHAT" — what does this pattern IMPLY for the decision-maker?

CRITICAL: Preserve all "(per source, date)" citations and "[LLM reasoning]" tags. Every claim must carry its source attribution through.

THE "SO WHAT" TEST:
- For SITUATION patterns: "If this pattern is true, then it implies [X] for the decision."
- For ACTION patterns: "The effect of [this pattern] is [Y], which means the decision-maker faces [Z]."

RULES:
- Each inference must connect the pattern BACK to the problem statement.
- Each inference should point toward (but NOT state) a possible hypothesis. It sets up the "therefore" without saying it.
- Include the key number or threshold that makes this inference concrete.
- Flag if the inference depends on LOW confidence findings.
- EVERY claim must cite the specific number, time period, and source from the underlying findings. No unanchored statements.
- NEVER use vague references ("as conditions normalised", "in the current cycle") — always state the specific period and data source.

BAD: "The margin premium is under pressure as the cycle turns"
GOOD: "The $3.2/bbl margin premium (FY25, per quarterly earnings vs. Singapore benchmark per S&P Platts) is structurally dependent on petrochemical integration uplift that has compressed 50-60% since FY22 peaks (PX spread: $300/t -> $130/t, per ICIS), meaning the premium's durability through FY27 requires petchem spreads to stabilize above $150/t — a condition the current 78-80% global ethylene utilization rate (per IHS, 2026E) does not support."

Return JSON:
{{"inferences": [
  {{"id": "I1", "pattern_id": "P1", "so_what": "...",
    "key_number": "...",
    "implies_for_decision": "...",
    "confidence_caveat": "..."}}
]}}""",
        f"PROBLEM STATEMENT: {ps}\n\nPATTERNS:\n{json.dumps(patterns, indent=2, ensure_ascii=False)}\n\nFINDINGS:\n{json.dumps(findings, indent=2, ensure_ascii=False)}\n\nDerive 'so what' inferences."
    )
    json.dump(inferences, open(syn_dir / "3_inferences.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"    {C.GREEN}Derived {len(inferences.get('inferences', []))} inferences{C.R}")

    # ── Build synthesis document ──
    synthesis = {
        "problem_statement": ps,
        "findings": findings,
        "patterns": patterns,
        "inferences": inferences,
    }
    json.dump(synthesis, open(syn_dir / "synthesis.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    state.set("synthesis_path", str(syn_dir / "synthesis.json"))

    # ── Build human-readable summary for checkpoint ──
    summary_lines = [f"  {C.BOLD}SYNTHESIS{C.R}\n"]

    # Findings count
    summary_lines.append(f"  {C.DIM}{len(all_findings)} key findings extracted across {len(findings.get('buckets', []))} buckets{C.R}\n")

    # Patterns
    summary_lines.append(f"  {C.BOLD}Patterns ({len(patterns.get('patterns', []))}):{C.R}")
    for p in patterns.get("patterns", []):
        imp = p.get("importance", "?")
        if imp == "CRITICAL":
            tag = f"{C.RED}{imp}{C.R}"
        elif imp == "IMPORTANT":
            tag = f"{C.YELLOW}{imp}{C.R}"
        else:
            tag = f"{C.DIM}{imp}{C.R}"
        ptype = p.get("type", "?")
        summary_lines.append(f"    {p['id']} [{tag}] ({ptype}) {p.get('name', '')}")
        summary_lines.append(f"       {C.DIM}{p.get('statement', '')[:120]}{C.R}")

    # Inferences
    summary_lines.append(f"\n  {C.BOLD}'So What' Inferences ({len(inferences.get('inferences', []))}):{C.R}")
    for inf in inferences.get("inferences", []):
        summary_lines.append(f"    {inf['id']} (from {inf.get('pattern_id', '?')})")
        summary_lines.append(f"       {inf.get('so_what', '')[:140]}")
        if inf.get("key_number"):
            summary_lines.append(f"       {C.BOLD}Key number: {inf['key_number']}{C.R}")

    summary = "\n".join(summary_lines)

    # Also write a markdown version
    md_lines = [f"# Synthesis\n\n**Problem Statement:** {ps}\n\n**Date:** {TODAY_STR}\n"]
    md_lines.append(f"\n## Key Findings ({len(all_findings)})\n")
    for b in findings.get("buckets", []):
        md_lines.append(f"\n### Bucket {b['bucket_id']}: {b.get('bucket_title', '')}\n")
        for f_item in b.get("findings", []):
            md_lines.append(f"- **{f_item['id']}** [{f_item.get('confidence', '?')}]: {f_item['finding']}")

    md_lines.append(f"\n\n## Patterns ({len(patterns.get('patterns', []))})\n")
    for p in patterns.get("patterns", []):
        md_lines.append(f"\n### {p['id']}: {p.get('name', '')} ({p.get('type', '')}, {p.get('importance', '')})\n")
        md_lines.append(p.get("statement", ""))
        md_lines.append(f"\nSupporting: {', '.join(p.get('supporting_findings', []))}")

    md_lines.append(f"\n\n## 'So What' Inferences ({len(inferences.get('inferences', []))})\n")
    for inf in inferences.get("inferences", []):
        md_lines.append(f"\n### {inf['id']} (from {inf.get('pattern_id', '')})\n")
        md_lines.append(f"**So What:** {inf.get('so_what', '')}\n")
        md_lines.append(f"**Key Number:** {inf.get('key_number', 'N/A')}\n")
        md_lines.append(f"**Implies:** {inf.get('implies_for_decision', '')}")

    (syn_dir / "synthesis.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"  {C.GREEN}Synthesis complete{C.R}")
    return summary, synthesis


# ---------------------------------------------------------------------------
# STEP 5: Hypotheses (Iterative Hypothesis Tree)
# ---------------------------------------------------------------------------

# Load hypothesis tree vault
HYP_VAULT = load_vault("hypothesis_tree_vault")

def step5_hypotheses(state, mece, working_doc, synthesis, feedback=None, autopilot=False, deep_research=False, locked_governing=None):
    print(f"  {C.GREEN}Building hypothesis tree (iterative)...{C.R}")

    # Check for human-dropped hypothesis files
    files = scan_inputs(state.dir, "hypothesis")
    human_hyps = extract_from_files(files) if files else []
    added = [h for h in state.data.get("human_inputs", []) if h["type"] == "add" and h["step"] == 5]
    human_adds = "\n".join(f"- {h['content']}" for h in added)
    human_context = ""
    if human_hyps:
        human_context += "\n\nHUMAN-PROVIDED EVIDENCE:\n" + "\n".join(f"From {d['file']}:\n{d['findings']}" for d in human_hyps)
    if human_adds:
        human_context += f"\n\nHUMAN-ADDED HYPOTHESES (must be included and tested):\n{human_adds}"

    ps = mece.get("smart_statement", "")
    sens = mece.get("decision_sensitivity", "")
    syn_findings = json.dumps(synthesis.get("findings", {}), indent=2, ensure_ascii=False)
    syn_patterns = json.dumps(synthesis.get("patterns", {}), indent=2, ensure_ascii=False)
    syn_inferences = json.dumps(synthesis.get("inferences", {}), indent=2, ensure_ascii=False)

    # Vault excerpts for prompts
    vault_conditions = json.dumps(HYP_VAULT.get("DECOMPOSITION_METHOD", {}).get("types_of_necessary_conditions", []), indent=2, ensure_ascii=False)
    vault_quality = json.dumps(HYP_VAULT.get("QUALITY_CHECKS", {}).get("five_tests_for_each_hypothesis", []), indent=2, ensure_ascii=False)
    vault_mistakes = json.dumps(HYP_VAULT.get("COMMON_MISTAKES", []), indent=2, ensure_ascii=False)
    vault_examples = json.dumps(HYP_VAULT.get("GOOD_VS_BAD_STATEMENTS", {}), indent=2, ensure_ascii=False)

    hyp_dir = state.dir / "hypotheses"
    hyp_dir.mkdir(exist_ok=True)
    all_graveyard = []
    MAX_ITERATIONS = 3

    # ════════════════════════════════════════════
    # PHASE 1: Form the Day 1 governing hypothesis
    # ════════════════════════════════════════════
    if locked_governing:
        # Hypothesis-driven mode: use the user's locked hypothesis
        governing = locked_governing
        print(f"    {C.DIM}Phase 1: Using locked governing hypothesis (hypothesis-driven mode){C.R}")
        print(f"    {C.BOLD}Locked: {governing[:120]}{C.R}")
    else:
        print(f"    {C.DIM}Phase 1: Forming Day 1 governing hypothesis...{C.R}")
        day1 = llm_json(
            f"""You are a senior strategist forming the "Day 1 answer" — your best hypothesis for the answer to the problem statement BEFORE deep testing.

Read the synthesis (findings, patterns, inferences) and form ONE governing hypothesis: a single sentence that directly answers the problem statement.

This is your starting point, not your final answer. It will be decomposed, tested, and potentially revised.

THE MOST IMPORTANT RULE: The hypothesis must ANSWER THE QUESTION THAT WAS ASKED.

Read the problem statement carefully. If it asks "what actions", name the actions. If it asks "which assets to double down on vs divest", name them. If it asks "how to restructure X, Y, and Z", address X, Y, and Z. A hypothesis that answers a DIFFERENT, SIMPLER question than the one asked is a failure — even if it sounds smart.

TEST: Could someone read ONLY your hypothesis and know the specific answer to the PS? If not, rewrite.

The governing hypothesis must:
1. DIRECTLY answer EVERY PART of the problem statement — if the PS has multiple parts, the hypothesis addresses all of them
2. Name SPECIFIC actions, assets, or choices — not directions ("shift to X") but moves ("do A, B, C")
3. Include a specific number, threshold, or timeframe
4. Be testable — you could prove it wrong with data
5. Be non-obvious — the opposite must also be plausible
6. Be 1-2 SENTENCES — maximum 30 words total. No subordinate clauses, no embedded reasoning.
7. State WHAT (specific actions), HOW (specific levers), BY WHEN (deadline). The WHY lives in sub-hypotheses.
8. Write like a normal person. No consulting jargon.

BAD: "Top-tier firms must shift from analytics to trusted advisor roles" — this is a DIRECTION, not an answer. Doesn't name specific actions, doesn't address talent, partnership economics, or what to double down on.
GOOD: "Top-tier firms should exit analytics delivery, convert 40% of partners to outcome-based comp, and acquire AI-native delivery teams by Q4 2026"

BAD: "The company should optimize its supply chain" — vague direction, not specific
GOOD: "Close 3 Gulf Coast plants, shift procurement to Brazilian suppliers, and hedge Q1 2027 at $72/bbl"

BAD: "Pioneer Bank can increase sales-force productivity by 30% within 12 months" — says the OUTCOME, not the ACTIONS
GOOD: "Pioneer Bank should outsource admin tasks, automate lead scoring, and retrain 200 advisors on wealth products within 12 months to lift productivity 30%"

Today is {TODAY_STR}.

Return JSON: {{"governing_hypothesis": "...", "confidence": "HIGH/MEDIUM/LOW", "key_reasoning": "2-3 sentences on why this is the best starting hypothesis"}}""",
            f"PROBLEM STATEMENT: {ps}\n\nDECISION SENSITIVITY: {sens}\n\n{('USER FEEDBACK: ' + feedback + '\n\n') if feedback else ''}INFERENCES:\n{syn_inferences}\n\nPATTERNS:\n{syn_patterns}\n\nForm the Day 1 governing hypothesis.",
            model=SONNET
        )
        governing = day1.get("governing_hypothesis", "")
        print(f"    {C.BOLD}Day 1: {governing[:120]}{C.R}")

    # ════════════════════════════════════════════
    # ITERATION LOOP
    # ════════════════════════════════════════════
    hyp_tree = {"governing_hypothesis": governing, "hypotheses": [], "graveyard": [], "iterations": []}

    # ── Shared decomposition prompt template ──
    DECOMPOSE_PROMPT = f"""You are decomposing a GOVERNING HYPOTHESIS into a HYPOTHESIS TREE.

A hypothesis tree starts with an ANSWER and works backward to find what must be true for that answer to hold.

FOR EACH PRIMARY HYPOTHESIS, ask: "What must be true for this to hold?"
Each sub-hypothesis is a NECESSARY CONDITION — if false, the parent weakens or collapses.

TYPES OF NECESSARY CONDITIONS to consider:
{vault_conditions}

KILL TEST — for each proposed sub-hypothesis, ask: "If this is false, does the parent still hold?"
- If YES → it's NOT a necessary condition → remove it
- If NO → it's load-bearing → keep it

FOR EACH LEAF (deepest sub-hypothesis), define BEFORE testing:
- test: what specific analysis or data proves/disproves this
- evidence_expected_if_true: what you'd see in the data
- evidence_expected_if_false: what would kill it
- decision_threshold: the specific number/condition that flips (e.g., "freight > $8/bbl = dead")

LOGIC TYPE per parent:
- AND: ALL sub-hypotheses must be true (most common for strategy)
- OR: ANY being true is sufficient (usually for "how to grow" questions)

QUALITY CHECKS:
{vault_quality}

COMMON MISTAKES TO AVOID:
{vault_mistakes}

STATEMENT STYLE — THIS IS A HARD CONSTRAINT. Study these examples:
{vault_examples}

STATEMENT LENGTH RULES (ENFORCED):
- A statement is ONE CLAIM. Maximum 15 words.
- NO subordinate clauses ("rather than demanding...", "without his legitimacy challenge disabling...")
- NO evidence in the statement ("as evidenced by...", "given that...")
- NO conditions in the statement ("if X stays AND Y preserved"). Conditions go in decision_threshold.
- NO jargon. Write like a normal person, not a consulting deck.
- The reasoning, evidence, caveats, and conditions go in test/threshold/evidence fields — NEVER in the statement.

GOOD: "Netanyahu can accept a toll-to-escrow conversion"
GOOD: "The Pakistan back-channel is open and active"
GOOD: "Alternative crude can arrive before inventory runs out"
GOOD: "Crack spreads widen by >$5/bbl within 14 days"
BAD:  "Netanyahu will accept an escrow-based toll conversion rather than demanding full Strait sovereignty rollback as a precondition" (28 words, subordinate clause, conditions baked in)
BAD:  "The US-Israel negotiating channel can compress alignment to <72 hours given the April 8 internal deadline" (conditions in statement)"""

    # Track the living tree across iterations
    primary_hyps = None  # set after first decomposition

    for iteration in range(MAX_ITERATIONS):
        print(f"\n  {C.GREEN}{'='*50}{C.R}")
        print(f"  {C.GREEN}Iteration {iteration + 1}/{MAX_ITERATIONS}{C.R}")
        print(f"  {C.GREEN}{'='*50}{C.R}")

        # ════════════════════════════════════════════
        # PHASE 2: Decompose (full on iter 1, surgical on iter 2+)
        # ════════════════════════════════════════════
        if iteration == 0:
            # First iteration: full decomposition
            print(f"    {C.DIM}Phase 2: Decomposing into necessary conditions...{C.R}")
            decomposition = llm_json(
                DECOMPOSE_PROMPT + f"""

GOVERNING HYPOTHESIS: {{governing}}

Generate 3-5 primary hypotheses, each with 2-4 sub-hypotheses (leaves). Two levels deep is enough.

Return JSON:
{{"primary_hypotheses": [
  {{
    "id": "H1",
    "statement": "...",
    "logic": "AND|OR",
    "necessary_because": "if false, the governing hypothesis fails because...",
    "sub_hypotheses": [
      {{
        "id": "H1.1",
        "statement": "...",
        "test": "what analysis proves/disproves this",
        "decision_threshold": "specific number or condition",
        "evidence_expected_if_true": "...",
        "evidence_expected_if_false": "..."
      }}
    ]
  }}
]}}""".replace("{{governing}}", governing),
                f"PROBLEM STATEMENT: {ps}\n\nGOVERNING HYPOTHESIS: {governing}\n\nFINDINGS:\n{syn_findings[:15000]}\n\nPATTERNS:\n{syn_patterns}\n\nDecompose into a hypothesis tree of necessary conditions.",
                model=SONNET
            )
            primary_hyps = decomposition.get("primary_hypotheses", [])

            # ── Guided checkpoint: review decomposition before testing ──
            if deep_research and not autopilot:
                print(f"\n    {C.BOLD}DECOMPOSITION — review before testing:{C.R}")
                print(f"    {C.DIM}{'─'*50}{C.R}")
                for ph in primary_hyps:
                    logic = ph.get("logic", "AND")
                    print(f"    {C.BOLD}{ph.get('id')}{C.R} [{logic}] {ph.get('statement', '')[:80]}")
                    for sh in ph.get("sub_hypotheses", []):
                        print(f"      {C.DIM}{sh.get('id')}: {sh.get('statement', '')[:70]}{C.R}")
                        if sh.get("decision_threshold"):
                            print(f"        threshold: {sh['decision_threshold'][:60]}")
                print(f"    {C.DIM}{'─'*50}{C.R}")
                print(f"\n    {C.DIM}Commands: approve / feedback: <changes> / add: <condition>{C.R}")
                while True:
                    try:
                        resp = input(f"    {C.YELLOW}>>> {C.R}").strip()
                    except (EOFError, KeyboardInterrupt):
                        resp = "approve"
                    if resp.lower() in ("approve", "skip", ""):
                        break
                    elif resp.lower().startswith("feedback:"):
                        fb = resp[9:].strip()
                        print(f"    {C.GREEN}Revising decomposition...{C.R}")
                        revision = llm_json(
                            DECOMPOSE_PROMPT + f"\n\nCURRENT TREE:\n{json.dumps(primary_hyps, indent=2, ensure_ascii=False)}\n\nFEEDBACK: {fb}\n\nRevise the tree. Keep what works, change what was flagged. Return same JSON structure.\n\nReturn JSON: {{\"primary_hypotheses\": [...]}}",
                            f"GOVERNING HYPOTHESIS: {governing}\n\nRevise based on feedback.",
                            model=SONNET
                        )
                        primary_hyps = revision.get("primary_hypotheses", primary_hyps)
                        print(f"    {C.GREEN}Revised. Review again or approve.{C.R}")
                        for ph in primary_hyps:
                            print(f"    {C.BOLD}{ph.get('id')}{C.R} {ph.get('statement', '')[:80]}")
                    elif resp.lower().startswith("add:"):
                        addition = resp[4:].strip()
                        print(f"    {C.GREEN}Adding condition...{C.R}")
                        next_id = max((int(h["id"].replace("H","")) for h in primary_hyps), default=0) + 1
                        new_branch = llm_json(
                            DECOMPOSE_PROMPT + f"\n\nAdd a NEW primary hypothesis branch for this condition: \"{addition}\"\n\nExisting branches (do not duplicate):\n{json.dumps([h.get('statement') for h in primary_hyps])}\n\nUse ID H{next_id}. Return JSON: {{\"new_hypothesis\": {{\"id\": \"H{next_id}\", \"statement\": \"...\", \"logic\": \"AND\", \"necessary_because\": \"...\", \"sub_hypotheses\": [...]}}}}",
                            f"GOVERNING HYPOTHESIS: {governing}\n\nAdd branch for: {addition}",
                            model=SONNET
                        )
                        if new_branch.get("new_hypothesis"):
                            primary_hyps.append(new_branch["new_hypothesis"])
                            print(f"    {C.GREEN}Added H{next_id}: {new_branch['new_hypothesis'].get('statement', '')[:80]}{C.R}")
                    else:
                        print(f"    {C.DIM}Unknown command. Try: approve / feedback: X / add: X{C.R}")

        else:
            # Subsequent iterations: keep survivors, replace killed branches only
            survivors = [ph for ph in primary_hyps if ph.get("status") != "killed"]
            killed_ids = [ph["id"] for ph in primary_hyps if ph.get("status") == "killed"]
            num_replacements = len(killed_ids)

            survivors_summary = json.dumps([{
                "id": h.get("id"), "statement": h.get("statement"), "status": h.get("status"),
                "leaf_verdicts": {sh["id"]: sh.get("verdict") for sh in h.get("sub_hypotheses", [])}
            } for h in survivors], indent=2, ensure_ascii=False)

            killed_summary = json.dumps([{
                "id": h.get("id"), "statement": h.get("statement"), "killed_by": h.get("killed_by")
            } for h in primary_hyps if h.get("status") == "killed"], indent=2, ensure_ascii=False)

            print(f"    {C.DIM}Phase 2: Keeping {len(survivors)} survivors, replacing {num_replacements} killed branch(es)...{C.R}")

            # Assign new IDs that don't collide with survivors
            existing_ids = {h["id"] for h in survivors}
            next_id_num = max((int(h["id"].replace("H","")) for h in primary_hyps), default=0) + 1

            replacement = llm_json(
                DECOMPOSE_PROMPT + f"""

REVISED GOVERNING HYPOTHESIS: {governing}

THE FOLLOWING BRANCHES SURVIVED TESTING — DO NOT REGENERATE THEM. They are already tested and carry evidence:
{survivors_summary}

THE FOLLOWING BRANCHES WERE KILLED:
{killed_summary}

Your job: generate {num_replacements} NEW replacement primary hypothesis(es) that:
1. Address the gap left by the killed branch(es) — what new necessary condition does the REVISED governing hypothesis require?
2. Do NOT overlap with the surviving branches
3. Each has 2-4 sub-hypotheses (leaves) with tests and thresholds

Use IDs starting from H{next_id_num}.

Return JSON:
{{"replacement_hypotheses": [
  {{
    "id": "H{next_id_num}",
    "statement": "...",
    "logic": "AND|OR",
    "necessary_because": "...",
    "sub_hypotheses": [
      {{
        "id": "H{next_id_num}.1",
        "statement": "...",
        "test": "...",
        "decision_threshold": "...",
        "evidence_expected_if_true": "...",
        "evidence_expected_if_false": "..."
      }}
    ]
  }}
]}}""",
                f"PROBLEM STATEMENT: {ps}\n\nGOVERNING HYPOTHESIS: {governing}\n\nFINDINGS:\n{syn_findings[:15000]}\n\nPATTERNS:\n{syn_patterns}\n\nGenerate {num_replacements} replacement branch(es).",
                model=SONNET
            )

            new_branches = replacement.get("replacement_hypotheses", [])
            # Merge: survivors (with their existing evidence) + new branches
            primary_hyps = survivors + new_branches

        total_leaves = sum(len(h.get("sub_hypotheses", [])) for h in primary_hyps)
        print(f"    {C.GREEN}Tree: {len(primary_hyps)} primary hypotheses, {total_leaves} leaves{C.R}")
        for ph in primary_hyps:
            logic = ph.get("logic", "AND")
            carried = " (carried)" if ph.get("status") in ("confirmed", "uncertain") and iteration > 0 and ph.get("verdict_iteration", -1) < iteration else ""
            print(f"      {ph['id']} [{logic}]{carried}: {ph.get('statement','')[:80]}")
            for sh in ph.get("sub_hypotheses", []):
                print(f"        {sh['id']}: {sh.get('statement','')[:70]}")

        # ════════════════════════════════════════════
        # PHASE 3: Test at the leaves (only untested ones on iter 2+)
        # ════════════════════════════════════════════
        # Identify which leaves need testing
        leaves_to_test = []
        for ph in primary_hyps:
            for sh in ph.get("sub_hypotheses", []):
                if sh.get("verdict"):
                    continue  # already tested from a prior iteration — skip
                leaves_to_test.append({
                    "id": sh["id"],
                    "parent_id": ph["id"],
                    "parent_statement": ph.get("statement", ""),
                    "parent_logic": ph.get("logic", "AND"),
                    "statement": sh.get("statement", ""),
                    "test": sh.get("test", ""),
                    "decision_threshold": sh.get("decision_threshold", ""),
                    "evidence_expected_if_true": sh.get("evidence_expected_if_true", ""),
                    "evidence_expected_if_false": sh.get("evidence_expected_if_false", ""),
                })

        already_tested = total_leaves - len(leaves_to_test)
        if already_tested > 0:
            print(f"    {C.DIM}Phase 3: Testing {len(leaves_to_test)} new leaves ({already_tested} carried from prior iteration)...{C.R}")
        else:
            print(f"    {C.DIM}Phase 3: Testing {len(leaves_to_test)} leaves against research...{C.R}")

        all_leaves = leaves_to_test

        # ── Pass 1: Test against existing research ──
        if deep_research:
            # Hypothesis-driven mode: skip Pass 1 entirely — no existing research
            print(f"    {C.DIM}Pass 1: SKIPPED (hypothesis-driven mode — no prior research){C.R}")
            # Mark all leaves as AMBER needing search so Pass 2 picks them all up
            test_results = {"leaf_results": []}
            for leaf in all_leaves:
                test_results["leaf_results"].append({
                    "id": leaf["id"],
                    "verdict": "AMBER",
                    "evidence_quality": "ABSENT",
                    "what_supports": "",
                    "what_contradicts": "",
                    "what_is_missing": f"No research conducted yet — need targeted search for: {leaf.get('test', '')}",
                    "decision_threshold_met": "unknown",
                    "needs_targeted_search": True,
                    "suggested_search_query": leaf.get("test", leaf.get("statement", ""))
                })
        elif not all_leaves:
            print(f"    {C.DIM}Pass 1: All leaves already tested — skipping.{C.R}")
            test_results = {"leaf_results": []}
        else:
            print(f"    {C.DIM}Pass 1: Testing against existing research...{C.R}")

        verdict_rules = f"""{"VERDICT RULES — AUTOPILOT MODE. Be decisive, not cautious. AMBER is not the default." if autopilot else "VERDICT RULES — GUIDED MODE. Be strict. The user will review and upgrade verdicts with their own evidence."}

GREEN — the evidence SUPPORTS this sub-hypothesis:
{"  - One credible source (government data, company filing, major news outlet, industry report) that directly addresses the claim = GREEN" if autopilot else "  - Multiple independent credible sources confirm the claim = GREEN"}
{"  - Two or more sources pointing the same direction = GREEN" if autopilot else "  - Human-injected evidence (marked HIGH confidence) that meets the threshold = GREEN"}
  - A specific number from a named source that meets the threshold = GREEN

AMBER — genuinely uncertain, evidence is MIXED or THIN:
  - Only [LLM reasoning] with no sourced data = AMBER
  - Evidence points both ways — some supports, some contradicts = AMBER
  - No relevant data found at all (ABSENT) = AMBER

RED — the evidence CONTRADICTS this sub-hypothesis:
  - A credible source directly contradicts the claim = RED
  - The specific number from a named source FAILS the threshold = RED

{"THE KEY RULE: If you found a real source with a real number that addresses the claim, it's GREEN or RED — not AMBER. AMBER means you genuinely don't know." if autopilot else "THE KEY RULE: Be conservative. Single web sources stay AMBER."}"""

        if all_leaves:
            test_results = llm_json(
                f"""You are testing LEAF-LEVEL sub-hypotheses against research evidence. Today is {TODAY_STR}.

For each leaf, search the research findings and working document for SPECIFIC evidence that addresses the decision threshold. Be precise — quote the source, the number, and whether it meets the threshold.

{verdict_rules}

For each leaf return:
- verdict: GREEN/AMBER/RED
- evidence_quality: STRONG / MODERATE / THIN / ABSENT
- what_supports: specific evidence WITH source citations
- what_contradicts: specific evidence WITH source citations
- what_is_missing: what specific data would resolve this (used for targeted search)
- decision_threshold_met: true/false/unknown
- needs_targeted_search: true/false (true ONLY if verdict is AMBER and a specific web query could resolve it)
- suggested_search_query: the exact query to run (only if needs_targeted_search is true)

Return JSON: {{"leaf_results": [...]}}""",
                "LEAVES TO TEST:\n{leaves}\n\nRESEARCH FINDINGS:\n{findings}\n\nWORKING DOCUMENT (detailed evidence):\n{wd}\n\nTest each leaf.".format(
                    leaves=json.dumps(all_leaves, indent=2, ensure_ascii=False),
                    findings=syn_findings[:20000],
                    wd=working_doc[:20000]
                ),
                model=SONNET
            )

        # ── Pass 2: Targeted search ──
        if deep_research:
            # Hypothesis-driven mode: search ALL leaves, not just AMBER
            leaves_to_search = test_results.get("leaf_results", [])
            max_searches = 20  # More searches in deep mode
        else:
            # Issue-driven mode: only search AMBER leaves that need it
            leaves_to_search = [r for r in test_results.get("leaf_results", []) if r.get("needs_targeted_search") and r.get("verdict", "").upper() == "AMBER"]
            max_searches = 6

        if leaves_to_search:
            mode_label = "DEEP RESEARCH (all leaves)" if deep_research else f"Targeted search for {len(leaves_to_search)} AMBER leaves"
            print(f"    {C.DIM}Pass 2: {mode_label}...{C.R}")
            try:
                from duckduckgo_search import DDGS
                import requests as _req

                # In deep_research mode, generate better search queries via LLM
                if deep_research:
                    print(f"      {C.DIM}Generating targeted queries for {len(leaves_to_search)} leaves...{C.R}")
                    query_gen = llm_json(
                        f"""For each hypothesis leaf below, generate 2 specific web search queries that would find evidence to CONFIRM or REFUTE it.

Make queries specific: include entity names, technical terms, dates, thresholds.

Return JSON: {{"leaf_queries": [{{"id": "H1.1", "queries": ["query 1", "query 2"]}}]}}""",
                        f"PROBLEM: {ps}\n\nLEAVES:\n" + json.dumps([{"id": l.get("id"), "statement": l.get("statement", l.get("what_is_missing", "")), "test": l.get("test", "")} for l in leaves_to_search], indent=2, ensure_ascii=False),
                        model=HAIKU, max_tokens=2048
                    )
                    leaf_query_map = {lq["id"]: lq["queries"] for lq in query_gen.get("leaf_queries", [])}
                else:
                    leaf_query_map = {}

                for leaf_r in leaves_to_search[:max_searches]:
                    # Get query — from LLM generation or from leaf's suggested query
                    if deep_research and leaf_r.get("id") in leaf_query_map:
                        queries_for_leaf = leaf_query_map[leaf_r["id"]]
                    else:
                        q = leaf_r.get("suggested_search_query", leaf_r.get("statement", ""))
                        queries_for_leaf = [q] if q else []

                    if not queries_for_leaf:
                        continue
                    leaf_id = leaf_r.get("id", "?")
                    print(f"      {C.DIM}{leaf_id}: searching {len(queries_for_leaf)} queries...{C.R}")

                    try:
                        snippets = []
                        with DDGS() as ddgs:
                            for query in queries_for_leaf[:3]:  # Max 3 queries per leaf in deep mode
                                time.sleep(1.5)
                                max_per_query = 8 if deep_research else 5
                                results = list(ddgs.text(query, max_results=max_per_query))
                                for r in results:
                                    snippets.append(f"{r.get('title','')}: {r.get('body','')[:200]} (source: {r.get('href','')})")

                        if snippets:
                            # Test/re-test this leaf with the search evidence
                            test_prompt = f"""Test this sub-hypothesis against web search evidence. Today is {TODAY_STR}.

SUB-HYPOTHESIS: {leaf_r.get('id')}
STATEMENT: {leaf_r.get('statement', leaf_r.get('what_is_missing', ''))}
{"ORIGINAL VERDICT: " + leaf_r.get('verdict', 'AMBER') if not deep_research else "FIRST TEST — no prior evidence."}
{"ORIGINAL EVIDENCE: " + str(leaf_r.get('what_supports', '')) if not deep_research else ""}

WEB SEARCH RESULTS:
{chr(10).join(snippets[:8 if deep_research else 5])}

{verdict_rules}

Return JSON:
{{"id": "{leaf_r.get('id')}", "new_verdict": "GREEN/AMBER/RED", "new_evidence": "what the search found (with source)", "evidence_quality": "STRONG/MODERATE/THIN/ABSENT", "verdict_changed": true}}"""

                            retest = llm_json(
                                test_prompt,
                                "Test with search evidence.",
                                model=SONNET if deep_research else HAIKU
                            )

                            new_verdict = retest.get("new_verdict", "AMBER").upper()
                            if deep_research or (retest.get("verdict_changed") and new_verdict != "AMBER"):
                                leaf_r["verdict"] = new_verdict
                                old_supports = leaf_r.get("what_supports", "")
                                new_evidence = retest.get("new_evidence", "")
                                leaf_r["what_supports"] = (str(old_supports) + " | " if old_supports else "") + "SEARCH: " + new_evidence
                                leaf_r["evidence_quality"] = retest.get("evidence_quality", "MODERATE")
                                color = C.GREEN if new_verdict == "GREEN" else C.RED if new_verdict == "RED" else C.YELLOW
                                print(f"        {color}{leaf_id}: → {new_verdict}{C.R}")
                            else:
                                print(f"        {C.DIM}{leaf_id}: remains AMBER{C.R}")
                    except Exception as e:
                        print(f"        {C.DIM}{leaf_id}: search failed ({e}){C.R}")
            except ImportError:
                print(f"    {C.DIM}DuckDuckGo not available — skipping targeted search{C.R}")

        # Map results back to leaves
        leaf_map = {r.get("id"): r for r in test_results.get("leaf_results", [])}

        # ════════════════════════════════════════════
        # PHASE 4: Kill propagation
        # ════════════════════════════════════════════
        print(f"    {C.DIM}Phase 4: Kill propagation...{C.R}")

        killed_parents = []
        iteration_log = {"iteration": iteration + 1, "governing": governing, "results": []}

        for ph in primary_hyps:
            logic = ph.get("logic", "AND").upper()
            sub_verdicts = []
            for sh in ph.get("sub_hypotheses", []):
                result = leaf_map.get(sh["id"])
                if result:
                    # New test result — write it
                    verdict = result.get("verdict", "AMBER").upper()
                    sh["verdict"] = verdict
                    sh["evidence_quality"] = result.get("evidence_quality", "ABSENT")
                    sh["what_supports"] = result.get("what_supports", "")
                    sh["what_contradicts"] = result.get("what_contradicts", "")
                    sh["what_is_missing"] = result.get("what_is_missing", "")
                    sh["decision_threshold_met"] = result.get("decision_threshold_met", "unknown")
                    sh["confidence_in_verdict"] = result.get("confidence_in_verdict", "LOW")
                else:
                    # Carried from prior iteration — use existing verdict
                    verdict = sh.get("verdict", "AMBER").upper()
                sub_verdicts.append(verdict)

                carried_tag = " (carried)" if not result and iteration > 0 else ""
                color = C.GREEN if verdict == "GREEN" else C.RED if verdict == "RED" else C.YELLOW
                qual = sh.get("evidence_quality", "?") if not result else result.get("evidence_quality", "?")
                print(f"        {color}{sh['id']}: {verdict}{C.R} [{qual}]{carried_tag} {sh.get('statement','')[:60]}")

            # Propagate
            if logic == "AND":
                if "RED" in sub_verdicts:
                    ph["status"] = "killed"
                    red_leaves = [sh["id"] for sh in ph.get("sub_hypotheses", []) if sh.get("verdict") == "RED"]
                    ph["killed_by"] = f"AND-logic: leaf {', '.join(red_leaves)} tested RED"
                    killed_parents.append(ph)
                    all_graveyard.append({"id": ph["id"], "statement": ph.get("statement", ""), "killed_by": ph["killed_by"]})
                    print(f"      {C.RED}✗ {ph['id']} KILLED — {ph['killed_by']}{C.R}")
                elif all(v == "GREEN" for v in sub_verdicts):
                    ph["status"] = "confirmed"
                    ph["confidence"] = "HIGH"
                    print(f"      {C.GREEN}✓ {ph['id']} CONFIRMED — all leaves GREEN{C.R}")
                else:
                    ph["status"] = "uncertain"
                    amber_count = sub_verdicts.count("AMBER")
                    ph["confidence"] = "MEDIUM" if amber_count <= 1 else "LOW"
                    print(f"      {C.YELLOW}? {ph['id']} UNCERTAIN — {amber_count} AMBER leaves{C.R}")
            else:  # OR logic
                if all(v == "RED" for v in sub_verdicts):
                    ph["status"] = "killed"
                    ph["killed_by"] = "OR-logic: ALL leaves tested RED"
                    killed_parents.append(ph)
                    all_graveyard.append({"id": ph["id"], "statement": ph.get("statement", ""), "killed_by": ph["killed_by"]})
                    print(f"      {C.RED}✗ {ph['id']} KILLED — all leaves RED (OR-logic){C.R}")
                elif any(v == "GREEN" for v in sub_verdicts):
                    ph["status"] = "confirmed"
                    ph["confidence"] = "HIGH"
                    print(f"      {C.GREEN}✓ {ph['id']} CONFIRMED — at least one GREEN leaf (OR-logic){C.R}")
                else:
                    ph["status"] = "uncertain"
                    ph["confidence"] = "MEDIUM"
                    print(f"      {C.YELLOW}? {ph['id']} UNCERTAIN (OR-logic){C.R}")

            iteration_log["results"].append({
                "id": ph["id"], "statement": ph.get("statement", "")[:100],
                "status": ph.get("status"), "logic": logic,
                "leaf_verdicts": {sh["id"]: sh.get("verdict") for sh in ph.get("sub_hypotheses", [])}
            })

        hyp_tree["iterations"].append(iteration_log)

        # ── Guided checkpoint: review verdicts after testing ──
        if deep_research and not autopilot:
            print(f"\n    {C.BOLD}TEST RESULTS — review before kill propagation proceeds:{C.R}")
            print(f"    {C.DIM}You can override verdicts with internal evidence.{C.R}")
            print(f"    {C.DIM}Commands: approve / override <H1.2> GREEN <evidence> / inject <H1> <data>{C.R}")
            while True:
                try:
                    resp = input(f"    {C.YELLOW}>>> {C.R}").strip()
                except (EOFError, KeyboardInterrupt):
                    resp = "approve"
                if resp.lower() in ("approve", "skip", ""):
                    break
                elif resp.lower().startswith("override"):
                    # override H1.2 GREEN "my evidence"
                    parts = resp.split(None, 3)
                    if len(parts) >= 3:
                        leaf_id = parts[1]
                        new_v = parts[2].upper()
                        evidence = parts[3] if len(parts) > 3 else "User override"
                        if new_v in ("GREEN", "RED", "AMBER"):
                            # Find the leaf and update
                            found = False
                            for ph in primary_hyps:
                                for sh in ph.get("sub_hypotheses", []):
                                    if sh.get("id") == leaf_id:
                                        old_v = sh.get("verdict", "AMBER")
                                        sh["verdict"] = new_v
                                        sh["evidence_quality"] = "STRONG"
                                        sh["what_supports"] = str(sh.get("what_supports", "")) + f" | USER: {evidence}"
                                        # Re-propagate parent status
                                        sub_verdicts = [s.get("verdict", "AMBER") for s in ph.get("sub_hypotheses", [])]
                                        logic = ph.get("logic", "AND").upper()
                                        if logic == "AND":
                                            if "RED" in sub_verdicts:
                                                ph["status"] = "killed"
                                                ph["killed_by"] = f"AND-logic: {leaf_id} RED (user override)"
                                            elif all(v == "GREEN" for v in sub_verdicts):
                                                ph["status"] = "confirmed"
                                            else:
                                                ph["status"] = "uncertain"
                                        color = C.GREEN if new_v == "GREEN" else C.RED if new_v == "RED" else C.YELLOW
                                        print(f"      {color}{leaf_id}: {old_v} → {new_v}{C.R} (user override)")
                                        found = True
                                        break
                                if found:
                                    break
                            if not found:
                                print(f"      {C.DIM}Leaf {leaf_id} not found{C.R}")
                        else:
                            print(f"      {C.DIM}Verdict must be GREEN, RED, or AMBER{C.R}")
                    else:
                        print(f"      {C.DIM}Usage: override H1.2 GREEN \"my evidence here\"{C.R}")
                else:
                    print(f"    {C.DIM}Commands: approve / override <id> GREEN|RED|AMBER <evidence>{C.R}")

            # Rebuild killed_parents after user overrides
            killed_parents = [ph for ph in primary_hyps if ph.get("status") == "killed"]

        # ════════════════════════════════════════════
        # PHASE 5: Check if governing hypothesis survives
        # ════════════════════════════════════════════
        active = [ph for ph in primary_hyps if ph.get("status") != "killed"]
        killed_count = len(killed_parents)

        if killed_count == 0:
            print(f"\n    {C.GREEN}Governing hypothesis stable — no kills this iteration. Stopping.{C.R}")
            hyp_tree["hypotheses"] = primary_hyps
            break
        elif len(active) == 0:
            print(f"\n    {C.RED}ALL primary hypotheses killed. Governing hypothesis must be revised.{C.R}")
        else:
            print(f"\n    {C.YELLOW}{killed_count} primary hypothesis(es) killed. Revising governing hypothesis...{C.R}")

        # ════════════════════════════════════════════
        # PHASE 6: Revise governing hypothesis
        # ════════════════════════════════════════════
        if iteration < MAX_ITERATIONS - 1:
            survivors_json = json.dumps([{
                "id": h.get("id"), "statement": h.get("statement"), "status": h.get("status"), "confidence": h.get("confidence"),
                "leaf_results": [{
                    "id": sh.get("id"), "verdict": sh.get("verdict"), "what_supports": str(sh.get("what_supports",""))[:200]
                } for sh in h.get("sub_hypotheses", [])]
            } for h in primary_hyps], indent=2, ensure_ascii=False)

            killed_json = json.dumps([{
                "id": k["id"], "statement": k["statement"], "killed_by": k["killed_by"]
            } for k in killed_parents], indent=2, ensure_ascii=False)

            # Build the survivor statements as the raw material for the revised hypothesis
            survivor_statements = [h.get("statement", "") for h in primary_hyps if h.get("status") != "killed"]
            killed_statements = [f"{k['id']}: {k['statement']} — killed because {k['killed_by']}" for k in killed_parents]

            revision = llm_json(
                f"""The hypothesis tree was tested and some branches were killed. Synthesize a revised governing hypothesis FROM THE SURVIVORS.

PROBLEM STATEMENT: {ps}

ORIGINAL GOVERNING HYPOTHESIS: {governing}

SURVIVING BRANCHES (these are the facts you know — the revised hypothesis must be built from these):
{chr(10).join(f"  - {s}" for s in survivor_statements)}

KILLED BRANCHES (these are what the evidence disproved):
{chr(10).join(f"  - {s}" for s in killed_statements)}

YOUR JOB:
1. Read the surviving branch statements — they ARE the answer. The revised governing hypothesis is the sentence that synthesizes what the survivors collectively say.
2. Incorporate the LESSON from each kill — if Israeli alignment was killed, the revised hypothesis must route around it, not ignore it.
3. Do NOT invent new claims. The hypothesis must be derivable from the survivors.
4. The revised hypothesis must ANSWER THE PROBLEM STATEMENT. Read the PS again. If it asks for specific actions, name them. If it asks which assets to keep vs divest, name them. A directional theme ("shift to X") is NOT an answer.

RULES:
- 1-2 SENTENCES. Maximum 30 words total.
- Name SPECIFIC actions, levers, choices — not directions.
- State WHAT (specific actions), HOW (specific levers), BY WHEN (deadline).
- No jargon, no subordinate clauses.
- Write like a normal person.
- The reasoning goes in revision_reason — NOT in the hypothesis.

Return JSON: {{
  "revised_governing_hypothesis": "...",
  "changed": true/false,
  "revision_reason": "why this revision follows from the survivors and kills",
  "what_the_kills_taught_us": "the specific constraint or lesson each kill revealed",
  "gap_left_by_kills": "what necessary condition is NOW missing that the original tree had — this is what the replacement branch must address"
}}""",
                f"Synthesize the revised governing hypothesis from survivors.",
                model=SONNET
            )

            new_gov = revision.get("revised_governing_hypothesis", governing)
            if revision.get("changed"):
                print(f"    {C.YELLOW}Governing hypothesis revised:{C.R}")
                print(f"    {C.DIM}Was: {governing[:100]}{C.R}")
                print(f"    {C.BOLD}Now: {new_gov[:100]}{C.R}")
                print(f"    {C.DIM}Reason: {revision.get('revision_reason', '')[:100]}{C.R}")
                governing = new_gov
                hyp_tree["governing_hypothesis"] = governing
            else:
                print(f"    {C.GREEN}Governing hypothesis confirmed — refining, not replacing.{C.R}")
                hyp_tree["hypotheses"] = primary_hyps
                break
        else:
            # Final iteration — keep what we have
            hyp_tree["hypotheses"] = primary_hyps

    # If we didn't set hypotheses in the loop (e.g., all iterations ran)
    if not hyp_tree.get("hypotheses"):
        hyp_tree["hypotheses"] = primary_hyps

    hyp_tree["graveyard"] = all_graveyard

    # ════════════════════════════════════════════
    # PHASE 7: Final governing hypothesis from survivors
    # ════════════════════════════════════════════
    active_final = [h for h in hyp_tree["hypotheses"] if h.get("status") != "killed"]
    if active_final:
        print(f"\n  {C.GREEN}Finalizing governing hypothesis from {len(active_final)} survivors...{C.R}")
        survivor_stmts = [h.get("statement", "") for h in active_final]
        killed_stmts = [f"{g.get('id')}: {g.get('statement')} — {g.get('killed_by')}" for g in all_graveyard]

        gov_result = llm_json(
            f"""Write the FINAL governing hypothesis by synthesizing the surviving branches.

PROBLEM STATEMENT: {ps}

SURVIVING BRANCHES (the revised hypothesis must be built from these — do not invent new claims):
{chr(10).join(f"  - {s}" for s in survivor_stmts)}

KILLED BRANCHES (lessons incorporated):
{chr(10).join(f"  - {s}" for s in killed_stmts) if killed_stmts else "  - None"}

THE MOST IMPORTANT RULE: The hypothesis must ANSWER THE QUESTION THAT WAS ASKED.
Read the problem statement again. If it asks for specific actions, name them. If it asks which assets to keep vs divest, name them. If it asks how to restructure X, Y, Z — address all three. A directional theme ("shift to X", "focus on Y") is NOT an answer. Name the specific moves.

RULES:
- 1-2 SENTENCES. Maximum 30 words total.
- Name SPECIFIC actions, levers, or choices — not directions or themes.
- State WHAT (specific actions), HOW (specific levers), BY WHEN (deadline).
- No jargon, no subordinate clauses.
- Write like a normal person.

Return JSON: {{"governing_hypothesis": "...", "what_was_killed_and_why": "..."}}""",
            "Finalize.",
            model=SONNET
        )
        hyp_tree["governing_hypothesis"] = gov_result.get("governing_hypothesis", governing)
        if gov_result.get("what_was_killed_and_why"):
            hyp_tree["kill_reasoning"] = gov_result["what_was_killed_and_why"]

    # ════════════════════════════════════════════
    # PHASE 8: Coverage check + decision sensitivity update
    # ════════════════════════════════════════════
    print(f"  {C.GREEN}Running coverage check...{C.R}")
    sections = mece.get("sections", [])
    buckets_json = json.dumps([{"id": s["section_id"], "title": s["title"]} for s in sections], indent=2)
    active_json = json.dumps([{"id": h.get("id"), "statement": h.get("statement", "")[:100]} for h in active_final], indent=2)

    coverage = llm_json(
        f"""Check whether every MECE bucket is represented by at least one surviving hypothesis.

MECE BUCKETS:\n{buckets_json}\n\nHYPOTHESES:\n{active_json}

Return JSON: {{"coverage": [{{"bucket_id": 1, "status": "covered|uncovered", "covered_by": ["H1"]}}], "gaps": [...]}}""",
        "Check coverage.", model=HAIKU, max_tokens=2048
    )
    hyp_tree["coverage"] = coverage

    uncovered = [c for c in coverage.get("coverage", []) if c.get("status") == "uncovered"]
    if uncovered:
        print(f"  {C.YELLOW}Coverage gaps: {len(uncovered)} bucket(s){C.R}")

    # Update decision sensitivity
    if sens and active_final:
        print(f"  {C.GREEN}Updating decision sensitivity...{C.R}")
        _sens_json = json.dumps([{"id": h.get("id"), "statement": h.get("statement", "")[:100]} for h in active_final], indent=2, ensure_ascii=False)
        sens_update = llm_json(
            f"""Update the decision sensitivity break point based on what the hypothesis tree testing revealed.

ORIGINAL: {sens}\n\nSURVIVORS:\n{_sens_json}\n\nKILLED: {len(all_graveyard)} hypotheses

Return JSON: {{"should_update": true/false, "updated_break_point": "...", "reason": "..."}}""",
            "Update.", model=HAIKU
        )
        if sens_update.get("should_update") and sens_update.get("updated_break_point"):
            mece["decision_sensitivity"] = sens_update["updated_break_point"]
            mece_path = state.get("mece_path")
            if mece_path and Path(mece_path).exists():
                json.dump(mece, open(mece_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            print(f"    {C.YELLOW}Break point updated{C.R}")

    # ════════════════════════════════════════════
    # Save
    # ════════════════════════════════════════════
    json.dump(hyp_tree, open(hyp_dir / "hypotheses.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    state.set("hyp_path", str(hyp_dir / "hypotheses.json"))

    # Build summary
    lines = []
    for h in hyp_tree.get("hypotheses", []):
        s = h.get("status", "?").upper()
        if s == "CONFIRMED":
            tag = f"{C.GREEN}CONFIRMED{C.R}"
        elif s == "KILLED":
            tag = f"{C.RED}KILLED{C.R}"
        else:
            tag = f"{C.YELLOW}UNCERTAIN{C.R}"
        lines.append(f"    {h.get('id','?')} [{tag}] {h.get('statement','')[:85]}")
        for sh in h.get("sub_hypotheses", []):
            v = sh.get("verdict", "?")
            vc = C.GREEN if v == "GREEN" else C.RED if v == "RED" else C.YELLOW
            lines.append(f"      {vc}{sh.get('id','?')}: {v}{C.R} {sh.get('statement','')[:65]}")

    gov = hyp_tree.get("governing_hypothesis", "")
    graveyard = hyp_tree.get("graveyard", [])
    iterations = len(hyp_tree.get("iterations", []))
    summary = f"  {C.BOLD}Governing:{C.R} {gov[:150]}\n"
    summary += f"  {C.DIM}({iterations} iteration(s), {len(active_final)} survived, {len(graveyard)} killed){C.R}\n\n"
    summary += "\n".join(lines)
    if graveyard:
        summary += f"\n\n  {C.RED}Graveyard ({len(graveyard)}):{C.R}"
        for g in graveyard:
            summary += f"\n    {C.DIM}{g.get('id','?')}: {g.get('killed_by','')[:80]}{C.R}"

    return summary, hyp_tree


# ---------------------------------------------------------------------------
# STEP 6: Final Document
# ---------------------------------------------------------------------------

def step6_final_doc(state, mece, hyp_tree, working_doc, synthesis=None, feedback=None):
    print(f"  {C.GREEN}Generating final document...{C.R}")

    # Load doc format
    # Try to load doc format from vault, fall back to sensible defaults
    doc_format = DOC_VAULT.get("formats", {}).get("strategic_memo", DOC_VAULT.get("formats", {}).get("amazon_6pager_crisis", {}))
    format_rules = json.dumps(doc_format.get("structure", []), indent=2, ensure_ascii=False) if doc_format.get("structure") else "[]"
    formatting = "\n".join(doc_format.get("formatting_rules", [])) if doc_format.get("formatting_rules") else ""

    ps = mece.get("smart_statement", "")
    topic = state.get("topic", "")
    audience = state.get("audience", "")

    # Generate prose content
    format_block = f"\nDOCUMENT FORMAT:\n{format_rules}\n\nFORMATTING RULES:\n{formatting}" if format_rules != "[]" else ""

    content = llm(
        f"""You are writing a 3-5 page strategic document for a senior decision-maker. Today is {TODAY_STR}.

CRITICAL: Preserve all "(per source, date)" citations inline. Every factual claim must show its source. Mark any unsourced numbers with "(unverified)". Keep "[LLM reasoning]" tags where the claim is analytical inference rather than sourced fact.
{format_block}

DOCUMENT STRUCTURE (in this exact order, each with its own <h2>):
1. Title (h1) — a thematic name that captures the essence of the problem in 3-8 words. Examples: "Workday's AI Dilemma" / "The Hormuz Countdown" / "OpenAI's Margin Trap".
   Followed IMMEDIATELY by the ORIGINAL problem statement in a <p class="ps"> tag — smaller font, italic. This is the client's original question, reproduced EXACTLY as given. Do not rewrite it.
2. <h2>Governing Hypothesis</h2> — This is THE ANSWER. Reproduce the governing hypothesis VERBATIM from the hypothesis tree. One sentence, bold, standalone. This is the single most important line in the document. Do NOT narrate the process ("the hypothesis was tested..."). Do NOT editorialize. Just state the answer.
   Then one paragraph (2-3 sentences) explaining WHY this is the answer — what evidence supports it, what was killed, what survived.
3. <h2>Context</h2> — 2-3 paragraphs: what is happening, why it matters, what is at stake. Sets the scene for a reader with zero background.
   Do NOT put the problem statement inside the context section. It already appears under the title.
4. <h2>What We Believe</h2> — wrap this section in <div class="beliefs">. List the surviving hypothesis branches as numbered <ol><li> statements. One sentence each. These are the NECESSARY CONDITIONS that support the governing hypothesis. No evidence yet — just the claims upfront. Do NOT label them H1/H2/H3 — just numbered 1, 2, 3. Do NOT say "X hypotheses are active" or any meta-commentary about the process.
5. <h2>Decisions Required</h2> — numbered list of specific actions with scope/size/timing. The reader gets the answer (governing hypothesis), the beliefs, and the asks BEFORE the deep dives. Front-load the decisions.
6. <h2>[Conclusion-as-headline]</h2> for each surviving branch — each is one section with: bold claim, evidence, break point, confidence level. The headline IS the finding, not a topic label. This is the "double click" on each belief — the evidence that supports it.
7. <h2>Hypotheses Tested and Rejected</h2> — 1-2 killed hypotheses with one-sentence kill reason.
8. <h2>Data Gaps</h2> — what still needs verification. LAST section in the document.

CRITICAL:
- Write in FULL PROSE PARAGRAPHS, not bullet points (except Decisions and Data Gaps which are numbered lists).
- No jargon. The audience should understand every sentence without domain expertise.
- Reference appendix slides inline: (see Appendix 1).
- State dates relative to today ({TODAY_STR}).
- The hypotheses section IS the analysis. Each hypothesis is one paragraph with: bold claim, evidence, break point, confidence.
- Include 1-2 KILLED hypotheses to show rigor.

Return the document as clean HTML with ONLY these elements:
- <h1> for document title
- <h2> for section headers
- <p> for paragraphs
- <ol><li> for numbered lists (decisions, data gaps)
- <strong> for bold (hypothesis claims, key numbers)
- <em> for emphasis
- NO classes, NO styles, NO divs, NO colors. Pure semantic HTML.
""",
        f"TOPIC: {topic}\nAUDIENCE: {audience}\nPROBLEM STATEMENT: {ps}\n\n{('USER FEEDBACK ON PRIOR DRAFT (you MUST address every point):\n' + feedback + '\n\n') if feedback else ''}HYPOTHESES (primary input — this IS your analysis):\n{json.dumps(hyp_tree, indent=2, ensure_ascii=False)}\n\nSYNTHESIS (patterns and inferences for context):\n{json.dumps(synthesis, indent=2, ensure_ascii=False)[:20000] if synthesis else 'N/A'}\n\nWORKING DOCUMENT (detailed research — pull specific numbers, sourced data points, and per-question findings to strengthen the brief):\n{working_doc[:30000]}\n\nWrite the final document. Use the hypotheses as the core structure. Pull specific sourced numbers from the working document to make every claim concrete."
    )

    # Strip markdown fences if present
    if content.strip().startswith("```"):
        content = content.strip().split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Wrap in styled HTML
    final_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_mod.escape(topic[:60])}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
body{{font-family:'Inter',sans-serif;max-width:960px;margin:0 auto;padding:48px 48px 60px;color:#1a1a1a;background:#fff;line-height:1.75;font-size:15px}}
h1{{font:800 28px/1.3 'Inter';margin:0 0 8px}}
.ps{{font:400 13px/1.6 'Inter';color:#666;font-style:italic;margin:4px 0 16px;padding:0}}
h2:first-of-type{{font:700 22px/1.3 'Inter';margin:8px 0 24px;padding-bottom:16px;border-bottom:3px solid #1a1a1a;color:#1a1a1a}}
h2{{font:700 18px/1.3 'Inter';margin:40px 0 16px;color:#1a1a1a;padding-bottom:8px;border-bottom:1px solid #e5e7eb}}
p{{margin:0 0 16px}}
strong{{color:#0a0a0a;font-weight:800}}
ol{{padding-left:24px;margin:12px 0 20px}}
li{{margin-bottom:14px;line-height:1.7}}
.beliefs ol{{padding-left:0;list-style:none;counter-reset:belief}}
.beliefs li{{padding-left:52px;position:relative;margin-bottom:20px;font-size:15px}}
.beliefs li::before{{counter-increment:belief;content:counter(belief);position:absolute;left:0;top:0;width:36px;height:36px;background:#1a1a1a;color:#fff;border-radius:50%;font:700 15px/36px 'Inter';text-align:center}}
.footer{{font:400 10px/1.4 'Inter';color:#bbb;text-align:center;margin-top:40px;padding-top:12px;border-top:1px solid #e5e7eb}}
</style>
</head>
<body>
{content}
<div class="footer">Developed by Parth Reddy</div>
</body>
</html>'''

    # Senior Partner Critique + Rewrite
    print(f"  {C.GREEN}Running strategic critique...{C.R}")
    revised_content = llm(
        f"""Rewrite this strategic document. Today is {TODAY_STR}. Return ONLY revised HTML (h1, h2, p, ol, li, strong, em -- no classes/styles/divs except class="ps" and class="beliefs").

VOICE: Third person, company name. No individual names. No board/investor references. Direct, authoritative, concise.

STRUCTURE (this order, each with its own h2):
1. h1: Thematic title (3-8 words)
2. p class="ps": Original problem statement -- KEEP EXACTLY as written
3. h2 Governing Hypothesis: THE ANSWER in bold. Reproduce VERBATIM. Then 2-3 sentences of why.
4. h2 Context: What is happening and why it matters
5. h2 What We Believe: div class="beliefs", numbered surviving branches, one sentence each
6. h2 Decisions Required: numbered, specific, timed, costed — BEFORE the deep dives. Reader gets answer + beliefs + asks first.
7. h2 per finding: headline IS the conclusion. Each section: bold lead-in -> evidence -> so what. This is the "double click" on each belief.
8. h2 Hypotheses Tested and Rejected: 1-2, one-sentence kill reason
9. h2 Data Gaps: what needs verification

WRITING — THIS IS A BOARDROOM DOCUMENT, NOT A PROCESS REPORT:
- Every paragraph starts with <strong>bold lead-in</strong> (3-8 words). No other bolding.
- One idea per sentence. Short. Direct. A 15-year-old follows it.
- Delete sentences that add no new fact or insight.
- No meta-commentary ("this thesis reverses if", "confidence: HIGH"). State findings, not process.
- No nested conditionals ("if X then Y unless Z"). Two short sentences instead.

STRIP INTERNAL PIPELINE SCAFFOLDING — the reader is a managing partner, not a process auditor:
- KEEP "[LLM reasoning]" tags — these are honest transparency markers showing analytical inference vs sourced fact. They stay.
- REMOVE all INTERNAL PIPELINE references and replace with REAL sources:
  "(per synthesis findings, financial_and_structural: mckinsey_headcount_collapse)" → "(Business Insider, August 2025)"
  "(per working document, landscape scan: key players)" → "(industry analysis, 2025-2026)"
  "(per synthesis findings, competitive_positioning: accenture_full_stack_credibility)" → "(Accenture Q2 FY2026 earnings)"
  The pattern: anything that says "per synthesis", "per working document", "per landscape scan" followed by internal field names is pipeline scaffolding. Replace with the ACTUAL source name, date, and publication.
- REMOVE: "DATA GAP", "H1/H2/H3", "Tier 1", "hypothesis tested", "break point", "diagnosticity", "was tested and rejected", "was tested and killed", "surviving hypothesis", "kill reason", "kill propagation"
- REWRITE process descriptions as findings: "Sequential execution was tested and rejected" → "Sequential execution runs out of runway." The reader doesn't care that you tested it. They care that it doesn't work.
- Where information is uncertain, state it naturally: "Exact figures are not public, but..."
- Keep REAL source citations: "(BCG annual report, 2024)", "(Business Insider, August 2025)"
- Unsourced numbers get "(estimated)" not "(unverified)"
- End each section with a punch, not a hedge.
- Recommendations: what, in what order, by when, what it costs, what happens if you do not.

THE FINAL TEST: Read every sentence. If it sounds like it came from an internal methodology document rather than a partner speaking to a managing partner, rewrite it or cut it.""",
        f"DOCUMENT TO REWRITE:\n{content}"
    )

    # Strip markdown fences if present
    if revised_content.strip().startswith("```"):
        revised_content = revised_content.strip().split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Save both versions
    path_draft = state.dir / "final_document_draft.html"
    path_draft.write_text(final_html, encoding="utf-8")

    final_html_revised = final_html.replace(content, revised_content)

    path = state.dir / "final_document.html"
    path.write_text(final_html_revised, encoding="utf-8")
    state.set("final_doc_path", str(path))
    print(f"  {C.GREEN}Final document (revised): {len(final_html_revised):,} chars{C.R}")

    return str(path)


# ---------------------------------------------------------------------------
# STEP 7: Appendix
# ---------------------------------------------------------------------------

def _truncate_label(label, max_len=30):
    """Truncate a label to max_len chars, strip newlines."""
    if not isinstance(label, str):
        return str(label)
    label = label.replace("\n", " ").replace("\r", "").strip()
    return label[:max_len-3] + "..." if len(label) > max_len else label


def _build_echart_option(chart_type, cd):
    """Build executive-quality ECharts option from chart_data. Annotations, reference lines, proper styling."""
    FONT = "Inter"
    BLUE = "#2563eb"
    RED = "#ef4444"
    GREEN = "#22c55e"
    AMBER = "#f59e0b"
    GREY = "#d1d5db"
    DARK = "#374151"

    try:
        if chart_type in ("bar", "horizontal_bar"):
            labels = [_truncate_label(l) for l in cd.get("labels", [])]
            values = cd.get("values", [])
            colors = cd.get("colors", [BLUE] * len(values))
            if len(colors) < len(values):
                colors += [BLUE] * (len(values) - len(colors))
            # Highlight strategy: if colors provided, use them; otherwise highlight max/min
            if all(c == colors[0] for c in colors):
                max_i = values.index(max(values)) if values else 0
                min_i = values.index(min(values)) if values else 0
                colors = [GREY] * len(values)
                colors[max_i] = BLUE
                if min_i != max_i:
                    colors[min_i] = RED

            # Reference line at average
            avg = sum(values) / len(values) if values else 0
            mark_line = {"data": [{"type": "average", "label": {"formatter": "avg: {c}", "fontSize": 11, "fontFamily": FONT, "color": DARK}, "lineStyle": {"type": "dashed", "color": "#9ca3af", "width": 1.5}}], "silent": True}

            if chart_type == "horizontal_bar":
                max_label = max((len(l) for l in labels), default=10)
                grid_left = min(max(max_label * 8, 200), 320)
                return json.dumps({
                    "xAxis": {"type": "value", "axisLabel": {"fontSize": 12, "fontFamily": FONT, "color": DARK}, "splitLine": {"lineStyle": {"color": "#f3f4f6"}}},
                    "yAxis": {"type": "category", "data": labels, "axisLabel": {"fontSize": 12, "width": grid_left - 30, "overflow": "truncate", "fontFamily": FONT, "color": DARK}},
                    "series": [{"type": "bar", "data": [{"value": v, "itemStyle": {"color": c, "borderRadius": [0, 4, 4, 0]}} for v, c in zip(values, colors)], "barWidth": "50%", "label": {"show": True, "position": "right", "fontSize": 14, "fontWeight": "bold", "fontFamily": FONT, "color": DARK}, "markLine": mark_line}],
                    "grid": {"left": grid_left, "right": 80, "top": 20, "bottom": 20},
                    "tooltip": {"trigger": "axis", "textStyle": {"fontFamily": FONT}}
                })
            else:
                return json.dumps({
                    "xAxis": {"type": "category", "data": labels, "axisLabel": {"fontSize": 11, "rotate": len(labels) > 4 and 30 or 0, "fontFamily": FONT, "color": DARK}},
                    "yAxis": {"type": "value", "axisLabel": {"fontSize": 12, "fontFamily": FONT, "color": DARK}, "splitLine": {"lineStyle": {"color": "#f3f4f6"}}},
                    "series": [{"type": "bar", "data": [{"value": v, "itemStyle": {"color": c, "borderRadius": [4, 4, 0, 0]}} for v, c in zip(values, colors)], "barWidth": "55%", "label": {"show": True, "position": "top", "fontSize": 14, "fontWeight": "bold", "fontFamily": FONT, "color": DARK}, "markLine": mark_line}],
                    "grid": {"bottom": len(labels) > 4 and 90 or 50, "top": 30, "left": 60, "right": 30},
                    "tooltip": {"trigger": "axis", "textStyle": {"fontFamily": FONT}}
                })

        elif chart_type == "waterfall":
            labels = [_truncate_label(l) for l in cd.get("labels", [])]
            values = cd.get("values", [])
            base = []
            visible = []
            running = 0
            for i, v in enumerate(values):
                if i == 0 or i == len(values) - 1:
                    base.append(0)
                    visible.append(abs(v))
                elif v >= 0:
                    base.append(running)
                    visible.append(v)
                else:
                    base.append(running + v)
                    visible.append(abs(v))
                running = running + v if i > 0 else v
            vis_colors = []
            vis_labels = []
            for i, v in enumerate(values):
                if i == 0 or i == len(values) - 1:
                    vis_colors.append(BLUE)
                    vis_labels.append(str(v))
                elif v >= 0:
                    vis_colors.append(GREEN)
                    vis_labels.append(f"+{v}")
                else:
                    vis_colors.append(RED)
                    vis_labels.append(str(v))
            return json.dumps({
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"fontSize": 11, "rotate": len(labels) > 5 and 25 or 0, "fontFamily": FONT, "color": DARK}},
                "yAxis": {"type": "value", "axisLabel": {"fontSize": 12, "fontFamily": FONT, "color": DARK}, "splitLine": {"lineStyle": {"color": "#f3f4f6"}}},
                "series": [
                    {"type": "bar", "stack": "wf", "data": base, "itemStyle": {"color": "transparent"}, "emphasis": {"itemStyle": {"color": "transparent"}}},
                    {"type": "bar", "stack": "wf", "data": [{"value": v, "itemStyle": {"color": c, "borderRadius": [3, 3, 0, 0]}, "label": {"show": True, "position": "top", "formatter": lbl, "fontSize": 14, "fontWeight": "bold", "fontFamily": FONT, "color": DARK}} for v, c, lbl in zip(visible, vis_colors, vis_labels)], "barWidth": "50%"}
                ],
                "grid": {"bottom": 80, "top": 30, "left": 70, "right": 30},
                "tooltip": {"trigger": "axis", "textStyle": {"fontFamily": FONT}}
            })

        elif chart_type in ("line", "area"):
            labels = cd.get("labels", [])
            series_data = cd.get("series", [])
            if not series_data and cd.get("values"):
                series_data = [{"name": "Value", "values": cd["values"]}]
            line_colors = [BLUE, RED, GREEN, AMBER, "#8b5cf6"]
            echarts_series = []
            for idx, s_item in enumerate(series_data):
                color = line_colors[idx % len(line_colors)]
                s_obj = {
                    "type": "line", "name": s_item.get("name", ""), "data": s_item.get("values", []),
                    "smooth": True, "lineStyle": {"width": 3, "color": color},
                    "itemStyle": {"color": color}, "symbol": "circle", "symbolSize": 6,
                    "label": {"show": len(s_item.get("values", [])) <= 8, "fontSize": 12, "fontWeight": "bold", "position": "top", "fontFamily": FONT},
                    "markPoint": {"data": [{"type": "max", "symbolSize": 40, "label": {"fontSize": 12, "fontWeight": "bold"}}, {"type": "min", "symbolSize": 40, "label": {"fontSize": 12, "fontWeight": "bold"}}]}
                }
                if chart_type == "area":
                    s_obj["areaStyle"] = {"opacity": 0.12, "color": color}
                echarts_series.append(s_obj)
            return json.dumps({
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"fontSize": 12, "fontFamily": FONT, "color": DARK}, "boundaryGap": False},
                "yAxis": {"type": "value", "axisLabel": {"fontSize": 12, "fontFamily": FONT, "color": DARK}, "splitLine": {"lineStyle": {"color": "#f3f4f6"}}},
                "series": echarts_series,
                "legend": {"show": len(echarts_series) > 1, "bottom": 0, "textStyle": {"fontSize": 12, "fontFamily": FONT}},
                "tooltip": {"trigger": "axis", "textStyle": {"fontFamily": FONT}},
                "grid": {"top": 40, "bottom": len(echarts_series) > 1 and 50 or 30, "left": 60, "right": 30}
            })

        elif chart_type in ("pie", "donut"):
            labels = cd.get("labels", [])
            values = cd.get("values", [])
            pie_colors = cd.get("colors", [BLUE, RED, GREEN, AMBER, "#8b5cf6", "#06b6d4"])
            pie_data = [{"name": l, "value": v, "itemStyle": {"color": pie_colors[i % len(pie_colors)]}} for i, (l, v) in enumerate(zip(labels, values))]
            # Highlight largest slice
            max_i = values.index(max(values)) if values else 0
            pie_data[max_i]["selected"] = True
            radius = ["45%", "78%"] if chart_type == "donut" else [0, "75%"]
            return json.dumps({
                "series": [{"type": "pie", "radius": radius, "data": pie_data, "selectedMode": "single", "selectedOffset": 10,
                    "label": {"fontSize": 13, "fontFamily": FONT, "formatter": "{b}\n{d}%", "fontWeight": "bold"},
                    "emphasis": {"itemStyle": {"shadowBlur": 15, "shadowColor": "rgba(0,0,0,0.2)"}},
                    "itemStyle": {"borderRadius": 4, "borderColor": "#fff", "borderWidth": 2}}],
                "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)", "textStyle": {"fontFamily": FONT}}
            })

        elif chart_type == "gauge":
            # Render as bullet chart (horizontal bar + target markLine) — NOT a gauge
            val = cd.get("value", 0)
            mx = cd.get("max", 100)
            mn = cd.get("min", 0)
            label = _truncate_label(cd.get("label", ""), 40)
            target = cd.get("target", mx)
            # Color the bar based on position: green if near/above target, red if far below
            rng = mx - mn
            pct = (val - mn) / rng if rng > 0 else 0.5
            bar_color = GREEN if pct > 0.7 else AMBER if pct > 0.4 else RED
            # Background range bands
            return json.dumps({
                "xAxis": {"type": "value", "min": mn, "max": mx, "axisLabel": {"fontSize": 12, "fontFamily": FONT, "color": DARK}, "splitLine": {"show": False}},
                "yAxis": {"type": "category", "data": [label], "axisLabel": {"fontSize": 14, "fontWeight": "bold", "fontFamily": FONT, "color": DARK, "width": 200, "overflow": "truncate"}},
                "series": [
                    {"type": "bar", "data": [{"value": mx, "itemStyle": {"color": "#f3f4f6", "borderRadius": [0, 4, 4, 0]}}], "barWidth": "80%", "z": 1, "silent": True},
                    {"type": "bar", "data": [{"value": val, "itemStyle": {"color": bar_color, "borderRadius": [0, 4, 4, 0]}}], "barWidth": "50%", "barGap": "-100%", "z": 2,
                        "label": {"show": True, "position": "right", "fontSize": 18, "fontWeight": "bold", "fontFamily": FONT, "color": DARK, "formatter": str(val)},
                        "markLine": {"data": [{"xAxis": target, "label": {"formatter": f"Target: {target}", "fontSize": 11, "fontFamily": FONT}, "lineStyle": {"type": "solid", "color": DARK, "width": 2.5}}], "symbol": ["none", "none"], "silent": True}
                    }
                ],
                "grid": {"left": 220, "right": 80, "top": 20, "bottom": 20},
                "tooltip": {"trigger": "axis", "textStyle": {"fontFamily": FONT}}
            })

        elif chart_type == "funnel":
            labels = cd.get("labels", [])
            values = cd.get("values", [])
            funnel_colors = [BLUE, "#6366f1", AMBER, RED, GREEN]
            funnel_data = [{"name": l, "value": v, "itemStyle": {"color": funnel_colors[i % len(funnel_colors)]}} for i, (l, v) in enumerate(zip(labels, values))]
            return json.dumps({
                "series": [{"type": "funnel", "data": funnel_data, "sort": "descending", "gap": 4,
                    "label": {"show": True, "position": "inside", "fontSize": 13, "fontWeight": "bold", "fontFamily": FONT, "color": "#fff", "formatter": "{b}: {c}"},
                    "itemStyle": {"borderColor": "#fff", "borderWidth": 2},
                    "emphasis": {"label": {"fontSize": 15}}}],
                "tooltip": {"trigger": "item", "formatter": "{b}: {c}", "textStyle": {"fontFamily": FONT}}
            })

        elif chart_type == "scatter":
            points = cd.get("points", [])
            x_label = cd.get("x_label", "X")
            y_label = cd.get("y_label", "Y")
            return json.dumps({
                "xAxis": {"name": x_label, "nameLocation": "center", "nameGap": 30, "nameTextStyle": {"fontSize": 13, "fontFamily": FONT, "fontWeight": "bold"}, "axisLabel": {"fontFamily": FONT}, "splitLine": {"lineStyle": {"color": "#f3f4f6"}}},
                "yAxis": {"name": y_label, "nameLocation": "center", "nameGap": 40, "nameTextStyle": {"fontSize": 13, "fontFamily": FONT, "fontWeight": "bold"}, "axisLabel": {"fontFamily": FONT}, "splitLine": {"lineStyle": {"color": "#f3f4f6"}}},
                "series": [{"type": "scatter", "data": points, "symbolSize": 14, "itemStyle": {"color": BLUE, "opacity": 0.8}, "emphasis": {"itemStyle": {"color": RED, "borderColor": DARK, "borderWidth": 2}}}],
                "tooltip": {"trigger": "item", "textStyle": {"fontFamily": FONT}},
                "grid": {"left": 60, "right": 30, "top": 30, "bottom": 50}
            })

        elif chart_type == "heatmap":
            x_labels = cd.get("x_labels", [])
            y_labels = cd.get("y_labels", [])
            values = cd.get("values", [])
            hm_data = []
            all_vals = []
            for yi, row in enumerate(values):
                for xi, val in enumerate(row if isinstance(row, list) else [row]):
                    hm_data.append([xi, yi, val])
                    all_vals.append(val)
            return json.dumps({
                "xAxis": {"type": "category", "data": x_labels, "axisLabel": {"fontFamily": FONT, "fontSize": 12}},
                "yAxis": {"type": "category", "data": y_labels, "axisLabel": {"fontFamily": FONT, "fontSize": 12}},
                "visualMap": {"min": min(all_vals) if all_vals else 0, "max": max(all_vals) if all_vals else 100, "calculable": True, "orient": "horizontal", "bottom": 0, "inRange": {"color": ["#f0f9ff", BLUE]}},
                "series": [{"type": "heatmap", "data": hm_data, "label": {"show": True, "fontSize": 13, "fontWeight": "bold", "fontFamily": FONT, "color": DARK}}],
                "grid": {"left": 80, "right": 30, "top": 20, "bottom": 60},
                "tooltip": {"textStyle": {"fontFamily": FONT}}
            })

        elif chart_type == "sankey":
            nodes = [{"name": n} for n in cd.get("nodes", [])]
            links = cd.get("links", [])
            return json.dumps({
                "series": [{"type": "sankey", "data": nodes, "links": links, "emphasis": {"focus": "adjacency"},
                    "lineStyle": {"color": "gradient", "curveness": 0.5},
                    "label": {"fontSize": 12, "fontFamily": FONT},
                    "itemStyle": {"borderWidth": 1, "borderColor": "#fff"}}],
                "tooltip": {"trigger": "item", "textStyle": {"fontFamily": FONT}}
            })

        # Fallback
        labels = cd.get("labels", [])
        values = cd.get("values", [])
        if labels and values:
            return json.dumps({"xAxis": {"type": "category", "data": labels}, "yAxis": {"type": "value"}, "series": [{"type": "bar", "data": values}]})

    except Exception:
        pass
    return None


def _md_to_html_page(md_path, title="Document"):
    """Convert a markdown file to a styled HTML page."""
    if not Path(md_path).exists():
        return None
    md_text = Path(md_path).read_text(encoding="utf-8")
    # Simple markdown to HTML conversion
    import re as _re
    html_body = md_text
    # Headers
    html_body = _re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_body, flags=_re.MULTILINE)
    html_body = _re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_body, flags=_re.MULTILINE)
    html_body = _re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_body, flags=_re.MULTILINE)
    # Bold
    html_body = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)
    # Italic
    html_body = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_body)
    # Bullet lists
    html_body = _re.sub(r'^- (.+)$', r'<li>\1</li>', html_body, flags=_re.MULTILINE)
    html_body = _re.sub(r'(<li>.*?</li>\n?)+', r'<ul>\g<0></ul>', html_body)
    # Paragraphs (lines not already tagged)
    lines = html_body.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<') and not stripped.startswith('---'):
            result.append(f'<p>{stripped}</p>')
        elif stripped == '---':
            result.append('<hr>')
        else:
            result.append(line)
    html_body = '\n'.join(result)

    html_path = Path(md_path).with_suffix('.html')
    page = f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
body{{font-family:'Inter',sans-serif;max-width:960px;margin:0 auto;padding:48px 48px 60px;color:#1a1a1a;line-height:1.75;font-size:15px}}
h1{{font:800 26px/1.3 'Inter';margin:0 0 24px;padding-bottom:12px;border-bottom:3px solid #1a1a1a}}
h2{{font:700 18px/1.3 'Inter';margin:32px 0 12px;padding-bottom:8px;border-bottom:1px solid #e5e7eb}}
h3{{font:700 15px/1.3 'Inter';margin:24px 0 8px}}
p{{margin:0 0 14px}}
strong{{font-weight:800}}
ul{{padding-left:24px;margin:8px 0 16px}}
li{{margin-bottom:8px}}
hr{{border:none;border-top:1px solid #e5e7eb;margin:24px 0}}
</style></head><body>
{html_body}
</body></html>'''
    html_path.write_text(page, encoding="utf-8")
    return str(html_path)


def _build_hypothesis_tree_html(run_dir):
    """Build a visual hypothesis TREE HTML page — governing → primary → leaves with verdicts."""
    run_dir = Path(run_dir)
    hyp_path = run_dir / "hypotheses" / "hypotheses.json"
    if not hyp_path.exists():
        return None

    with open(hyp_path, encoding="utf-8") as f:
        hyp = json.load(f)

    e = html_mod.escape
    gov = e(hyp.get("governing_hypothesis", ""))
    hypotheses = hyp.get("hypotheses", [])
    graveyard = hyp.get("graveyard", [])
    iterations = len(hyp.get("iterations", []))

    confirmed = len([h for h in hypotheses if h.get("status") == "confirmed"])
    uncertain = len([h for h in hypotheses if h.get("status") == "uncertain"])
    killed_count = len(graveyard)

    # Build tree nodes
    tree_html = ""
    for h in hypotheses:
        hid = h.get("id", "?")
        status = h.get("status", "uncertain").upper()
        stmt = e(h.get("statement", ""))
        logic = h.get("logic", "AND").upper()
        conf = h.get("confidence", "?").upper()
        necessary = e(h.get("necessary_because", ""))
        subs = h.get("sub_hypotheses", [])

        s_color = "#16a34a" if status == "CONFIRMED" else "#ef4444" if status == "KILLED" else "#d97706"
        s_bg = "rgba(22,163,74,0.06)" if status == "CONFIRMED" else "rgba(239,68,68,0.06)" if status == "KILLED" else "rgba(217,119,6,0.06)"
        s_border = "#bbf7d0" if status == "CONFIRMED" else "#fecaca" if status == "KILLED" else "#fde68a"

        # Sub-hypothesis leaves
        leaves_html = ""
        for sh in subs:
            sid = sh.get("id", "?")
            s_stmt = e(sh.get("statement", ""))
            verdict = sh.get("verdict", "?").upper()
            eq = sh.get("evidence_quality", "?")
            threshold = e(sh.get("decision_threshold", ""))
            supports = e(str(sh.get("what_supports", ""))[:200])
            contradicts = e(str(sh.get("what_contradicts", ""))[:200])
            missing = e(str(sh.get("what_is_missing", ""))[:150])

            v_color = "#16a34a" if verdict == "GREEN" else "#ef4444" if verdict == "RED" else "#d97706"
            v_bg = "#f0fdf4" if verdict == "GREEN" else "#fef2f2" if verdict == "RED" else "#fffbeb"
            v_icon = "✓" if verdict == "GREEN" else "✗" if verdict == "RED" else "?"

            leaves_html += f'''
      <div style="position:relative;padding-left:32px;margin-bottom:8px;">
        <div style="position:absolute;left:0;top:0;bottom:0;width:2px;background:{v_color};opacity:0.3;"></div>
        <div style="position:absolute;left:-5px;top:8px;width:12px;height:12px;border-radius:50%;background:{v_bg};border:2px solid {v_color};display:flex;align-items:center;justify-content:center;font-size:8px;color:{v_color};font-weight:800;">{v_icon}</div>
        <div style="background:{v_bg};border:1px solid {v_color}22;border-radius:6px;padding:12px 16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span style="font:700 12px 'Inter';color:{v_color};">{sid}</span>
            <div>
              <span style="font:600 10px 'Inter';color:{v_color};background:{v_bg};padding:2px 8px;border-radius:10px;border:1px solid {v_color}44;">{verdict}</span>
              <span style="font:400 10px 'Inter';color:#999;margin-left:6px;">{eq}</span>
            </div>
          </div>
          <p style="font:400 13px/1.5 'Inter';color:#1a1a1a;margin:0 0 6px;">{s_stmt}</p>
          {"<p style='font:400 11px/1.4 Inter;color:#666;margin:0;'><span style=color:#16a34a>▲</span> " + supports + "</p>" if supports and supports != "None" else ""}
          {"<p style='font:400 11px/1.4 Inter;color:#666;margin:0;'><span style=color:#ef4444>▼</span> " + contradicts + "</p>" if contradicts and contradicts != "None" and contradicts != "" else ""}
          {"<p style='font:400 11px/1.4 Inter;color:#999;margin:0;'>◌ Missing: " + missing + "</p>" if missing and missing != "None" and missing != "" else ""}
          {"<p style='font:400 10px Inter;color:#999;margin:4px 0 0;'>Threshold: " + threshold + "</p>" if threshold else ""}
        </div>
      </div>'''

        tree_html += f'''
<div style="position:relative;margin-bottom:24px;margin-left:40px;">
  <!-- Connector line from governing -->
  <div style="position:absolute;left:-20px;top:0;width:2px;height:100%;background:#e5e7eb;"></div>
  <div style="position:absolute;left:-24px;top:20px;width:8px;height:8px;border-radius:50%;background:{s_color};"></div>

  <!-- Primary hypothesis -->
  <div style="background:{s_bg};border:1px solid {s_border};border-radius:8px;padding:16px 20px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
      <span style="font:800 14px 'Inter';color:{s_color};">{hid} — {status}</span>
      <div>
        <span style="font:600 10px 'Inter';color:#888;background:#f3f4f6;padding:2px 8px;border-radius:10px;">{logic}-logic</span>
        <span style="font:600 10px 'Inter';color:{s_color};background:{s_bg};padding:2px 8px;border-radius:10px;border:1px solid {s_color}44;margin-left:4px;">{conf}</span>
      </div>
    </div>
    <p style="font:500 14px/1.5 'Inter';color:#1a1a1a;margin:0;">{stmt}</p>
    {"<p style='font:400 11px/1.4 Inter;color:#888;margin:6px 0 0;font-style:italic;'>Why necessary: " + necessary + "</p>" if necessary else ""}
  </div>

  <!-- Leaf sub-hypotheses -->
  <div style="margin-left:20px;">
{leaves_html}
  </div>
</div>'''

    # Graveyard
    graveyard_html = ""
    if graveyard:
        graveyard_html = '<div style="margin-top:40px;padding-top:24px;border-top:2px solid #fecaca;"><h2 style="color:#ef4444;margin:0 0 16px;font:700 16px Inter;">Hypothesis Graveyard</h2>'
        for k in graveyard:
            graveyard_html += f'''<div style="background:#fef2f2;border-left:3px solid #ef4444;padding:12px 16px;margin-bottom:8px;border-radius:0 6px 6px 0;">
  <p style="font:600 12px Inter;color:#ef4444;margin:0 0 4px;">{e(k.get("id",""))}: KILLED</p>
  <p style="font:400 13px/1.5 Inter;color:#1a1a1a;margin:0 0 4px;">{e(k.get("statement","")[:150])}</p>
  <p style="font:400 11px Inter;color:#999;margin:0;">Kill reason: {e(k.get("killed_by",""))}</p>
</div>'''
        graveyard_html += '</div>'

    page = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hypothesis Tree</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;max-width:960px;margin:0 auto;padding:48px 32px 80px;color:#1a1a1a;background:#fff;line-height:1.6}}
</style></head><body>

<!-- Stats -->
<div style="display:flex;gap:12px;margin-bottom:24px;">
  <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:10px 20px;text-align:center;flex:1;">
    <div style="font:800 22px 'Inter';color:#16a34a;">{confirmed}</div>
    <div style="font:500 10px 'Inter';color:#555;text-transform:uppercase;letter-spacing:1px;">Confirmed</div>
  </div>
  <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 20px;text-align:center;flex:1;">
    <div style="font:800 22px 'Inter';color:#d97706;">{uncertain}</div>
    <div style="font:500 10px 'Inter';color:#555;text-transform:uppercase;letter-spacing:1px;">Uncertain</div>
  </div>
  <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:10px 20px;text-align:center;flex:1;">
    <div style="font:800 22px 'Inter';color:#ef4444;">{killed_count}</div>
    <div style="font:500 10px 'Inter';color:#555;text-transform:uppercase;letter-spacing:1px;">Killed</div>
  </div>
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 20px;text-align:center;flex:1;">
    <div style="font:800 22px 'Inter';color:#2563eb;">{iterations}</div>
    <div style="font:500 10px 'Inter';color:#555;text-transform:uppercase;letter-spacing:1px;">Iterations</div>
  </div>
</div>

<!-- Governing Hypothesis (tree root) -->
<div style="background:#eff6ff;border:2px solid #2563eb;border-radius:10px;padding:20px 24px;margin-bottom:8px;position:relative;">
  <div style="font:700 10px 'Inter';color:#2563eb;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">Governing Hypothesis</div>
  <p style="font:600 16px/1.5 'Inter';color:#1a1a1a;margin:0;">{gov}</p>
</div>

<!-- Connector -->
<div style="width:2px;height:16px;background:#e5e7eb;margin:0 0 0 40px;"></div>

<!-- Legend -->
<div style="font:400 11px 'Inter';color:#888;margin:0 0 16px 40px;">
  <span style="color:#16a34a;">● GREEN</span> = evidence confirms &nbsp;
  <span style="color:#d97706;">● AMBER</span> = thin/uncertain &nbsp;
  <span style="color:#ef4444;">● RED</span> = evidence kills &nbsp;
  | AND-logic: one RED kills parent · OR-logic: all RED kills parent
</div>

<!-- Tree branches -->
{tree_html}

{graveyard_html}

<div style="font:400 10px 'Inter';color:#bbb;margin-top:40px;padding-top:12px;border-top:1px solid #f3f4f6;">
  Anvil v2.0 · Iterative hypothesis tree · {iterations} iteration(s) · Leaf-level testing with GREEN/AMBER/RED verdicts
</div>

</body></html>'''

    out_path = run_dir / "hypotheses" / "hypotheses.html"
    out_path.write_text(page, encoding="utf-8")
    return str(out_path)


def _build_hypothesis_map_html(run_dir):
    """Build a clean horizontal tree map — governing → primary → leaves. Statements only, no detail."""
    run_dir = Path(run_dir)
    hyp_path = run_dir / "hypotheses" / "hypotheses.json"
    if not hyp_path.exists():
        return None

    with open(hyp_path, encoding="utf-8") as f:
        hyp = json.load(f)

    e = html_mod.escape
    gov = e(hyp.get("governing_hypothesis", ""))
    hypotheses = hyp.get("hypotheses", [])
    graveyard = hyp.get("graveyard", [])

    # Build branch rows
    branches_html = ""
    for i, h in enumerate(hypotheses):
        hid = h.get("id", "?")
        status = h.get("status", "uncertain").upper()
        stmt = e(h.get("statement", ""))
        logic = h.get("logic", "AND").upper()
        subs = h.get("sub_hypotheses", [])

        def _md_bold(text):
            """Convert **bold** markdown to <strong> tags."""
            import re as _re
            return _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

        def _bold_only(text):
            """Extract ONLY the bold phrase for the map view. Falls back to full text if no bold markers."""
            import re as _re
            match = _re.search(r'\*\*(.+?)\*\*', text)
            if match:
                return match.group(1)
            return text

        # Color by level — each primary hypothesis gets a distinct color family
        level_colors = [
            {"border": "#2563eb", "bg": "#eff6ff", "text": "#1d4ed8"},   # blue
            {"border": "#7c3aed", "bg": "#f5f3ff", "text": "#6d28d9"},   # purple
            {"border": "#0891b2", "bg": "#ecfeff", "text": "#0e7490"},   # cyan
            {"border": "#c2410c", "bg": "#fff7ed", "text": "#c2410c"},   # orange
            {"border": "#15803d", "bg": "#f0fdf4", "text": "#15803d"},   # green
            {"border": "#be185d", "bg": "#fdf2f8", "text": "#be185d"},   # pink
        ]
        lc = level_colors[i % len(level_colors)]

        # Override with status color if killed
        if status == "KILLED":
            lc = {"border": "#ef4444", "bg": "#fef2f2", "text": "#ef4444"}

        # Leaf nodes
        leaves_html = ""
        for sh in subs:
            sid = sh.get("id", "?")
            s_stmt = e(sh.get("statement", ""))
            verdict = sh.get("verdict", "?").upper()
            v_color = "#16a34a" if verdict == "GREEN" else "#ef4444" if verdict == "RED" else "#d97706"
            v_bg = "#f0fdf4" if verdict == "GREEN" else "#fef2f2" if verdict == "RED" else "#fffbeb"
            v_icon = "✓" if verdict == "GREEN" else "✗" if verdict == "RED" else "?"

            leaves_html += f'''<div class="leaf">
<div class="leaf-dot" style="background:{lc['border']};"></div>
<div class="leaf-line" style="background:{lc['border']};opacity:0.3;"></div>
<div class="leaf-node" style="border-color:{lc['border']};background:{lc['bg']};">
  <span class="leaf-id" style="color:{lc['text']};">{sid}</span>
  <span class="leaf-verdict" style="color:{v_color};">{v_icon}</span>
  <span class="leaf-stmt">{_bold_only(s_stmt)}</span>
</div>
</div>'''

        branches_html += f'''<div class="branch">
<div class="branch-connector" style="background:{lc['border']};opacity:0.3;"></div>
<div class="branch-node" style="border-color:{lc['border']};background:{lc['bg']};">
  <span class="branch-id" style="color:{lc['text']};">{hid}</span>
  <span class="branch-logic" style="color:{lc['text']};">{logic}</span>
  <span class="branch-stmt">{_bold_only(stmt)}</span>
</div>
<div class="leaves">
{leaves_html}
</div>
</div>'''

    # Graveyard row
    grave_html = ""
    if graveyard:
        for g in graveyard:
            grave_html += f'<div class="grave-node"><span class="grave-id">{e(g.get("id",""))}</span> {e(g.get("statement","")[:80])}</div>'
        grave_html = f'<div class="graveyard"><div class="grave-label">GRAVEYARD</div>{grave_html}</div>'

    page = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hypothesis Map</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#fff;color:#1a1a1a;padding:32px;overflow-x:auto;min-width:100%}}
.tree{{display:flex;align-items:flex-start;gap:0;min-height:80vh;width:max-content}}

/* Root */
.root{{flex-shrink:0;width:220px;display:flex;align-items:center;position:relative}}
.root-node{{background:#eff6ff;border:2px solid #2563eb;border-radius:8px;padding:10px 12px;width:180px;position:relative}}
.root-label{{font:700 8px 'Inter';color:#2563eb;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px}}
.root-stmt{{font:600 10px/1.3 'Inter';color:#1a1a1a}}
.root-line{{position:absolute;right:-20px;top:50%;width:20px;height:2px;background:#e5e7eb}}

/* Branches column */
.branches{{display:flex;flex-direction:column;gap:16px;margin-left:20px;position:relative}}
.branches::before{{content:'';position:absolute;left:0;top:20px;bottom:20px;width:2px;background:#e5e7eb}}

.branch{{display:flex;align-items:flex-start;gap:0;position:relative}}
.branch-connector{{width:16px;height:2px;background:#e5e7eb;margin-top:20px;flex-shrink:0}}
.branch-node{{flex-shrink:0;width:280px;border:1.5px solid;border-radius:6px;padding:8px 12px}}
.branch-id{{font:800 11px 'Inter';display:block}}
.branch-logic{{font:500 9px 'Inter';float:right;padding:1px 6px;border-radius:8px;background:#f3f4f6}}
.branch-stmt{{font:400 11px/1.3 'Inter';color:#1a1a1a;display:block;margin-top:3px}}

/* Leaves */
.leaves{{display:flex;flex-direction:column;gap:6px;margin-left:8px;position:relative}}
.leaves::before{{content:'';position:absolute;left:8px;top:6px;bottom:6px;width:1px;background:#e5e7eb}}

.leaf{{display:flex;align-items:center;gap:0;position:relative}}
.leaf-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;z-index:1;margin-left:5px}}
.leaf-line{{width:10px;height:1px;background:#e5e7eb;flex-shrink:0}}
.leaf-node{{border:1px solid;border-radius:4px;padding:5px 10px;min-width:250px;flex:1}}
.leaf-id{{font:700 10px 'Inter';margin-right:4px}}
.leaf-stmt{{font:400 10px/1.3 'Inter';color:#374151}}

/* Graveyard */
.graveyard{{margin-top:32px;padding:16px;border:1px dashed #fecaca;border-radius:6px;margin-left:240px}}
.grave-label{{font:700 10px 'Inter';color:#ef4444;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px}}
.grave-node{{font:400 11px/1.4 'Inter';color:#999;padding:4px 0;border-bottom:1px solid #fef2f2}}
.grave-id{{font:700 11px 'Inter';color:#ef4444;margin-right:6px}}
</style></head><body>

<div class="tree">
  <!-- Root: Governing Hypothesis -->
  <div class="root">
    <div class="root-node">
      <div class="root-label">Governing</div>
      <div class="root-stmt">{_bold_only(gov)}</div>
      <div class="root-line"></div>
    </div>
  </div>

  <!-- Branches: Primary Hypotheses → Leaves -->
  <div class="branches">
{branches_html}
  </div>
</div>

{grave_html}

</body></html>'''

    out_path = run_dir / "hypotheses" / "hypothesis_map.html"
    out_path.write_text(page, encoding="utf-8")
    return str(out_path)


def _build_combined_output(run_dir):
    """Combine all outputs into one tabbed HTML file using iframes."""
    run_dir = Path(run_dir)

    # Convert markdown files to HTML
    synthesis_html = _md_to_html_page(run_dir / "synthesis" / "synthesis.md", "Synthesis")
    debrief_html = _md_to_html_page(run_dir / "research" / "debrief.md", "Research Debrief")
    hypothesis_html = _build_hypothesis_tree_html(run_dir)
    hypothesis_map = _build_hypothesis_map_html(run_dir)

    # Build tab config
    tabs = [
        ("Report", "final_document.html"),
        ("Appendix", "appendix.html"),
        ("Issue Tree", "tree.html"),
        ("Hyp Tree", "hypotheses/hypotheses.html" if hypothesis_html else ""),
        ("Hyp Map", "hypotheses/hypothesis_map.html" if hypothesis_map else ""),
        ("Synthesis", "synthesis/synthesis.html" if synthesis_html else ""),
        ("Research Debrief", "research/debrief.html" if debrief_html else ""),
    ]
    tabs = [(name, f) for name, f in tabs if f]

    tab_divs = "\n".join(
        f'<div class="tab{" active" if i == 0 else ""}" onclick="switchTab(\'{f}\',this)">{name}</div>'
        for i, (name, f) in enumerate(tabs)
    )

    combined = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Strategic Brief</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#f8fafc;height:100vh;display:flex;flex-direction:column}}
.tab-bar{{position:sticky;top:0;z-index:100;background:#1a1a1a;display:flex;padding:0 24px;box-shadow:0 2px 8px rgba(0,0,0,.15);flex-shrink:0}}
.tab{{padding:14px 24px;color:#999;font:600 12px/1 'Inter';cursor:pointer;border-bottom:3px solid transparent;transition:all .15s;letter-spacing:.3px}}
.tab:hover{{color:#fff}}
.tab.active{{color:#fff;border-bottom-color:#2563eb}}
iframe{{flex:1;width:100%;border:none}}
</style></head><body>
<div class="tab-bar">
{tab_divs}
</div>
<iframe id="content" src="{tabs[0][1]}"></iframe>
<script>
function switchTab(file, el) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('content').src = file;
}}
</script>
</body></html>'''

    combined_path = run_dir / "output.html"
    combined_path.write_text(combined, encoding="utf-8")
    print(f"  {C.GREEN}Combined output: {combined_path}{C.R}")
    return str(combined_path)


def step7_appendix(state, mece, hyp_tree, working_doc, feedback=None):
    print(f"  {C.GREEN}Generating appendix slides...{C.R}")

    # Build chart framework from vault
    chart_framework_parts = []
    if CHART_VAULT.get("THE_PROCESS"):
        chart_framework_parts.append("CHART DESIGN PROCESS:\n" + json.dumps(CHART_VAULT["THE_PROCESS"], indent=2, ensure_ascii=False))
    if CHART_VAULT.get("CHART_SELECTION_DECISION_TREE"):
        chart_framework_parts.append("DECISION TREE (follow in order, stop at first match):\n" + json.dumps(CHART_VAULT["CHART_SELECTION_DECISION_TREE"]["tree"], indent=2, ensure_ascii=False))
    if CHART_VAULT.get("KNAFLIC_DESIGN_PRINCIPLES"):
        chart_framework_parts.append("DESIGN PRINCIPLES:\n" + json.dumps(CHART_VAULT["KNAFLIC_DESIGN_PRINCIPLES"], indent=2, ensure_ascii=False))
    if CHART_VAULT.get("TITLE_RULES"):
        chart_framework_parts.append("TITLE RULES:\n" + json.dumps(CHART_VAULT["TITLE_RULES"], indent=2, ensure_ascii=False))
    if CHART_VAULT.get("ECHARTS_STYLING_DEFAULTS"):
        chart_framework_parts.append("ECHARTS STYLING:\n" + json.dumps(CHART_VAULT["ECHARTS_STYLING_DEFAULTS"], indent=2, ensure_ascii=False))
    chart_rules = "\n\n".join(chart_framework_parts)

    # Read the final document to map claims from it (not the working doc)
    final_doc_path = state.get("final_doc_path", "")
    if final_doc_path and Path(final_doc_path).exists():
        import re as _re
        final_html = Path(final_doc_path).read_text(encoding="utf-8")
        # Strip HTML tags to get plain text for the prompt
        final_text = _re.sub(r'<[^>]+>', '', final_html)
        final_text = _re.sub(r'\s+', ' ', final_text).strip()
    else:
        final_text = ""

    # TWO-STEP APPROACH: identify claims first, then generate chart data per slide
    # Step 1: Identify 4-6 claims that need charts + chart type + title (small JSON)
    print(f"    {C.DIM}Step 1: Identifying chartable claims...{C.R}")
    claim_specs = llm_json(
        f"""Identify 4-6 claims from this strategic document that need proving with a chart.

For each claim, specify WHAT chart to make — but do NOT generate the chart data yet.

DECISION TREE — pick the best chart type:
1. RANKING or COMPARISON? -> "horizontal_bar"
2. CHANGE OVER TIME? -> "line"
3. BUILD-UP or BREAKDOWN? -> "waterfall"
4. PART OF A WHOLE? -> "donut" (max 6 slices)
5. SINGLE KPI vs TARGET? -> "gauge"
6. FLOW? -> "sankey"

VARIETY: use at least 3 different chart types. Do NOT default to horizontal_bar for everything.

Only pick claims that have REAL SOURCED NUMBERS in the document. No chart for unsourced claims.

Return JSON: {{"claims": [
  {{
    "appendix_num": 1,
    "claim_sentence": "exact sentence from document",
    "action_title": "conclusion headline, 8-12 words",
    "subtitle": "units, period, source",
    "chart_type": "horizontal_bar|line|waterfall|donut|gauge|bar|scatter|sankey",
    "data_description": "what data points to extract for this chart",
    "conclusion": "one sentence takeaway",
    "source_line": "data source"
  }}
]}}""",
        "{fb}FINAL DOCUMENT:\n{doc}".format(
            fb=f"USER FEEDBACK:\n{feedback}\n\n" if feedback else "",
            doc=final_text[:15000]
        ),
        model=SONNET, max_tokens=4096
    )

    claims = claim_specs.get("claims", [])
    print(f"    {C.DIM}{len(claims)} chartable claims identified{C.R}")

    # Step 2: Generate chart_data for each claim individually (parallel)
    print(f"    {C.DIM}Step 2: Generating chart data per slide...{C.R}")

    def _gen_chart_data(claim):
        chart_type = claim.get("chart_type", "horizontal_bar")
        data_formats = {
            "bar": '{"labels": ["A","B","C"], "values": [10,20,30], "colors": ["#2563eb","#2563eb","#ef4444"]}',
            "horizontal_bar": '{"labels": ["A","B","C"], "values": [10,20,30], "colors": ["#2563eb","#2563eb","#ef4444"]}',
            "line": '{"labels": ["Q1","Q2","Q3"], "series": [{"name": "X", "values": [10,12,15]}]}',
            "area": '{"labels": ["Q1","Q2","Q3"], "series": [{"name": "X", "values": [10,12,15]}]}',
            "waterfall": '{"labels": ["Start","+A","-B","End"], "values": [100,30,-15,115], "colors": ["#2563eb","#22c55e","#ef4444","#2563eb"]}',
            "donut": '{"labels": ["A","B","C"], "values": [45,30,25]}',
            "pie": '{"labels": ["A","B","C"], "values": [45,30,25]}',
            "gauge": '{"value": 73, "min": 0, "max": 100, "label": "KPI", "target": 100}',
            "scatter": '{"points": [[1,2],[3,4]], "x_label": "X", "y_label": "Y"}',
            "sankey": '{"nodes": ["A","B","C"], "links": [{"source":"A","target":"C","value":50}]}',
            "funnel": '{"labels": ["Step1","Step2"], "values": [100,50]}',
            "heatmap": '{"x_labels": ["A","B"], "y_labels": ["X","Y"], "values": [[1,2],[3,4]]}',
        }
        fmt = data_formats.get(chart_type, data_formats["horizontal_bar"])

        prompt_sys = "Generate chart_data for this proof slide. Use REAL numbers from the document.\n\n"
        prompt_sys += "CLAIM: " + claim.get('claim_sentence', '') + "\n"
        prompt_sys += "CHART TYPE: " + chart_type + "\n"
        prompt_sys += "DATA TO EXTRACT: " + claim.get('data_description', '') + "\n\n"
        prompt_sys += "REQUIRED FORMAT for " + chart_type + ":\nchart_data: " + fmt + "\n\n"
        prompt_sys += "RULES:\n- Labels max 20 characters. Abbreviate.\n- Max 6 data points.\n"
        prompt_sys += "- Colors: RED #ef4444 for bad, GREEN #22c55e for good, BLUE #2563eb for neutral, GREY #d1d5db for context.\n"
        prompt_sys += "- ONE highlight color for the story, rest grey.\n\n"
        prompt_sys += 'Return JSON: {"chart_data": ...}'

        result = llm_json(
            prompt_sys,
            "SOURCE TEXT:\n" + final_text[:5000],
            model=HAIKU, max_tokens=1024
        )
        claim["chart_data"] = result.get("chart_data", {})
        return claim

    completed_slides = []
    with ThreadPoolExecutor(max_workers=min(len(claims), 4)) as executor:
        futures = {executor.submit(_gen_chart_data, c): c for c in claims}
        for future in as_completed(futures):
            try:
                slide = future.result()
                completed_slides.append(slide)
                print(f"      {C.GREEN}Slide {slide.get('appendix_num', '?')}: {slide.get('chart_type', '?')}{C.R}")
            except Exception as e:
                print(f"      {C.RED}Slide failed: {e}{C.R}")

    completed_slides.sort(key=lambda x: x.get("appendix_num", 0))
    slides = {"slides": completed_slides}

    # Save slide data
    app_dir = state.dir / "appendix"
    app_dir.mkdir(exist_ok=True)
    json.dump(slides, open(app_dir / "slides.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Render HTML
    slide_list = slides.get("slides", [])
    total = len(slide_list)
    e = html_mod.escape
    css = (ROOT / "presentation_engine" / "templates" / "appendix_slide.css").read_text(encoding="utf-8") if (ROOT / "presentation_engine" / "templates" / "appendix_slide.css").exists() else ""

    slides_html = ""
    charts_js = ""
    for s in slide_list:
        num = s.get("appendix_num", s.get("num", "?"))
        slot = s.get("slot_type", "?")
        slot_labels = {"A": "Prove a Number", "B": "Prove a Claim", "D": "Prove Executable"}
        title = e(s.get("action_title", ""))
        subtitle = e(s.get("subtitle", ""))
        conclusion = e(s.get("conclusion", ""))
        source = e(s.get("source_line", s.get("source", "")))
        canvas_id = f"ch-a{num}"

        # Build ECharts from chart_data using helper
        chart_html = ""
        div_id = f"chart-{num}"
        cd = s.get("chart_data", s.get("data", {}))
        chart_type = s.get("chart_type", "bar")
        echart_opt_str = None

        # Force gauge → horizontal_bar if the data has labels (categorical, not single KPI)
        if chart_type == "gauge" and isinstance(cd, dict) and cd.get("labels"):
            chart_type = "horizontal_bar"

        # Use our styled template (executive quality) from chart_data
        if isinstance(cd, dict) and (cd.get("labels") or cd.get("points") or cd.get("nodes") or cd.get("value") is not None):
            echart_opt_str = _build_echart_option(chart_type, cd)
        elif s.get("echart_option"):
            echart_opt_str = json.dumps(s["echart_option"], ensure_ascii=False)

        if echart_opt_str:
            charts_js += f"""
(function(){{var d=document.getElementById('{div_id}');if(!d)return;var c=echarts.init(d);c.setOption({echart_opt_str});window.addEventListener('resize',function(){{c.resize()}});}})();
"""
            chart_html = f'<div class="chart-area" id="{div_id}" style="width:100%;height:450px;min-height:400px"></div>'

        conc_html = f'<div class="slide-conclusion">{conclusion}</div>' if conclusion else ""

        slides_html += f'''<div class="slide" id="s{num}">
<div class="slide-inner">
<div class="slide-top"><span class="slide-num">Appendix {num}</span><span class="slide-slot">Slot {slot} | {e(slot_labels.get(slot, slot))}</span></div>
<h2 class="slide-title">{title}</h2>
<p class="slide-subtitle">{subtitle}</p>
{chart_html}
{conc_html}
<div class="slide-bottom"><div class="slide-source">{source}</div></div>
</div></div>\n'''

    appendix_html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Appendix</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>{css}</style></head><body>
<div class="progress" id="prog"></div>
{slides_html}
<div class="nav">
<button class="nav-btn" onclick="go(-1)">&larr;</button>
<span class="nav-counter" id="ctr">1/{total}</span>
<button class="nav-btn" onclick="go(1)">&rarr;</button>
</div>
<script>{charts_js}
const sl=document.querySelectorAll('.slide'),tot={total},pr=document.getElementById('prog'),ct=document.getElementById('ctr');let cur=0;
function go(d){{cur=Math.max(0,Math.min(tot-1,cur+d));sl[cur].scrollIntoView({{behavior:'smooth'}})}}
function up(){{let b=0;sl.forEach((s,i)=>{{if(s.getBoundingClientRect().top<innerHeight*.5)b=i}});cur=b;pr.style.width=((b+1)/tot*100)+'%';ct.textContent=(b+1)+'/'+tot}}
addEventListener('scroll',up);addEventListener('keydown',e=>{{if(e.key=='ArrowDown'||e.key=='ArrowRight')go(1);if(e.key=='ArrowUp'||e.key=='ArrowLeft')go(-1)}});up();
</script></body></html>'''

    path = state.dir / "appendix.html"
    path.write_text(appendix_html, encoding="utf-8")
    state.set("appendix_path", str(path))
    print(f"  {C.GREEN}Appendix: {total} slides, {len(appendix_html):,} chars{C.R}")
    return str(path)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Strategic Problem-Solving Pipeline")
    parser.add_argument("--topic", type=str, help="Topic to analyze")
    parser.add_argument("--audience", type=str, help="Target audience")
    parser.add_argument("--resume", type=str, help="Resume from run directory")
    parser.add_argument("--output", type=str, help="Output directory (use existing folder)")
    parser.add_argument("--autopilot", action="store_true", help="Run end-to-end without human checkpoints (coffee mode)")
    parser.add_argument("--hypothesis", type=str, default=None, help="Hypothesis-driven mode: provide your Day 1 answer to stress-test")
    args = parser.parse_args()
    AUTOPILOT = args.autopilot
    HYPOTHESIS_MODE = args.hypothesis is not None
    USER_HYPOTHESIS = args.hypothesis

    # On resume, detect mode from state.json if --hypothesis wasn't passed
    if args.resume and not HYPOTHESIS_MODE:
        _resume_state_path = Path(args.resume) / "state.json"
        if _resume_state_path.exists():
            _resume_state = json.load(open(_resume_state_path, encoding="utf-8"))
            if _resume_state.get("mode") == "hypothesis-driven":
                HYPOTHESIS_MODE = True
                USER_HYPOTHESIS = _resume_state.get("user_hypothesis", "")
                print(f"  Detected hypothesis-driven mode from previous run")

    clear()

    # Welcome — amber
    print(f"""
{C.AMBER}╔══════════════════════════════════════╗
║  ▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄    ║
║  █   A N V I L                █    ║
║  ▀▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▀    ║
║       ╲▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄╱             ║
║        ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀              ║
║  strategic problem engine  v0.1      ║
╚══════════════════════════════════════╝{C.R}
""")

    # Setup
    if args.resume:
        run_dir = Path(args.resume)
    elif args.output:
        run_dir = Path(args.output) if os.path.isabs(args.output) else OUTPUTS / "runs" / args.output
    elif args.topic:
        slug = args.topic[:40].lower().replace(" ", "_").replace("/", "_")
        run_dir = OUTPUTS / "runs" / slug
    else:
        print(f"  {C.RED}Provide --topic and --audience, or --resume{C.R}")
        sys.exit(1)

    global _run_dir
    _run_dir = run_dir

    state = State(run_dir)
    if args.topic:
        state.set("topic", args.topic)
    if args.audience:
        state.set("audience", args.audience)

    print(f"  Topic:    {C.BOLD}{state.get('topic')}{C.R}")
    print(f"  Audience: {C.BOLD}{state.get('audience')}{C.R}")
    print(f"  Output:   {C.BOLD}{run_dir}{C.R}")
    if state.step > 0:
        print(f"  {C.YELLOW}Resuming from Step {state.step}{C.R}")
    print()

    # Create input dirs
    (run_dir / "inputs" / "research").mkdir(parents=True, exist_ok=True)
    (run_dir / "inputs" / "hypothesis").mkdir(parents=True, exist_ok=True)

    # Telemetry — log run start
    log_run_start(state.get("topic", ""), state.get("audience", ""))
    _run_start_time = time.time()

    # Reset dashboard — always write current run's state, overwriting any previous run
    state.save()  # triggers update_dashboard which writes dashboard_state.js

    mece = None
    hyp_tree = None
    working_doc = ""
    synthesis = None

    # ── STEP 0 ──
    if state.step <= 0:
        summary, mece, AUTOPILOT = step0(state, autopilot=AUTOPILOT, hypothesis_mode=HYPOTHESIS_MODE)
        while True:
            action, detail = checkpoint(0, summary, autopilot=AUTOPILOT)
            if action == "quit":
                return
            elif action == "feedback":
                if HYPOTHESIS_MODE:
                    # In hypothesis mode, feedback revises the PS only
                    print(f"  {C.GREEN}Revising PS with feedback...{C.R}")
                    summary, mece, AUTOPILOT = step0(state, autopilot=AUTOPILOT, hypothesis_mode=True)
                else:
                    print(f"  {C.GREEN}Revising with feedback...{C.R}")
                    mece = llm_json(
                        "Revise this MECE decomposition based on feedback. Return same JSON structure.",
                        f"CURRENT:\n{json.dumps(mece, indent=2, ensure_ascii=False)}\n\nFEEDBACK: {detail}\n\nRevise."
                    )
                    json.dump(mece, open(state.dir / "mece" / "decomposition.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                    summary, _ = f"  {C.GREEN}Revised.{C.R}\n" + step0.__doc__, mece
                    summary, mece = step0(state, autopilot=AUTOPILOT)
            else:
                break
        state.complete(0)
    else:
        mece = json.load(open(state.get("mece_path"), encoding="utf-8"))

    # ══════════════════════════════════════════════════════════════
    # HYPOTHESIS-DRIVEN MODE: challenge → lock → skip to step 5
    # ══════════════════════════════════════════════════════════════
    if HYPOTHESIS_MODE and state.step <= 5:
        ps = mece.get("smart_statement", "")
        sens = mece.get("decision_sensitivity", "")

        # Load landscape scan + user data for challenge context
        ls_path = state.get("landscape_path")
        landscape_text = ""
        if ls_path and Path(ls_path).exists():
            ls_summary_path = Path(ls_path).parent / "landscape_summary.md"
            if ls_summary_path.exists():
                landscape_text = ls_summary_path.read_text(encoding="utf-8")
        # Append user data if injected
        ud_path = state.get("user_data_path")
        if ud_path and Path(ud_path).exists():
            landscape_text += "\n\n" + Path(ud_path).read_text(encoding="utf-8")

        # ── Challenge the user's Day 1 answer ──
        print(f"\n  {C.BOLD}{'='*55}{C.R}")
        print(f"  {C.YELLOW}{C.BOLD}HYPOTHESIS-DRIVEN MODE{C.R}")
        print(f"  {C.BOLD}{'='*55}{C.R}")
        print(f"\n  {C.BOLD}Your Day 1 answer:{C.R}")
        print(f"  {C.CYAN}{USER_HYPOTHESIS[:300]}{C.R}\n")

        challenge = llm_json(
            f"""You are stress-testing a user's Day 1 hypothesis. You have landscape scan data.

YOUR JOB: Find the weaknesses in THIS hypothesis. Poke holes. Name what could go wrong. DO NOT propose a different strategy.

For each challenge, be SPECIFIC:
- Name the assumption being tested
- Cite what the landscape data says that contradicts or complicates it
- State what would need to be true for this part of the hypothesis to hold

EXAMPLE:
User hypothesis: "Acquire 2-3 AI-native workflow companies by Q3 2027"
GOOD challenge: "Sana raised at $8B valuation in March 2026. Can Workday afford 2-3 acquisitions at these valuations without dilutive equity? The landscape shows AI-native HCM startups are priced at 40-60x revenue."
BAD challenge: "Instead of acquiring, Workday should build internally." (THIS IS A DIFFERENT STRATEGY — NOT YOUR JOB)

Today is {TODAY_STR}.

Return JSON: {{
  "assessment": "strong|needs_sharpening|fundamentally_flawed",
  "challenges": ["specific challenge to element 1 of hypothesis with landscape data", "specific challenge to element 2", "specific challenge to element 3"],
  "landscape_contradictions": "the single strongest piece of evidence from the landscape that threatens this hypothesis",
  "what_must_be_true": ["condition 1 for hypothesis to hold", "condition 2", "condition 3"],
  "confidence": "HIGH/MEDIUM/LOW",
  "key_reasoning": "2-3 sentences on overall strength/weakness"
}}""",
            f"PROBLEM STATEMENT: {ps}\n\nDECISION SENSITIVITY: {sens}\n\nUSER'S DAY 1 ANSWER: {USER_HYPOTHESIS}\n\nLANDSCAPE SCAN:\n{landscape_text[:8000]}",
            model=SONNET
        )

        assessment = challenge.get("assessment", "needs_sharpening")
        challenges_list = challenge.get("challenges", [])
        contradictions = challenge.get("landscape_contradictions", "")
        must_be_true = challenge.get("what_must_be_true", [])

        # The hypothesis stays as the user wrote it — challenge doesn't rewrite it
        sharpened = USER_HYPOTHESIS

        print(f"  {C.BOLD}ASSESSMENT: {assessment.upper()}{C.R}\n")
        if challenges_list:
            print(f"  {C.BOLD}Challenges to your hypothesis:{C.R}")
            for ch in challenges_list:
                print(f"    {C.YELLOW}• {ch[:200]}{C.R}")
        if contradictions:
            print(f"\n  {C.BOLD}Strongest contradiction from landscape:{C.R}")
            print(f"    {C.RED}{contradictions[:300]}{C.R}")
        if must_be_true:
            print(f"\n  {C.BOLD}For this hypothesis to hold, these must be true:{C.R}")
            for cond in must_be_true:
                print(f"    {C.DIM}• {cond[:150]}{C.R}")
        print(f"\n  {C.BOLD}Your hypothesis (unchanged):{C.R}")
        print(f"  {C.CYAN}{sharpened[:200]}{C.R}\n")

        # Hypothesis challenge pauses for user alignment in guided mode.
        # In autopilot via anvil.py, stdin is closed — the slash command handles alignment
        # BEFORE calling the pipeline, so auto-accept is correct there.
        if not AUTOPILOT:
            while True:
                print(f"\n  {C.BOLD}Current hypothesis:{C.R}")
                print(f"  {C.CYAN}{sharpened[:200]}{C.R}\n")
                print(f"  {C.DIM}accept / revise / Enter to accept{C.R}")
                try:
                    resp = input(f"  {C.YELLOW}>>> {C.R}").strip()
                except (EOFError, KeyboardInterrupt):
                    resp = "accept"
                if resp.lower() in ("accept", "approve", "lock", ""):
                    print(f"  {C.GREEN}Hypothesis locked.{C.R}\n")
                    break
                elif resp.lower() in ("revise", "edit"):
                    print(f"  {C.DIM}Type your revised hypothesis:{C.R}")
                    try:
                        new_hyp = input(f"  {C.YELLOW}> {C.R}").strip()
                    except (EOFError, KeyboardInterrupt):
                        new_hyp = ""
                    if new_hyp:
                        sharpened = new_hyp
                        print(f"  {C.GREEN}Updated.{C.R}")
                else:
                    sharpened = resp
                    print(f"  {C.GREEN}Updated: {sharpened[:120]}{C.R}")

        state.set("mode", "hypothesis-driven")
        state.set("user_hypothesis", USER_HYPOTHESIS)
        state.set("locked_governing", sharpened)

        # Build a lightweight working doc from landscape scan
        landscape_wd = f"# Working Document (Hypothesis-Driven Mode)\n\n"
        landscape_wd += f"**Problem:** {ps}\n**Date:** {TODAY_STR}\n"
        landscape_wd += f"**Mode:** Hypothesis-driven — testing user's Day 1 answer\n\n"
        landscape_wd += f"## Governing Hypothesis\n{sharpened}\n\n"
        landscape_wd += f"## Landscape Scan\n{landscape_text}\n"

        wd_dir = state.dir / "working_doc"
        wd_dir.mkdir(exist_ok=True)
        (wd_dir / "working_document.md").write_text(landscape_wd, encoding="utf-8")
        state.set("wd_path", str(wd_dir / "working_document.md"))
        working_doc = landscape_wd

        # Build a lightweight synthesis from landscape
        print(f"  {C.GREEN}Synthesizing landscape findings for hypothesis testing...{C.R}")
        hyp_synthesis = llm_json(
            f"""Extract findings, patterns, and inferences from this landscape scan. These will be used as the evidence base for hypothesis testing.

Return JSON: {{
  "findings": {{"key findings with specific data points, dates, sources"}},
  "patterns": {{"cross-cutting patterns and trends"}},
  "inferences": {{"so-what implications for the governing hypothesis"}}
}}""",
            f"PROBLEM: {ps}\n\nGOVERNING HYPOTHESIS: {sharpened}\n\nLANDSCAPE SCAN:\n{landscape_text[:15000]}",
            model=HAIKU
        )

        syn_dir = state.dir / "synthesis"
        syn_dir.mkdir(exist_ok=True)
        json.dump(hyp_synthesis, open(syn_dir / "synthesis.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        state.set("synthesis_path", str(syn_dir / "synthesis.json"))
        synthesis = hyp_synthesis

        # Skip steps 1-4, jump to step 5
        for skip_step in range(1, 5):
            state.complete(skip_step)

        print(f"""
  {C.BOLD}{'='*55}{C.R}
  {C.YELLOW}{C.BOLD}HYPOTHESIS-DRIVEN — SKIPPING TO DEEP TESTING{C.R}
  {C.BOLD}{'='*55}{C.R}

  {C.DIM}Skipped: MECE decomposition, broad research, working doc, synthesis{C.R}
  {C.DIM}Reason: You have a Day 1 answer. We test it directly.{C.R}

  {C.BOLD}What happens next:{C.R}
    {C.GREEN}1.{C.R} Decompose hypothesis into necessary conditions
    {C.GREEN}2.{C.R} Deep targeted web search on EVERY leaf (not just uncertain ones)
    {C.GREEN}3.{C.R} Stress test, kill propagation, iterate
    {C.GREEN}4.{C.R} Final brief + appendix from survivors

  {C.BOLD}Estimated:{C.R} ~10 min  |  ~$1-2 API cost
  {C.BOLD}{'='*55}{C.R}
""")

        # Now run step 5 with deep_research=True and the locked governing hypothesis
        summary, hyp_tree = step5_hypotheses(
            state, mece, working_doc, synthesis,
            autopilot=AUTOPILOT,
            deep_research=True,
            locked_governing=sharpened
        )
        while True:
            action, detail = checkpoint(5, summary,
                extra_cmds=[("add: <hypothesis>", "inject a hypothesis to test")], autopilot=AUTOPILOT)
            if action == "quit":
                return
            elif action == "add":
                state.add_input(5, "add", detail)
                print(f"  {C.GREEN}Added. Re-generating with your hypothesis...{C.R}")
                summary, hyp_tree = step5_hypotheses(state, mece, working_doc, synthesis, autopilot=AUTOPILOT, deep_research=True, locked_governing=sharpened)
            elif action == "feedback":
                print(f"  {C.GREEN}Revising hypotheses with your feedback...{C.R}")
                summary, hyp_tree = step5_hypotheses(state, mece, working_doc, synthesis, feedback=detail, autopilot=AUTOPILOT, deep_research=True, locked_governing=sharpened)
            else:
                break
        state.complete(5)

        # Skip to step 6 — converges with issue-driven path
        # (falls through to step 6 below)

    # ── ISSUE-DRIVEN PATH: steps 1-5 as normal ──
    if not HYPOTHESIS_MODE:

        # ── STEP 1 ──
        if state.step <= 1:
            summary, tree_path = step1(state, mece)
            action, _ = checkpoint(1, summary, html_path=tree_path, autopilot=AUTOPILOT)
            if action == "quit":
                return
            if action == "back":
                state.step = 0
                return main()
            state.complete(1)

        # ── 80/20 Tiering (runs once, before research) ──
        if state.step <= 2 and not state.get("tiers_path"):
            tier_questions(state, mece)
            # Save updated mece with tier labels
            json.dump(mece, open(state.get("mece_path"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

        # ── STEP 2: Research ──
        research_by_bucket = None
        if state.step <= 2:
            progress_bar(2)

            # Generate research brief (what data is needed)
            brief, total_must, total_nice = step2_research_brief(state, mece)

            # Ask human how to proceed
            choice, selected_items = research_input_prompt(state, brief, total_must, total_nice, autopilot=AUTOPILOT)

            if choice == "C":
                # Save and quit — human will gather research and resume
                print(f"\n  {C.GREEN}Progress saved. To resume:{C.R}")
                print(f"  {C.BOLD}1.{C.R} Review: {state.dir / 'research' / 'research_checklist.md'}")
                print(f"  {C.BOLD}2.{C.R} Drop files in: {state.dir / 'inputs' / 'research'}")
                print(f"  {C.BOLD}3.{C.R} Resume: python pipeline.py --resume {state.dir}\n")
                return

            human_data = []

            if choice == "B":
                # Scan for human-provided research files
                input_dir = state.dir / "inputs" / "research"
                files = scan_inputs(state.dir, "research")
                if not files:
                    print(f"\n  {C.YELLOW}No files found in {input_dir}{C.R}")
                    print(f"  {C.DIM}Drop your research files there and press Enter to scan again,{C.R}")
                    print(f"  {C.DIM}or type 'A' to proceed with public knowledge, or 'C' to quit.{C.R}\n")
                    while True:
                        try:
                            resp = input(f"  {C.YELLOW}[Enter to scan / A / C]: {C.R}").strip().upper()
                        except (EOFError, KeyboardInterrupt):
                            resp = "C"
                        if resp == "C":
                            return
                        elif resp == "A":
                            break
                        else:
                            files = scan_inputs(state.dir, "research")
                            if files:
                                break
                            print(f"  {C.YELLOW}Still no files found. Try again.{C.R}")
                if files:
                    print(f"  {C.GREEN}Extracting data from {len(files)} file(s)...{C.R}")
                    human_data = extract_from_files(files)

            elif choice == "D":
                # Selective input — combine direct data + any files
                direct_data = [item for item in selected_items if item.get("source") == "direct"]
                file_refs = [item for item in selected_items if item.get("source") == "file"]

                if direct_data:
                    # Package direct input as human_data
                    for d in direct_data:
                        human_data.append({"file": f"direct_input_{d['id']}", "findings": f"[{d['id']}] {d['data']}"})

                if file_refs:
                    files = scan_inputs(state.dir, "research")
                    if files:
                        print(f"  {C.GREEN}Extracting from {len(files)} file(s) for {len(file_refs)} items...{C.R}")
                        human_data.extend(extract_from_files(files))

            # Execute research + working doc (overlapped pipeline)
            print(f"\n  {C.GREEN}Steps 2+3: Research -> Working Document (overlapped pipeline)...{C.R}")

            sections = mece.get("sections", [])
            topic = state.get("topic", "")
            audience = state.get("audience", "")
            research_dir = state.dir / "research"
            research_dir.mkdir(exist_ok=True)
            wd_dir = state.dir / "working_doc"
            wd_dir.mkdir(exist_ok=True)

            human_answers = [h for h in state.data.get("human_inputs", []) if h["type"] == "answer"]
            wd_human_context = ""
            if human_answers:
                wd_human_context = "\n\nHUMAN-PROVIDED ANSWERS (treat as HIGH confidence):\n" + "\n".join(f"- {h['content']}" for h in human_answers)

            # Load current events if available
            ce_path = state.get("current_events_path")
            current_events_data = None
            if ce_path and Path(ce_path).exists():
                with open(ce_path, encoding="utf-8") as f:
                    ce_file = json.load(f)
                if isinstance(ce_file, dict):
                    # New format: landscape.json with "events" key
                    if "events" in ce_file:
                        current_events_data = ce_file.get("events", [])
                    # Old format: current_events.json with "all_results" key
                    elif "all_results" in ce_file:
                        current_events_data = ce_file.get("all_results", [])
                        print(f"  {C.DIM}(loaded old-format current events){C.R}")
                    elif "ranked" in ce_file:
                        current_events_data = ce_file.get("ranked", [])
                    else:
                        current_events_data = ce_file
                elif isinstance(ce_file, list):
                    current_events_data = ce_file

            # Phase 1: ALL web searches — sequential, throttled
            print(f"  {C.GREEN}Phase 1: Web search (sequential, {len(sections)} buckets)...{C.R}")
            search_data = _web_search_all_buckets(topic, sections, current_events=current_events_data)

            # Phase 2: ALL synthesis + working doc — parallel
            print(f"  {C.GREEN}Phase 2: Synthesis + Working Doc (parallel)...{C.R}")
            def _synth_and_wd(s):
                sid, r_text = _synthesize_one_bucket(topic, s, search_data, human_data if human_data else None, research_dir, current_events=current_events_data)
                _, title, wd_text = _working_doc_one_bucket(topic, audience, s, {sid: r_text}, "", state.dir, wd_human_context)
                return sid, r_text, title, wd_text

            research_by_bucket = {}
            wd_results = {}
            with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as executor:
                futures = {executor.submit(_synth_and_wd, s): s for s in sections}
                for future in as_completed(futures):
                    s = futures[future]
                    try:
                        sid, r_text, title, wd_text = future.result()
                        research_by_bucket[sid] = r_text
                        wd_results[sid] = (title, wd_text)
                        print(f"    {C.GREEN}Bucket {sid} done{C.R}")
                    except Exception as e:
                        print(f"    {C.RED}Bucket {s['section_id']} failed: {e}{C.R}")

            # Save research
            compiled = "\n\n---\n\n".join(research_by_bucket[sid] for sid in sorted(research_by_bucket.keys()))
            (research_dir / "compiled.md").write_text(compiled, encoding="utf-8")
            state.set("research_path", str(research_dir / "compiled.md"))
            research = compiled
            state.complete(2)

            # Save working doc
            wd_parts = [f"## Bucket {sid}: {wd_results[sid][0]}\n\n{wd_results[sid][1]}" for sid in sorted(wd_results.keys())]
            full_wd = f"# Working Document\n\n**Topic:** {topic}\n**Date:** {TODAY_STR}\n\n" + "\n\n---\n\n".join(wd_parts)
            (wd_dir / "working_document.md").write_text(full_wd, encoding="utf-8")
            state.set("wd_path", str(wd_dir / "working_document.md"))
            working_doc = full_wd
            state.complete(3)

            print(f"  {C.GREEN}Steps 2+3 done: {len(research_by_bucket)} buckets (parallel pipeline){C.R}")
        else:
            rp = state.get("research_path")
            research = Path(rp).read_text(encoding="utf-8") if rp and Path(rp).exists() else ""
            # If compiled.md is empty, rebuild from individual bucket files
            if not research.strip():
                research_dir = state.dir / "research"
                bucket_files = sorted(research_dir.glob("bucket_*.md"))
                if bucket_files:
                    parts = [bf.read_text(encoding="utf-8") for bf in bucket_files if bf.read_text(encoding="utf-8").strip()]
                    research = "\n\n---\n\n".join(parts)
                    if research.strip():
                        (research_dir / "compiled.md").write_text(research, encoding="utf-8")
                        print(f"  {C.DIM}Rebuilt compiled.md from {len(parts)} bucket files{C.R}")
            wp = state.get("wd_path")
            working_doc = Path(wp).read_text(encoding="utf-8") if wp and Path(wp).exists() else ""
            # If working doc is empty, try to rebuild from bucket files
            if not working_doc.strip():
                wd_dir = state.dir / "working_doc"
                wd_bucket_files = sorted(wd_dir.glob("bucket_*.md")) if wd_dir.exists() else []
                if wd_bucket_files:
                    wd_parts = [f.read_text(encoding="utf-8") for f in wd_bucket_files if f.read_text(encoding="utf-8").strip()]
                    if wd_parts:
                        working_doc = f"# Working Document\n\n**Topic:** {state.get('topic', '')}\n\n" + "\n\n---\n\n".join(wd_parts)
                        (wd_dir / "working_document.md").write_text(working_doc, encoding="utf-8")
                        print(f"  {C.DIM}Rebuilt working_document.md from {len(wd_parts)} bucket files{C.R}")

        # ── Research Debrief (generated once, before synthesis) ──
        debrief_path = state.dir / "research" / "debrief.md"
        if not debrief_path.exists() and working_doc:
            print(f"\n  {C.GREEN}Generating research debrief...{C.R}")
            ps = mece.get("smart_statement", "")

            # Include landscape scan data so the LLM knows it has real-time research
            landscape_context = ""
            ls_path = state.get("landscape_path")
            if ls_path and Path(ls_path).exists():
                ls_summary_path = Path(ls_path).parent / "landscape_summary.md"
                if ls_summary_path.exists():
                    landscape_context = ls_summary_path.read_text(encoding="utf-8")[:8000]

            debrief_text = llm(
                f"""Summarize the research findings in a 2-5 page debrief. Today is {TODAY_STR}.

    You've just completed research across multiple workstreams. Present what you found — clearly, precisely, like walking into the partner's office.

    IMPORTANT: The working document below was built from LIVE WEB RESEARCH conducted on {TODAY_STR} — real-time article fetches, news searches, and data pulls. You HAVE current information. Do NOT disclaim lack of real-time data. Do NOT add prefatory notes about your knowledge cutoff or evidentiary foundation. The research is the evidence — present it with confidence. If a specific data point could not be confirmed, flag that individual point, not the entire debrief.

    CRITICAL RULES FOR EVERY SINGLE FACT:
    - ALWAYS state the TIME PERIOD: "In FY25" / "As of March 2026" / "Over 2020-2025" / "In Q3 2025"
    - ALWAYS state the SOURCE: "per company 10-K" / "per EIA data" / "per industry estimates" / "per our analysis of public filings"
    - ALWAYS state the BASELINE for comparisons: "vs. $X in FY24" / "vs. industry average of Y%" / "compared to peer median of Z"
    - NEVER use vague cycle references: not "as the cycle normalised" but "as industry margins fell from X (Q1 2024, per source) to Y (Q4 2025, per source)"
    - NEVER use insider jargon without defining it on first use: always parenthetical explanation on first mention
    - NEVER present a finding without anchoring it in a specific number, date, and comparison

    BAD: "The margin premium has widened as the cycle normalised"
    GOOD: "The company's operating margin averaged 18.4% in FY25 (per quarterly earnings), a 5.2pp premium over the industry median (13.2%, per Capital IQ comps, same period) — this premium widened from 3.8pp in FY24, suggesting structural rather than cyclical advantage"

    BAD: "The capability gap versus peers is an architectural problem"
    GOOD: "Top 3 competitors invest 8-12% of revenue in R&D (per FY24 annual reports), vs. the company at 3.5% (per FY25 10-K). This 5-8pp gap has compounded over 2018-2025, resulting in a patent portfolio 4x smaller (per USPTO data) and a product release cadence 60% slower (per industry tracker)"

    TONE: Confident but precise. Every claim is anchored. A reader with zero context can follow every sentence.

    STRUCTURE (2-5 pages):

    1. **Bottom line up front** (3-4 sentences)
       The single most important thing we learned. What surprised us. What changes the framing. MUST include specific numbers, dates, and sources — even here.

    2. **What we found** (one section per research area, 3-5 bullets each)
       For each area:
       - Headline finding with number, time period, source, and comparison baseline
       - 2-3 supporting data points, each fully anchored
       - Flag LOW confidence findings with what's missing: "estimated at X (LOW — based on industry analogy, not company-specific data)"
       - Mark any finding that directly affects the decision sensitivity break point

    3. **What remains uncertain** (half page)
       - Where the analysis relies on estimates rather than confirmed data
       - What additional information from the client would sharpen the picture
       - State these naturally — "We do not have confirmed throughput data for March, but based on..." NOT "DATA GAP: throughput data unavailable"

    4. **Early signals** (half page)
       - 2-3 cross-cutting observations with the specific data that triggered them
       - Tensions or contradictions — name both sides with numbers
       - Anchored in facts, not vibes""",
                f"PROBLEM STATEMENT: {ps}\n\n{'LANDSCAPE SCAN (live web research, ' + TODAY_STR + '):\n' + landscape_context + '\n\n' if landscape_context else ''}WORKING DOCUMENT:\n{working_doc[:50000]}\n\nDebrief me on what you found. Every fact must have a time period, source, and comparison baseline."
            )
            debrief_md = f"# Research Debrief\n\n**Date:** {TODAY_STR}\n**Problem:** {ps[:200]}\n\n---\n\n{debrief_text}"
            debrief_path.write_text(debrief_md, encoding="utf-8")
            state.set("debrief_path", str(debrief_path))

            # Show debrief checkpoint
            # Truncate for terminal but full version in the file
            debrief_preview = debrief_text[:2500]
            if len(debrief_text) > 2500:
                debrief_preview += f"\n\n  {C.DIM}... (type 'view' to read full debrief){C.R}"
            debrief_summary = f"  {C.BOLD}RESEARCH DEBRIEF{C.R}\n  {C.DIM}{'_'*50}{C.R}\n\n{debrief_preview}"

            action, detail = checkpoint(3, debrief_summary, html_path=str(debrief_path), autopilot=AUTOPILOT)
            if action == "quit":
                return
            elif action == "back":
                state.step = 2
                return main()

        # ── STEP 4: Synthesis (human checkpoint) ──
        synthesis = None
        if state.step <= 4:
            summary, synthesis = step4_synthesis(state, mece, working_doc)
            while True:
                action, detail = checkpoint(4, summary,
                    extra_cmds=[("add: <insight>", "inject a pattern or finding you see")], autopilot=AUTOPILOT)
                if action == "quit":
                    return
                elif action == "back":
                    state.step = 1
                    return main()
                elif action == "add":
                    state.add_input(4, "add", detail)
                    print(f"  {C.GREEN}Added. Re-running synthesis with your input...{C.R}")
                    summary, synthesis = step4_synthesis(state, mece, working_doc)
                elif action == "feedback":
                    print(f"  {C.GREEN}Revising synthesis with your feedback...{C.R}")
                    summary, synthesis = step4_synthesis(state, mece, working_doc, feedback=detail)
                else:
                    break
            state.complete(4)
        else:
            sp = state.get("synthesis_path")
            synthesis = json.load(open(sp, encoding="utf-8")) if sp and Path(sp).exists() else {}

        # ── STEP 5: Hypotheses ──
        if state.step <= 5:
            summary, hyp_tree = step5_hypotheses(state, mece, working_doc, synthesis, autopilot=AUTOPILOT)
            while True:
                action, detail = checkpoint(5, summary,
                    extra_cmds=[("add: <hypothesis>", "inject a hypothesis to test")], autopilot=AUTOPILOT)
                if action == "quit":
                    return
                elif action == "back":
                    state.step = 4
                    return main()
                elif action == "add":
                    state.add_input(5, "add", detail)
                    print(f"  {C.GREEN}Added. Re-generating with your hypothesis...{C.R}")
                    summary, hyp_tree = step5_hypotheses(state, mece, working_doc, synthesis, autopilot=AUTOPILOT)
                elif action == "feedback":
                    print(f"  {C.GREEN}Revising hypotheses with your feedback...{C.R}")
                    summary, hyp_tree = step5_hypotheses(state, mece, working_doc, synthesis, feedback=detail, autopilot=AUTOPILOT)
                else:
                    break

            # ── Hypothesis proof: what evidence is needed? ──
            active_hyps = [h for h in hyp_tree.get("hypotheses", []) if h.get("status") != "killed"]
            data_gaps = hyp_tree.get("data_gaps", [])
            data_required = [h.get("data_required", "") for h in active_hyps if h.get("data_required")]

            if data_gaps or data_required:
                hyp_dir = state.dir / "hypotheses"
                hyp_dir.mkdir(exist_ok=True)
                input_dir = state.dir / "inputs" / "hypothesis"
                input_dir.mkdir(parents=True, exist_ok=True)

                # Generate proof requirements (client-aware)
                print(f"\n  {C.GREEN}Identifying evidence needed to prove/disprove hypotheses...{C.R}")
                audience = state.get("audience", "")
                ps = mece.get("smart_statement", "")
                proof_brief = llm_json(
                    f"""You are a research director. Hypotheses have been generated but some need additional evidence to confirm or disprove. Today is {TODAY_STR}.

    CLIENT CONTEXT:
    Problem statement: {ps}
    Audience: {audience}

    From the context, infer who the client is and what evidence they likely have access to internally. Generate SPECIFIC, TAILORED requests.

    For each active hypothesis, identify what SPECIFIC evidence would:
    1. CONFIRM it (make confidence HIGH)
    2. DISPROVE it (kill it)

    Classify each evidence item:
    - PUBLIC: available from public reports, databases, filings
    - PROPRIETARY: requires internal company data or systems
    - EXPERT: requires interviews or specialist judgment
    - FIELD: requires primary research or experiments

    FOR PROPRIETARY items — be specific:
    - Name the team, system, or document that would have it
    - State exactly what format would be useful
    - Frame as a direct ask: "Can your [team] provide [specific data]?"

    Return JSON:
    {{"proof_requirements": [
      {{"hypothesis_id": "H1", "hypothesis": "...", "current_confidence": "...",
        "to_confirm": [{{"id": "P1.1", "evidence_needed": "...", "source_type": "PUBLIC|PROPRIETARY|EXPERT|FIELD", "where_to_find": "...", "client_ask": "specific request to the client team"}}],
        "to_disprove": [{{"id": "D1.1", "evidence_needed": "...", "source_type": "PUBLIC|PROPRIETARY|EXPERT|FIELD", "where_to_find": "...", "client_ask": "..."}}]
      }}
    ],
    "total_items": 0}}""",
                    "HYPOTHESES:\n{hyps}\n\nDATA GAPS:\n{gaps}\n\nIdentify client-aware proof requirements.".format(
                        hyps=json.dumps([{"id": h.get("id"), "statement": h.get("statement"), "confidence": h.get("confidence"), "data_required": h.get("data_required", "")} for h in active_hyps], indent=2, ensure_ascii=False),
                        gaps=json.dumps(data_gaps, indent=2, ensure_ascii=False)
                    )
                )

                json.dump(proof_brief, open(hyp_dir / "proof_requirements.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

                # Write human-readable checklist
                proof_lines = [f"# Hypothesis Proof Requirements\n", f"**Generated:** {TODAY_STR}\n"]
                total_proof = 0
                proprietary_proof = []
                for pr in proof_brief.get("proof_requirements", []):
                    proof_lines.append(f"\n## {pr.get('hypothesis_id', '?')}: {pr.get('hypothesis', '')[:100]}")
                    proof_lines.append(f"**Current confidence:** {pr.get('current_confidence', '?')}\n")
                    proof_lines.append("### To Confirm:")
                    for item in pr.get("to_confirm", []):
                        proof_lines.append(f"- [ ] **{item['id']}** [{item.get('source_type', '?')}]: {item['evidence_needed']}")
                        if item.get("client_ask"):
                            proof_lines.append(f"  - **Ask:** {item['client_ask']}")
                        proof_lines.append(f"  - Where: {item.get('where_to_find', 'N/A')}")
                        total_proof += 1
                        if item.get("source_type") in ("PROPRIETARY", "EXPERT", "FIELD"):
                            proprietary_proof.append(item)
                    proof_lines.append("\n### To Disprove:")
                    for item in pr.get("to_disprove", []):
                        proof_lines.append(f"- [ ] **{item['id']}** [{item.get('source_type', '?')}]: {item['evidence_needed']}")
                        if item.get("client_ask"):
                            proof_lines.append(f"  - **Ask:** {item['client_ask']}")
                        proof_lines.append(f"  - Where: {item.get('where_to_find', 'N/A')}")
                        total_proof += 1
                        if item.get("source_type") in ("PROPRIETARY", "EXPERT", "FIELD"):
                            proprietary_proof.append(item)
                (hyp_dir / "proof_checklist.md").write_text("\n".join(proof_lines), encoding="utf-8")

                # Show options
                print(f"\n  {C.BOLD}HYPOTHESIS PROOF{C.R}")
                print(f"  {C.DIM}{'_'*50}{C.R}\n")
                print(f"  {total_proof} evidence items needed to prove/disprove {len(active_hyps)} hypotheses.")
                if proprietary_proof:
                    print(f"  {C.YELLOW}{len(proprietary_proof)} items need data from you or your client.{C.R}")
                print(f"  Proof checklist saved to: {C.BLUE}{hyp_dir / 'proof_checklist.md'}{C.R}\n")

                if AUTOPILOT:
                    print(f"  {C.DIM}[autopilot] proceeding with current evidence{C.R}\n")
                    proof_choice = "A"
                else:
                    print(f"  How would you like to proceed?\n")
                    print(f"    {C.BOLD}A{C.R}  Proceed with current evidence")
                    print(f"       {C.DIM}Some hypotheses may remain UNCERTAIN in the final document{C.R}")
                    print(f"    {C.BOLD}B{C.R}  I have evidence to upload (covers everything)")
                    print(f"       {C.DIM}Drop files in: {input_dir}{C.R}")
                    if proprietary_proof:
                        print(f"    {C.BOLD}D{C.R}  I can provide some evidence (selective)")
                        print(f"       {C.DIM}Review what's needed, provide what you have, skip the rest{C.R}")
                    print(f"    {C.BOLD}C{C.R}  Let me go gather this (save & quit)")
                    print(f"       {C.DIM}Review the checklist, gather data, resume later with --resume{C.R}")
                    print()

                    valid_proof = ["A", "B", "C"] + (["D"] if proprietary_proof else [])
                    while True:
                        try:
                            proof_choice = input(f"  {C.YELLOW}Choose [{'/'.join(valid_proof)}]: {C.R}").strip().upper()
                        except (EOFError, KeyboardInterrupt):
                            proof_choice = "C"
                        if proof_choice in valid_proof:
                            break
                        print(f"  {C.RED}Please enter {'/'.join(valid_proof)}{C.R}")

                if proof_choice == "C":
                    print(f"\n  {C.GREEN}Progress saved. To resume:{C.R}")
                    print(f"  {C.BOLD}1.{C.R} Review: {hyp_dir / 'proof_checklist.md'}")
                    print(f"  {C.BOLD}2.{C.R} Drop evidence in: {input_dir}")
                    print(f"  {C.BOLD}3.{C.R} Resume: python pipeline.py --resume {state.dir}\n")
                    return

                if proof_choice == "D":
                    # Selective evidence input
                    print(f"\n  {C.BOLD}EVIDENCE YOU CAN PROVIDE{C.R}")
                    print(f"  {C.DIM}{'_'*50}{C.R}\n")
                    print(f"  {C.DIM}For each item: type the data, 'skip' to proceed without, or 'file' if uploaded.{C.R}\n")

                    proof_evidence = []
                    for item in proprietary_proof:
                        print(f"  {C.BOLD}{item['id']}{C.R}")
                        if item.get("client_ask"):
                            print(f"  {C.CYAN}{item['client_ask']}{C.R}")
                        else:
                            print(f"  {item['evidence_needed']}")
                        print()
                        try:
                            resp = input(f"  {C.YELLOW}{item['id']} > {C.R}").strip()
                        except (EOFError, KeyboardInterrupt):
                            resp = "skip"

                        if resp.lower() == "skip" or not resp:
                            print(f"  {C.DIM}Skipped{C.R}\n")
                        elif resp.lower() == "file":
                            print(f"  {C.GREEN}Will extract from uploaded files{C.R}\n")
                            proof_evidence.append({"file": f"file_ref_{item['id']}", "findings": ""})
                        else:
                            print(f"  {C.GREEN}Got it{C.R}\n")
                            proof_evidence.append({"file": f"direct_{item['id']}", "findings": f"[{item['id']}] {resp}"})

                    # Also check for uploaded files
                    files = scan_inputs(state.dir, "hypothesis")
                    if files:
                        proof_evidence.extend(extract_from_files(files))

                    if proof_evidence:
                        real_evidence = [e for e in proof_evidence if e.get("findings")]
                        if real_evidence:
                            print(f"  {C.GREEN}Re-evaluating hypotheses with {len(real_evidence)} evidence item(s)...{C.R}")
                            evidence_text = "\n".join(f"From {e['file']}:\n{e['findings']}" for e in real_evidence)
                            update = llm_json(
                                """You have new evidence for hypothesis evaluation. For each hypothesis, check if the new evidence CONFIRMS, CONTRADICTS, or is NEUTRAL. Update confidence and status accordingly.

    Return JSON: {"updates": [{"id": "H1", "new_status": "confirmed/uncertain/killed", "new_confidence": "HIGH/MEDIUM/LOW", "evidence_impact": "..."}]}""",
                                f"HYPOTHESES:\n{json.dumps(hyp_tree, indent=2, ensure_ascii=False)}\n\nNEW EVIDENCE:\n{evidence_text}\n\nUpdate hypotheses."
                            )
                            for u in update.get("updates", []):
                                for h in hyp_tree.get("hypotheses", []):
                                    if h.get("id") == u.get("id"):
                                        h["status"] = u.get("new_status", h.get("status"))
                                        h["confidence"] = u.get("new_confidence", h.get("confidence"))
                                        h["evidence_update"] = u.get("evidence_impact", "")
                                        print(f"    {C.GREEN}{u['id']}: -> {u.get('new_status', '?')} ({u.get('new_confidence', '?')}){C.R}")
                            json.dump(hyp_tree, open(hyp_dir / "hypotheses.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                            state.set("hyp_path", str(hyp_dir / "hypotheses.json"))

                elif proof_choice == "B":
                    files = scan_inputs(state.dir, "hypothesis")
                    if not files:
                        print(f"\n  {C.YELLOW}No files found in {input_dir}{C.R}")
                        print(f"  {C.DIM}Drop files and press Enter, or type 'A' to proceed without.{C.R}\n")
                        while True:
                            try:
                                resp = input(f"  {C.YELLOW}[Enter to scan / A]: {C.R}").strip().upper()
                            except (EOFError, KeyboardInterrupt):
                                resp = "A"
                            if resp == "A":
                                break
                            files = scan_inputs(state.dir, "hypothesis")
                            if files:
                                break
                            print(f"  {C.YELLOW}Still no files. Try again.{C.R}")

                    if files:
                        print(f"  {C.GREEN}Extracting evidence from {len(files)} file(s)...{C.R}")
                        evidence = extract_from_files(files)
                        if evidence:
                            # Re-run hypothesis stress-test with new evidence
                            print(f"  {C.GREEN}Re-evaluating hypotheses with new evidence...{C.R}")
                            evidence_text = "\n".join(f"From {e['file']}:\n{e['findings']}" for e in evidence)
                            update = llm_json(
                                """You have new evidence for hypothesis evaluation. For each hypothesis, check if the new evidence CONFIRMS, CONTRADICTS, or is NEUTRAL. Update confidence and status accordingly.

    Return JSON: {"updates": [{"id": "H1", "new_status": "confirmed/uncertain/killed", "new_confidence": "HIGH/MEDIUM/LOW", "evidence_impact": "..."}]}""",
                                f"HYPOTHESES:\n{json.dumps(hyp_tree, indent=2, ensure_ascii=False)}\n\nNEW EVIDENCE:\n{evidence_text}\n\nUpdate hypotheses."
                            )
                            for u in update.get("updates", []):
                                for h in hyp_tree.get("hypotheses", []):
                                    if h.get("id") == u.get("id"):
                                        h["status"] = u.get("new_status", h.get("status"))
                                        h["confidence"] = u.get("new_confidence", h.get("confidence"))
                                        h["evidence_update"] = u.get("evidence_impact", "")
                                        print(f"    {C.GREEN}{u['id']}: -> {u.get('new_status', '?')} ({u.get('new_confidence', '?')}){C.R}")

                            # Re-save
                            json.dump(hyp_tree, open(hyp_dir / "hypotheses.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                            state.set("hyp_path", str(hyp_dir / "hypotheses.json"))

            state.complete(5)
        else:
            hp = state.get("hyp_path")
            hyp_tree = json.load(open(hp, encoding="utf-8")) if hp and Path(hp).exists() else {}

    # ── Ensure hyp_tree, synthesis, working_doc are loaded (both paths) ──
    if hyp_tree is None:
        hp = state.get("hyp_path")
        hyp_tree = json.load(open(hp, encoding="utf-8")) if hp and Path(hp).exists() else {}
    if not synthesis:
        sp = state.get("synthesis_path")
        synthesis = json.load(open(sp, encoding="utf-8")) if sp and Path(sp).exists() else {}
    if not working_doc:
        wp = state.get("wd_path")
        working_doc = Path(wp).read_text(encoding="utf-8") if wp and Path(wp).exists() else ""

    # ── STEP 6: Final Document ──
    if state.step <= 6:
        doc_path = step6_final_doc(state, mece, hyp_tree, working_doc, synthesis)
        while True:
            action, detail = checkpoint(6, f"  Final document generated ({Path(doc_path).stat().st_size:,} bytes)", html_path=doc_path, autopilot=AUTOPILOT)
            if action == "quit":
                return
            elif action == "back":
                state.step = 5
                return main()
            elif action == "feedback":
                print(f"  {C.GREEN}Revising final document with your feedback...{C.R}")
                doc_path = step6_final_doc(state, mece, hyp_tree, working_doc, synthesis, feedback=detail)
            else:
                break
        state.complete(6)

    # ── STEP 7: Appendix ──
    if state.step <= 7:
        app_path = step7_appendix(state, mece, hyp_tree, working_doc)
        while True:
            slide_count = len(json.load(open(state.dir / 'appendix' / 'slides.json', encoding='utf-8')).get('slides', []))
            action, detail = checkpoint(7, f"  Appendix: {slide_count} slides", html_path=app_path, autopilot=AUTOPILOT)
            if action == "quit":
                return
            elif action == "back":
                state.step = 6
                return main()
            elif action == "feedback":
                print(f"  {C.GREEN}Revising appendix with your feedback...{C.R}")
                app_path = step7_appendix(state, mece, hyp_tree, working_doc, feedback=detail)
            else:
                break
        state.complete(7)

    # ── Combine into single tabbed HTML ──
    combined_path = _build_combined_output(run_dir)

    # ── DONE ──
    print(f"""
{C.GREEN}{C.BOLD}{'='*60}
  PIPELINE COMPLETE
{'='*60}{C.R}

  {C.BOLD}Combined output:{C.R}
    {combined_path}

  {C.BOLD}Individual files:{C.R}
    {run_dir / 'final_document.html'}
    {run_dir / 'appendix.html'}
    {run_dir / 'tree.html'}
    {run_dir / 'synthesis' / 'synthesis.md'}
    {run_dir / 'working_doc' / 'working_document.md'}
""")


if __name__ == "__main__":
    main()

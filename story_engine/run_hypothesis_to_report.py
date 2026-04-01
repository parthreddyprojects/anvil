#!/usr/bin/env python3
"""
Steps 4-6: Hypothesis Tree -> One-Pager -> Condensed Report
Runs for all 4 PS: RIL, Nayara, IOCL/HMEL, Low-NCI PSU

Usage:
    python run_hypothesis_to_report.py          # all 4 PS
    python run_hypothesis_to_report.py --ps 1   # just PS1 (RIL)
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
import html as html_mod
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_THINK = "claude-sonnet-4-6"       # hypothesis generation + review
MODEL_FAST  = "claude-sonnet-4-6"       # one-pager, condensed report
MAX_TOKENS  = 16384
ROOT        = Path(__file__).parent
OUTPUTS     = ROOT.parent / "outputs"
MECE_DIR    = OUTPUTS / "mece_3ps"
WD_DIR      = OUTPUTS / "working_docs"
HYP_DIR     = OUTPUTS / "hypothesis_trees"
REPORT_DIR  = OUTPUTS / "reports"

# 4 Problem Statements — RIL split from Nayara, plus original PS2/PS3
PS_CONFIG = {
    1: {
        "name": "Reliance Industries (Jamnagar)",
        "short": "RIL",
        "source_ps": "ps1",  # which MECE/WD to pull from
        "focus": "Reliance Industries Jamnagar DTA+SEZ (1.4 mbpd). EXCLUDE Nayara/Vadinar — this is RIL only.",
        "brief_type": "crisis",
    },
    2: {
        "name": "Nayara Energy (Vadinar)",
        "short": "Nayara",
        "source_ps": "ps1",  # same source, different focus
        "focus": "Nayara Energy Vadinar (400 kbpd). EXCLUDE Reliance/Jamnagar — this is Nayara only. Focus on Rosneft SDN risk, 80-85% Russian dependency, existential liquidity.",
        "brief_type": "crisis",
    },
    3: {
        "name": "IOCL & HMEL (Mid-Tier PSU)",
        "short": "IOCL_HMEL",
        "source_ps": "ps2",
        "focus": "IOCL (Paradip, Panipat, Gujarat) and HMEL Bathinda. Mid-complexity PSU refiners sustaining operations under frozen retail prices.",
        "brief_type": "crisis",
    },
    4: {
        "name": "Low-Complexity PSU Refiners",
        "short": "LowNCI_PSU",
        "source_ps": "ps3",
        "focus": "HPCL Mumbai, BPCL Mumbai, BPCL Kochi, CPCL Manali, IOCL Bina, NRL Numaligarh. Survival mode — avoid cascade shutdown.",
        "brief_type": "crisis",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_client() -> anthropic.Anthropic:
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        for p in [ROOT.parent / ".env", ROOT.parent.parent / "iran-crisis-v2" / ".env"]:
            if p.exists():
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            if api_key:
                break
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(msg):
    line = f"[{ts()}] {msg}"
    print(line, flush=True)
    log_path = OUTPUTS / "pipeline_hypothesis.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def llm(client, system, user, model=MODEL_THINK, max_tokens=MAX_TOKENS):
    """Single LLM call, returns text."""
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


def llm_json(client, system, user, model=MODEL_THINK, max_tokens=MAX_TOKENS):
    """LLM call that returns parsed JSON."""
    raw = llm(client, system, user, model, max_tokens)
    # Strip markdown fences
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def load_working_doc(source_ps: str) -> str:
    """Load the working document markdown for a PS."""
    wd_path = WD_DIR / source_ps / "working_document.md"
    if wd_path.exists():
        return wd_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Working document not found: {wd_path}")


def load_mece(source_ps: str) -> dict:
    """Load the final MECE decomposition JSON."""
    mece_path = MECE_DIR / source_ps / "3_final.json"
    if mece_path.exists():
        return json.load(open(mece_path, encoding="utf-8"))
    raise FileNotFoundError(f"MECE not found: {mece_path}")


# ---------------------------------------------------------------------------
# STEP 4: Hypothesis Tree
# ---------------------------------------------------------------------------

HYPOTHESIS_SYSTEM = """You are a McKinsey senior partner building a hypothesis tree for a C-suite crisis brief.

You will receive a problem statement, MECE decomposition, and a working document with evidence.

Your job: generate 5-8 CORE HYPOTHESES that directly answer the problem statement. Not sub-questions -- assertive, testable claims about what the decision-maker should do and why.

CRITICAL RULES:
1. Every hypothesis must have a NUMBER and a THRESHOLD. "Margins are under pressure" is not a hypothesis. "$156/bbl basket generates +$5-7/bbl GRM at Jamnagar because NCI 21.1 complexity yields 216-grade flexibility" IS a hypothesis.
2. Every number must be DERIVED -- show the math or cite the source from the working document. Never state a breakeven, loss rate, or capacity figure without showing where it came from.
3. Every hypothesis must be INDEPENDENTLY TESTABLE. If two hypotheses are actually the same claim stated differently, merge them.
4. Each decision ask must be ATOMIC -- one decision per hypothesis, one owner, one deadline. Never bundle "call Aramco AND draw credit lines AND engage MoPNG" into one hypothesis. These are three separate testable claims.
5. Flag INTERNAL CONTRADICTIONS explicitly. If hypothesis A assumes crude is available but hypothesis B assumes procurement is blocked, resolve the contradiction or flag it.
6. For any number that requires LIVE DATA you do not have (current inventory levels, live prices, confirmed vessel positions, legal opinions), do NOT present estimates as facts. Instead mark them explicitly as DATA_REQUIRED with who needs to provide it and by when.

Each hypothesis must have:
- A clear, falsifiable statement with a number/threshold
- A break point: the specific value at which this hypothesis flips
- The DERIVATION of every key number (show the math from working doc data)
- Evidence FOR (from the working document, with source citation)
- Evidence AGAINST (contrarian -- the strongest counterargument)
- Confidence: HIGH (3+ evidence points, survives contrarian) / MEDIUM (structural estimate) / LOW (extrapolated, needs live data)
- Cascade effects: if this hypothesis is killed, what else changes?
- Data required: any live data needed to confirm/kill this hypothesis

Return JSON:
{
  "governing_hypothesis": "One sentence: what should the decision-maker do?",
  "hypotheses": [
    {
      "id": "H1",
      "statement": "Assertive claim with number and timeframe",
      "break_point": "The number at which this flips",
      "derivation": "How the key numbers were calculated from working doc data",
      "evidence_for": ["point 1 (source)", "point 2 (source)"],
      "evidence_against": ["strongest counterargument"],
      "confidence": "HIGH|MEDIUM|LOW",
      "confidence_basis": "why this confidence level",
      "cascade_if_killed": "what changes if this is wrong",
      "status": "confirmed|uncertain|killed",
      "data_required": ["specific data point needed, who provides it, by when"]
    }
  ],
  "data_gaps": [
    {
      "item": "what is needed",
      "owner": "who can provide it",
      "deadline": "by when",
      "impact_if_missing": "what decision is blocked without this"
    }
  ]
}
JSON only. No markdown."""


def step4_hypothesis_tree(client, ps_id: int, config: dict) -> dict:
    """Generate hypothesis tree for a PS."""
    log(f"  PS{ps_id} [{config['short']}] Step 4: Hypothesis Tree")

    source_ps = config["source_ps"]
    mece = load_mece(source_ps)
    wd = load_working_doc(source_ps)

    # Truncate working doc to fit context
    wd_truncated = wd[:60000]

    user_prompt = f"""PROBLEM STATEMENT:
{mece['smart_statement']}

DECISION SENSITIVITY:
{mece['decision_sensitivity']}

FOCUS: {config['focus']}

MECE BUCKETS ({len(mece['sections'])} buckets, {sum(len(s['questions']) for s in mece['sections'])} questions):
{json.dumps([{"id": s["section_id"], "title": s["title"], "num_questions": len(s["questions"])} for s in mece["sections"]], indent=2)}

WORKING DOCUMENT (evidence base):
{wd_truncated}

Generate 5-8 core hypotheses that ANSWER this problem statement for {config['name']}.
These are not questions — they are assertive claims about what to do.
Each must be testable and have a clear break point."""

    result = llm_json(client, HYPOTHESIS_SYSTEM, user_prompt)
    return result


# ---------------------------------------------------------------------------
# STEP 4B: Review & Prove/Disprove Hypotheses
# ---------------------------------------------------------------------------

REVIEW_SYSTEM = """You are a contrarian analyst reviewing a hypothesis tree. Your job is to stress-test each hypothesis against the evidence.

For each hypothesis:
1. Is the evidence sufficient to support the stated confidence level?
2. Is the break point realistic and correctly identified?
3. Is the contrarian argument the STRONGEST possible, or did the analyst go easy?
4. Are there cascade effects that were missed?
5. Should any hypothesis be KILLED based on the evidence?

Be harsh. If the evidence is weak, downgrade confidence. If the contrarian is stronger than the hypothesis, kill it.

Return JSON:
{
  "reviewed_hypotheses": [
    {
      "id": "H1",
      "original_status": "confirmed|uncertain|killed",
      "reviewed_status": "confirmed|uncertain|killed",
      "confidence_change": "unchanged|upgraded|downgraded",
      "new_confidence": "HIGH|MEDIUM|LOW",
      "review_notes": "What changed and why",
      "stronger_contrarian": "A better counterargument if the original was weak, or null",
      "missed_cascades": "Any missed cascade effects, or null"
    }
  ],
  "graveyard": [
    {
      "id": "H_killed",
      "statement": "the killed hypothesis",
      "killed_by": "the evidence that killed it",
      "resurrection_condition": "what would need to change to bring it back"
    }
  ],
  "overall_assessment": "One paragraph: is the hypothesis tree sound?"
}
JSON only."""


def step4b_review_hypotheses(client, ps_id: int, config: dict, hyp_tree: dict) -> dict:
    """LLM reviews and stress-tests the hypothesis tree."""
    log(f"  PS{ps_id} [{config['short']}] Step 4B: Review & Prove/Disprove")

    wd = load_working_doc(config["source_ps"])[:40000]

    user_prompt = f"""HYPOTHESIS TREE TO REVIEW:
{json.dumps(hyp_tree, indent=2)}

WORKING DOCUMENT (evidence base):
{wd}

FOCUS: {config['focus']}

Stress-test every hypothesis. Be harsh. Kill anything that doesn't hold up."""

    result = llm_json(client, REVIEW_SYSTEM, user_prompt)
    return result


def merge_review(hyp_tree: dict, review: dict) -> dict:
    """Merge review results back into hypothesis tree."""
    reviewed = {r["id"]: r for r in review.get("reviewed_hypotheses", [])}
    for h in hyp_tree.get("hypotheses", []):
        r = reviewed.get(h["id"])
        if r:
            h["status"] = r["reviewed_status"]
            h["confidence"] = r["new_confidence"]
            if r.get("review_notes"):
                h["review_notes"] = r["review_notes"]
            if r.get("stronger_contrarian"):
                h["evidence_against"] = [r["stronger_contrarian"]]

    hyp_tree["graveyard"] = review.get("graveyard", [])
    hyp_tree["overall_assessment"] = review.get("overall_assessment", "")
    return hyp_tree


# ---------------------------------------------------------------------------
# STEP 6: One-Pager
# ---------------------------------------------------------------------------

ONEPAGER_SYSTEM = """You are a McKinsey senior partner writing a one-page CEO crisis briefing.

The one-pager has 5 fixed sections in this exact order:

1. HEADER: Title = conclusion, not topic label. One sentence that states what should be decided.

2. SITUATION: 2-3 sentences max. One anchor number. What happens if nothing is done.

3. PERFORMANCE DATA: 3-4 KPIs only. Every KPI has a variance (vs baseline, vs target, vs peer). Never a raw number alone.

4. ANALYSIS: Pick ONE form based on brief type:
   - Crisis: Root causes (3 items max, each quantified)
   Format each as: "[Finding]. [Quantified impact]. [So what for the decision]."

5. DECISION REQUIRED: 2-3 numbered asks. Each specific. Each sized ($ amount or scope). No vague language.

Begin with a condensed version of the problem statement (2-3 sentences).

CRITICAL RULES:
1. Each DECISION must be ATOMIC -- one ask, one owner, one deadline. NEVER bundle multiple asks. "Secure PMO authority AND draw credit AND engage ADNOC" is THREE decisions.
2. Every number must be TRACEABLE to the hypothesis tree or working document. Show one-line derivation in parentheses.
3. Numbers must be INTERNALLY CONSISTENT. If situation says 60-70% crude at risk, analysis cannot recommend "aggressive run maximization" without resolving the contradiction.
4. DECISIONS must have a SEQUENCE -- state which decision gates which.
5. Any data point requiring LIVE VERIFICATION must be flagged as [REQUIRES VERIFICATION: source].

Return JSON:
{
  "condensed_ps": "2-3 sentence problem statement",
  "header": "Conclusion as title -- one sentence",
  "situation": "2-3 sentences, one anchor number, what happens if nothing done",
  "performance_data": [
    {"kpi": "name", "value": "current", "variance": "vs what", "direction": "up|down|flat", "source": "where this comes from"}
  ],
  "analysis": [
    {"finding": "root cause statement", "impact": "quantified (with derivation)", "so_what": "implication for decision"}
  ],
  "decisions": [
    {"number": 1, "ask": "specific, sized, atomic ask", "owner": "who decides", "deadline": "by when", "depends_on": "prior decision or null"}
  ],
  "data_required_before_signoff": [
    {"item": "what is needed", "owner": "who provides it", "deadline": "by when", "blocks": "which decision is blocked"}
  ]
}
JSON only."""


def step6_one_pager(client, ps_id: int, config: dict, hyp_tree: dict) -> dict:
    """Generate one-pager from hypothesis tree + working doc."""
    log(f"  PS{ps_id} [{config['short']}] Step 6: One-Pager")

    wd = load_working_doc(config["source_ps"])[:40000]
    mece = load_mece(config["source_ps"])

    user_prompt = f"""PROBLEM STATEMENT:
{mece['smart_statement']}

FOCUS: {config['focus']}

HYPOTHESIS TREE (reviewed):
{json.dumps(hyp_tree, indent=2)}

WORKING DOCUMENT (evidence):
{wd}

BRIEF TYPE: {config['brief_type']}

Write the one-pager for {config['name']}. Crisis brief format.
Begin with condensed problem statement."""

    result = llm_json(client, ONEPAGER_SYSTEM, user_prompt)
    return result


# ---------------------------------------------------------------------------
# STEP 6B: CEO Review of One-Pager
# ---------------------------------------------------------------------------

CEO_REVIEW_SYSTEM = """You are a Fortune 500 CEO reviewing a one-page crisis briefing prepared by your strategy team.

You have 3 minutes. You are impatient. You care about:
1. Is the recommendation clear and actionable?
2. Are the numbers credible? Do the KPIs actually support the recommendation?
3. Are the asks specific enough to approve right now, or do they need more work?
4. What's missing that you need before signing off?
5. Is this brief hiding uncertainty behind confident language?

Be direct. Flag problems. Don't be polite.

Return JSON:
{
  "verdict": "APPROVE|REVISE|REJECT",
  "clarity_score": 1-10,
  "actionability_score": 1-10,
  "credibility_score": 1-10,
  "problems": ["list of specific issues"],
  "missing": ["what you need that isn't here"],
  "suggested_changes": ["specific rewrites or additions"],
  "would_sign_off": true|false,
  "ceo_note": "One paragraph — your gut reaction as CEO"
}
JSON only."""


def step6b_ceo_review(client, ps_id: int, config: dict, one_pager: dict) -> dict:
    """CEO hat reviews the one-pager."""
    log(f"  PS{ps_id} [{config['short']}] Step 6B: CEO Review")

    user_prompt = f"""ONE-PAGER FOR YOUR REVIEW:

COMPANY: {config['name']}

CONDENSED PROBLEM STATEMENT:
{one_pager.get('condensed_ps', '')}

HEADER (recommendation):
{one_pager.get('header', '')}

SITUATION:
{one_pager.get('situation', '')}

PERFORMANCE DATA:
{json.dumps(one_pager.get('performance_data', []), indent=2)}

ANALYSIS:
{json.dumps(one_pager.get('analysis', []), indent=2)}

DECISIONS REQUIRED:
{json.dumps(one_pager.get('decisions', []), indent=2)}

Review this as CEO. 3 minutes. Be harsh."""

    result = llm_json(client, CEO_REVIEW_SYSTEM, user_prompt)
    return result


# ---------------------------------------------------------------------------
# STEP 5: Condensed Report (HTML)
# ---------------------------------------------------------------------------

def step5_condensed_report(ps_id: int, config: dict, mece: dict, hyp_tree: dict, one_pager: dict, ceo_review: dict) -> str:
    """Generate condensed report HTML. No LLM needed — just assembly."""
    log(f"  PS{ps_id} [{config['short']}] Step 5: Condensed Report (HTML)")

    h = html_mod.escape

    # Hypotheses HTML
    colors = ["#dc2626", "#f59e0b", "#2563eb", "#7c3aed", "#16a34a", "#0891b2", "#be123c", "#4f46e5"]
    conf_color = {"HIGH": "#16a34a", "MEDIUM": "#f59e0b", "LOW": "#dc2626"}
    conf_bg = {"HIGH": "#f0fdf4", "MEDIUM": "#fffbeb", "LOW": "#fef2f2"}

    hyp_html = ""
    for i, hyp in enumerate(hyp_tree.get("hypotheses", [])):
        c = colors[i % len(colors)]
        cc = conf_color.get(hyp.get("confidence", "MEDIUM"), "#f59e0b")
        cb = conf_bg.get(hyp.get("confidence", "MEDIUM"), "#fffbeb")
        status = hyp.get("status", "uncertain")
        status_icon = {"confirmed": "CONFIRMED", "killed": "KILLED", "uncertain": "UNCERTAIN"}.get(status, "?")

        hyp_html += f'''<div class="hyp">
<span class="ht" style="background:{c};color:#fff">{h(hyp.get("id",""))}</span>
<div>
<div class="hx">{h(hyp.get("statement",""))}</div>
<div class="hs">Break point: {h(hyp.get("break_point","N/A"))} | Status: <strong style="color:{cc}">{status_icon}</strong> ({hyp.get("confidence","?")})</div>
</div></div>\n'''

    # Graveyard HTML
    grave_html = ""
    for g in hyp_tree.get("graveyard", []):
        grave_html += f'<div class="kf" style="border-left-color:#dc2626;background:#fef2f2"><div class="kf-text"><strong>KILLED:</strong> {h(g.get("statement",""))} — {h(g.get("killed_by",""))}</div></div>\n'

    # One-pager HTML
    kpi_html = ""
    for kpi in one_pager.get("performance_data", []):
        kpi_html += f'''<div class="kpi-row">
<span class="kpi-name">{h(kpi.get("kpi",""))}</span>
<span class="kpi-val">{h(str(kpi.get("value","")))}</span>
<span class="kpi-var">{h(kpi.get("variance",""))}</span>
</div>\n'''

    analysis_html = ""
    for a in one_pager.get("analysis", []):
        analysis_html += f'<div class="finding"><strong>{h(a.get("finding",""))}</strong> {h(a.get("impact",""))} <em>{h(a.get("so_what",""))}</em></div>\n'

    decisions_html = ""
    for d in one_pager.get("decisions", []):
        decisions_html += f'<div class="decision"><span class="d-num">{d.get("number","")}</span>{h(d.get("ask",""))}</div>\n'

    # CEO review HTML
    ceo_verdict = ceo_review.get("verdict", "?")
    ceo_color = {"APPROVE": "#16a34a", "REVISE": "#f59e0b", "REJECT": "#dc2626"}.get(ceo_verdict, "#888")
    ceo_problems = "".join(f"<li>{h(p)}</li>" for p in ceo_review.get("problems", []))
    ceo_missing = "".join(f"<li>{h(m)}</li>" for m in ceo_review.get("missing", []))

    # Bucket findings from hypothesis tree
    buckets_html = ""
    for s in mece.get("sections", []):
        sid = s["section_id"]
        title = h(s["title"])
        buckets_html += f'<div class="bucket"><div class="bn">BUCKET {sid}</div><div class="bt">{title}</div></div>\n'

    # Data required before sign-off (from hypothesis tree + one-pager)
    data_gaps = []
    for gap in hyp_tree.get("data_gaps", []):
        data_gaps.append(gap)
    for gap in one_pager.get("data_required_before_signoff", []):
        data_gaps.append(gap)
    # Deduplicate by item
    seen = set()
    unique_gaps = []
    for g in data_gaps:
        key = g.get("item", "")[:50]
        if key not in seen:
            seen.add(key)
            unique_gaps.append(g)

    datagap_html = ""
    if unique_gaps:
        for g in unique_gaps:
            datagap_html += f'''<div class="dg-row">
<div class="dg-item">{h(g.get("item",""))}</div>
<div class="dg-meta"><strong>Owner:</strong> {h(g.get("owner","TBD"))} | <strong>Deadline:</strong> {h(g.get("deadline","ASAP"))} | <strong>Blocks:</strong> {h(g.get("blocks", g.get("impact_if_missing","")))}</div>
</div>\n'''

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(config["name"])} — Crisis Brief</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;max-width:880px;margin:0 auto;padding:40px 24px 80px;line-height:1.7;color:#1a1a1a;background:#fff}}
h1{{font:900 30px/1.15 'Inter';margin-bottom:6px}}
h2{{font:800 20px/1.2 'Inter';margin:44px 0 14px;padding-bottom:8px;border-bottom:2px solid #1a1a1a}}
p,li{{font:400 14px/1.7 'Inter';color:#333}}
strong{{color:#000}}
.meta{{font:400 12px/1.5 'Inter';color:#888;margin-bottom:28px}}
.ps-box{{background:#0a0a0a;color:#fff;padding:24px 28px;border-radius:8px;margin:24px 0}}
.ps-box p{{color:#ccc;font-size:13.5px;line-height:1.6}}
.ps-label{{font:700 10px/1 'JetBrains Mono';letter-spacing:2px;text-transform:uppercase;color:#ff3b3b;margin-bottom:10px}}
.sens{{background:#fef3c7;border-left:4px solid #f59e0b;padding:14px 18px;border-radius:0 8px 8px 0;margin:16px 0}}
.sens p{{font-size:13px;color:#92400e}}
.hyp{{display:grid;grid-template-columns:auto 1fr;gap:10px;padding:12px 0;border-bottom:1px solid #eee}}
.ht{{font:700 10px/1 'JetBrains Mono';padding:3px 8px;border-radius:4px;white-space:nowrap;height:fit-content}}
.hx{{font:500 13.5px/1.5 'Inter'}}
.hs{{font:400 11.5px/1.4 'Inter';color:#666;margin-top:3px}}
.kf{{padding:12px 16px;border-left:4px solid #888;border-radius:0 6px 6px 0;margin:8px 0}}
.kf-text{{font:400 13px/1.6 'Inter';color:#1a1a1a}}
.onepager{{background:#f8fafc;border:2px solid #1a1a1a;border-radius:12px;padding:28px;margin:24px 0}}
.op-header{{font:800 22px/1.2 'Inter';color:#1a1a1a;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid #1a1a1a}}
.op-section{{margin:16px 0}}
.op-label{{font:700 10px/1 'JetBrains Mono';letter-spacing:2px;text-transform:uppercase;color:#888;margin-bottom:8px}}
.kpi-row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee}}
.kpi-name{{font:500 13px/1 'Inter';color:#555}}
.kpi-val{{font:700 14px/1 'JetBrains Mono';color:#1a1a1a}}
.kpi-var{{font:500 12px/1 'Inter';color:#888}}
.finding{{padding:10px 0;border-bottom:1px solid #f0f0f0;font:400 13px/1.6 'Inter'}}
.decision{{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid #f0f0f0}}
.d-num{{font:800 24px/1 'JetBrains Mono';color:#dc2626;min-width:30px}}
.ceo-box{{border:2px solid {ceo_color};border-radius:8px;padding:20px;margin:16px 0}}
.ceo-verdict{{font:800 16px/1 'JetBrains Mono';color:{ceo_color};margin-bottom:8px}}
.bucket{{margin:8px 0;padding:12px 16px;background:#f9fafb;border-radius:6px;border:1px solid #e5e7eb}}
.bn{{font:800 10px/1 'JetBrains Mono';color:#2563eb;margin-bottom:2px}}
.bt{{font:600 13px/1.3 'Inter';color:#111}}
.dg-row{{padding:10px 14px;border-left:4px solid #dc2626;background:#fef2f2;border-radius:0 6px 6px 0;margin:6px 0}}
.dg-item{{font:500 13px/1.5 'Inter';color:#991b1b}}
.dg-meta{{font:400 11px/1.4 'Inter';color:#888;margin-top:2px}}
.foot{{font:400 11px/1.5 'Inter';color:#aaa;text-align:center;margin-top:48px;padding-top:20px;border-top:1px solid #eee}}
</style>
</head>
<body>

<h1>{h(config["name"])}: Crisis Brief</h1>
<div class="meta">Decision Deadline: April 3, 2026 | Indian Basket: $156/bbl</div>

<div class="ps-box">
<div class="ps-label">Problem Statement</div>
<p>{h(one_pager.get("condensed_ps", mece.get("smart_statement", "")))}</p>
</div>

<div class="sens">
<p><strong>Decision Sensitivity:</strong> {h(mece.get("decision_sensitivity", "")[:300])}</p>
</div>

<h2>Core Hypotheses</h2>
{hyp_html}

{f'<h2>Hypothesis Graveyard</h2>{grave_html}' if grave_html else ''}

<h2>One-Pager</h2>
<div class="onepager">
<div class="op-header">{h(one_pager.get("header", ""))}</div>

<div class="op-section">
<div class="op-label">Situation</div>
<p>{h(one_pager.get("situation", ""))}</p>
</div>

<div class="op-section">
<div class="op-label">Performance Data</div>
{kpi_html}
</div>

<div class="op-section">
<div class="op-label">Analysis</div>
{analysis_html}
</div>

<div class="op-section">
<div class="op-label">Decision Required</div>
{decisions_html}
</div>
</div>

<h2>CEO Review</h2>
<div class="ceo-box">
<div class="ceo-verdict">{ceo_verdict} (Clarity: {ceo_review.get("clarity_score","?")}/10 | Actionability: {ceo_review.get("actionability_score","?")}/10 | Credibility: {ceo_review.get("credibility_score","?")}/10)</div>
<p>{h(ceo_review.get("ceo_note", ""))}</p>
{f'<div class="op-section"><div class="op-label">Problems</div><ul>{ceo_problems}</ul></div>' if ceo_problems else ''}
{f'<div class="op-section"><div class="op-label">Missing</div><ul>{ceo_missing}</ul></div>' if ceo_missing else ''}
</div>

{f'<h2>Data Required Before Sign-Off</h2>{datagap_html}' if datagap_html else ''}

<h2>MECE Buckets ({len(mece.get("sections",[]))} buckets)</h2>
{buckets_html}

<div class="foot">Developed by Parth Reddy</div>
</body>
</html>'''
    return page


# ---------------------------------------------------------------------------
# Run pipeline for one PS
# ---------------------------------------------------------------------------

def run_ps(client, ps_id: int):
    config = PS_CONFIG[ps_id]
    short = config["short"]
    source_ps = config["source_ps"]

    log(f"{'='*60}")
    log(f"PS{ps_id}: {config['name']}")
    log(f"{'='*60}")

    # Create output dirs
    ps_dir = REPORT_DIR / short.lower()
    ps_dir.mkdir(parents=True, exist_ok=True)
    hyp_ps_dir = HYP_DIR / short.lower()
    hyp_ps_dir.mkdir(parents=True, exist_ok=True)

    mece = load_mece(source_ps)

    # Step 4: Hypothesis Tree
    hyp_tree = step4_hypothesis_tree(client, ps_id, config)
    (hyp_ps_dir / "hypotheses_raw.json").write_text(
        json.dumps(hyp_tree, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"  Hypotheses: {len(hyp_tree.get('hypotheses', []))} generated")

    # Step 4B: Review & Prove/Disprove
    review = step4b_review_hypotheses(client, ps_id, config, hyp_tree)
    (hyp_ps_dir / "review.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    hyp_tree = merge_review(hyp_tree, review)
    (hyp_ps_dir / "hypotheses_final.json").write_text(
        json.dumps(hyp_tree, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    confirmed = sum(1 for h in hyp_tree.get("hypotheses", []) if h.get("status") == "confirmed")
    killed = len(hyp_tree.get("graveyard", []))
    log(f"  Review: {confirmed} confirmed, {killed} killed, assessment: {review.get('overall_assessment', '')[:80]}")

    # Step 6: One-Pager
    one_pager = step6_one_pager(client, ps_id, config, hyp_tree)
    (ps_dir / "one_pager.json").write_text(
        json.dumps(one_pager, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"  One-pager: {one_pager.get('header', '')[:60]}")

    # Step 6B: CEO Review
    ceo_review = step6b_ceo_review(client, ps_id, config, one_pager)
    (ps_dir / "ceo_review.json").write_text(
        json.dumps(ceo_review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"  CEO verdict: {ceo_review.get('verdict', '?')} (clarity {ceo_review.get('clarity_score','?')}, actionability {ceo_review.get('actionability_score','?')}, credibility {ceo_review.get('credibility_score','?')})")

    # Step 5: Condensed Report HTML
    report_html = step5_condensed_report(ps_id, config, mece, hyp_tree, one_pager, ceo_review)
    report_path = ps_dir / "report.html"
    report_path.write_text(report_html, encoding="utf-8")
    log(f"  Report: {len(report_html):,} chars -> {report_path}")

    log(f"  PS{ps_id} [{short}] COMPLETE")
    return ps_id, short, report_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ps", type=int, help="Run single PS (1-4)")
    args = parser.parse_args()

    client = get_client()

    log("=" * 60)
    log("HYPOTHESIS -> ONE-PAGER -> REPORT PIPELINE")
    log("=" * 60)

    if args.ps:
        ps_ids = [args.ps]
    else:
        ps_ids = [1, 2, 3, 4]

    results = []
    for ps_id in ps_ids:
        if ps_id not in PS_CONFIG:
            log(f"ERROR: PS{ps_id} not configured")
            continue
        try:
            result = run_ps(client, ps_id)
            results.append(result)
        except Exception as e:
            log(f"  ERROR on PS{ps_id}: {e}")
            import traceback
            traceback.print_exc()

    log("")
    log("=" * 60)
    log("PIPELINE COMPLETE")
    log("=" * 60)
    for ps_id, short, path in results:
        log(f"  PS{ps_id} [{short}]: {path}")


if __name__ == "__main__":
    main()

import json, sys, os
sys.stdout.reconfigure(encoding="utf-8")
import anthropic
from dotenv import load_dotenv
load_dotenv()

key = os.environ.get("ANTHROPIC_API_KEY")
if not key:
    for p in [".env", "../iran-crisis-v2/.env"]:
        if os.path.exists(p):
            for line in open(p):
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
        if key:
            break
client = anthropic.Anthropic(api_key=key)

CRITIQUE_SYSTEM = """You are a McKinsey Senior Partner reviewing a one-pager before it goes to a CEO.

You care about:
1. STORY: headline tells CEO what to decide in one sentence. Situation creates urgency in 2 sentences. Analysis proves the headline.
2. PYRAMID: top-down logic. No data dumps.
3. BREVITY: 60 seconds. Every word earns its place. Flag anything >5 seconds to parse.
4. ACTION TITLES: conclusion not description. "Approve X by Y or Z happens" not "Overview of situation."
5. NUMBERS: max 3 numbers per field. Pick single most defensible number, not ranges. Ranges signal uncertainty.
6. JARGON: flag anything a non-oil CEO would not understand. CDU, NCI, SBM, bbl = jargon. Cash burn, days of supply = plain English.
7. SO-WHAT: every finding ends with what CEO should DO.

Return JSON:
{"story_score": 1-10, "brevity_score": 1-10, "problems": ["specific"], "fixes": ["specific rewrite"]}
JSON only."""

REWRITE_SYSTEM = """Rewrite this CEO one-pager based on critique. HARD RULES:
- Header: under 20 words, states the decision not the situation
- Situation: 2 sentences max, ONE anchor number, what happens if nothing done
- KPI values: ONE number each, no ranges. Pick the most defensible single figure.
- KPI variance: under 10 words
- Analysis findings: ONE sentence each, no compound sentences
- Decisions: start with verb (Approve/Authorize/Direct), under 25 words each
- Zero jargon — if a CEO at a tech company wouldn't understand it, rewrite it
Return same JSON structure. JSON only."""


def strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return t


for ps in ["iocl_hmel", "lownci_psu"]:
    ceo_path = f"outputs/reports/{ps}/one_pager_ceo.json"
    if os.path.exists(ceo_path):
        op = json.load(open(ceo_path, encoding="utf-8"))
    else:
        op = json.load(open(f"outputs/reports/{ps}/one_pager.json", encoding="utf-8"))

    print(f"=== CRITIQUING {ps} ===")

    # Step 1: MBB critique
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=CRITIQUE_SYSTEM,
        messages=[{"role": "user", "content": "Critique this one-pager:\n" + json.dumps(op, indent=2, ensure_ascii=False)}],
    )
    critique = json.loads(strip_fences(resp.content[0].text))

    print(f"  Story: {critique.get('story_score')}/10 | Brevity: {critique.get('brevity_score')}/10")
    for p in critique.get("problems", []):
        print(f"  PROBLEM: {p[:150]}")

    json.dump(critique, open(f"outputs/reports/{ps}/mbb_critique.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # Step 2: Apply fixes
    print(f"  Rewriting...")
    resp2 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=REWRITE_SYSTEM,
        messages=[{
            "role": "user",
            "content": "ONE-PAGER:\n" + json.dumps(op, indent=2, ensure_ascii=False) + "\n\nCRITIQUE:\n" + json.dumps(critique, indent=2, ensure_ascii=False) + "\n\nApply all fixes.",
        }],
    )
    new_op = json.loads(strip_fences(resp2.content[0].text))

    json.dump(new_op, open(f"outputs/reports/{ps}/one_pager_final.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"  HEADER: {new_op.get('header', '')[:120]}")
    for k in new_op.get("performance_data", []):
        print(f"  KPI: {k.get('kpi', '')}: {k.get('value', '')}")
    for d in new_op.get("decisions", []):
        print(f"  D{d.get('number', '')}: {d.get('ask', '')[:120]}")
    print()

    # Step 3: Regenerate HTML
    sys.path.insert(0, "story_engine")
    from gen_onepager_appendix import render_onepager_html, PS_MAP
    html = render_onepager_html(ps, PS_MAP[ps], new_op)
    open(f"outputs/reports/{ps}/onepager.html", "w", encoding="utf-8").write(html)
    print(f"  HTML: {len(html):,} chars")

print("Done")

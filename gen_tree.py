import json, html as h

with open("outputs/mece_3ps/ps1/3_final.json", encoding="utf-8") as f:
    d = json.load(f)

LABELS = {
    1: {
        "1.1": "Crude inventory days & autonomous operation window",
        "1.2": "Russian cargoes in transit & war-risk status",
        "1.3": "OFAC waiver status & banking disruption risk",
        "1.4": "ME term contracts & force majeure clauses",
        "1.5": "Product inventory by grade",
        "1.6": "Derivatives mark-to-market & covenant risk",
        "1.7": "Port infrastructure: SBMs, jetties, draft limits",
        "1.8": "Export commitments & penalty clauses",
        "1.9": "MRPL shutdown gap by product grade",
        "1.10": "Credit line headroom for spot procurement",
        "1.11": "Rosneft SDN ownership contagion",
        "1.12": "Product evacuation logistics capacity",
        "1.13": "Petrochemical feedstock position",
        "1.14": "Current crude diet vs. design envelope",
        "1.15": "NOC force majeure notices",
    },
    2: {
        "2.1": "West African spot availability",
        "2.2": "US crude economics & CDU compatibility",
        "2.3": "CPC Blend (Caspian) viability",
        "2.4": "North African crudes (Libya, Algeria)",
        "2.5": "At-sea VLCC cargo diversions",
        "2.6": "Crude compatibility matrix per refinery",
        "2.7": "Saudi Aramco Red Sea / Yanbu route",
        "2.8": "All-in cost differential vs. Russian baseline",
        "2.9": "Domestic Indian crude (ONGC, OIL)",
        "2.10": "War-risk insurance & P&I availability",
        "2.11": "Kazakh crude via BTC / Ceyhan",
        "2.12": "Iraqi Kirkuk via Ceyhan (non-Hormuz)",
        "2.13": "Procurement tenor: spot vs. term",
        "2.14": "Fujairah / Singapore blending hub",
    },
    3: {
        "3.1": "CDU utilization rate & max sustainable throughput",
        "3.2": "Yield shift from heavy-sour to light-sweet",
        "3.3": "Secondary unit bottlenecks (HCU, FCC, coker)",
        "3.4": "Hydrogen generation capacity",
        "3.5": "Turnaround deferral NPV",
        "3.6": "Cut point optimization for diesel/jet",
        "3.7": "Naphtha absorption by petrochemical complex",
        "3.8": "Utility constraints (steam, cooling, power)",
        "3.9": "Environmental consent limits at max throughput",
        "3.10": "Aggregate incremental product volume",
        "3.11": "Sulfur recovery unit capacity",
        "3.12": "Desalter limits with alternative crudes",
        "3.13": "Fuel oil yield & residue upgrading economics",
        "3.14": "Catalyst inventory & replenishment lead times",
    },
    4: {
        "4.1": "Crack spreads by destination (Singapore, Rotterdam)",
        "4.2": "PSU OMC replacement volume & pricing",
        "4.3": "Export infrastructure throughput ceiling",
        "4.4": "SEZ domestic diversion flexibility",
        "4.5": "Product tanker availability & freight",
        "4.6": "Naphtha: export vs. domestic vs. internal cracker",
        "4.7": "Aviation fuel supply gap (MRPL airports)",
        "4.8": "Domestic market absorption capacity",
        "4.9": "FX hedging on USD export revenue",
        "4.10": "Existing export contract optionality",
        "4.11": "LPG domestic obligation & government mandate risk",
        "4.12": "Product quality spec compliance on new crude diet",
        "4.13": "South Asian regional export (Bangladesh)",
        "4.14": "DTA domestic supply obligation quantum",
    },
    5: {
        "5.1": "Incremental working capital at $156/bbl",
        "5.2": "Derivative book exposure & margin calls",
        "5.3": "Crack spread hedge: lock or leave open?",
        "5.4": "Speculative long crude position?",
        "5.5": "War-risk insurance P&L impact",
        "5.6": "SEZ tax advantage (export vs. domestic)",
        "5.7": "Contango storage trade viability",
        "5.8": "Counterparty credit quality under stress",
        "5.9": "EBITDA stress test: base vs. worst case",
        "5.10": "Above-capacity crude trading opportunity",
        "5.11": "Standalone liquidity runway",
        "5.12": "Contingent liabilities & cross-default risk",
        "5.13": "PSU OMC receivables concentration",
    },
    6: {
        "6.1": "Hormuz reopening scenario probabilities",
        "6.2": "Inventory loss exposure on crisis-price crude",
        "6.3": "Procurement halt triggers",
        "6.4": "Government export duty / windfall tax risk",
        "6.5": "Insurance withdrawal contingency",
        "6.6": "Russia waiver extension probability",
        "6.7": "Cyber threat posture (DCS/SCADA)",
        "6.8": "RIL-Nayara mutual support protocol",
        "6.9": "Decision authority matrix & escalation thresholds",
        "6.10": "Government forced disclosure risk",
        "6.11": "Maritime incident contingency (VLCC loss)",
        "6.12": "Demand destruction scenario",
        "6.13": "Nayara existential risk (Rosneft SDN)",
    },
    7: {
        "7.1": "MoPNG Secretary engagement",
        "7.2": "KASEZ: SEZ domestic sale permission",
        "7.3": "OFAC counsel: written legal opinion",
        "7.4": "Rosneft board engagement (Nayara)",
        "7.5": "Saudi Aramco / ADNOC emergency uplift",
        "7.6": "War-risk & P&I insurance broker status",
        "7.7": "RBI banking: emergency LC facility",
        "7.8": "PSU OMC product supply offers",
        "7.9": "ISPRL emergency SPR release",
        "7.10": "Indian Navy escort coordination",
        "7.11": "Ministry of Ports facilitation",
        "7.12": "Gujarat Maritime Board pre-clearance",
        "7.13": "MEA diplomatic channel (US, Gulf states)",
        "7.14": "Parliamentary / media communication prep",
    },
    8: {
        "8.1": "Five-gate decision dependency map",
        "8.2": "Irreversibility map & reversibility premium",
        "8.3": "24/48/72-hour decision triage",
        "8.4": "RIL-Nayara commercial arrangements",
        "8.5": "Crisis command structure & comms cascade",
    },
    9: {
        "9.1": "PSU OMC supply → durable term conversion",
        "9.2": "Forced diversification → structural relationships",
        "9.3": "Permanent Russian crude loss GRM impact",
        "9.4": "Required capex response ($400-800M)",
        "9.5": "ISPRL Phase II policy shaping",
    },
}

# Build tree: PS → Buckets → Questions (short label, full question on hover)
branches = ""
for s in d["sections"]:
    sid = s["section_id"]
    # Short bucket label: just the first phrase before the colon
    raw_title = s["title"]
    short = raw_title.split(":")[0].strip() if ":" in raw_title else raw_title
    short = h.escape(short)
    full_title = h.escape(raw_title)

    # Hand-crafted short headers per question
    labels = LABELS.get(sid, {})
    leaves = ""
    for q in s["questions"]:
        qid = q["id"]
        qt = q["question"]
        label = labels.get(qid, qid)
        leaves += f'<div class="leaf" title="{h.escape(qt)}"><span class="lid">{qid}</span>{h.escape(label)}</div>\n'

    branches += f'''<div class="branch">
<div class="bnode" title="{full_title}"><span class="bnum">{sid}</span>{short}</div>
<div class="leaves">{leaves}</div>
</div>\n'''

page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Issue Tree — RIL 72-Hour Crisis Brief</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#fff;color:#1a1a1a;overflow-x:auto}}
.header{{max-width:880px;margin:0 auto;padding:40px 24px 0}}
h1{{font:900 30px/1.15 'Inter';margin-bottom:6px}}
.meta{{font:400 12px/1.5 'Inter';color:#888;margin-bottom:20px}}
.tabs{{display:flex;gap:0;margin-bottom:24px;border-bottom:2px solid #e5e7eb}}
.tab{{font:600 13px/1 'Inter';padding:10px 20px;color:#888;text-decoration:none;border-bottom:2px solid transparent;margin-bottom:-2px}}
.tab:hover{{color:#1a1a1a}}
.tab.active{{color:#2563eb;border-bottom-color:#2563eb}}
.hint{{font:400 11px/1.4 'Inter';color:#aaa;margin-bottom:16px}}

/* Tree layout — horizontal */
.tree-wrap{{overflow-x:auto;padding:0 24px 60px}}
.tree{{display:flex;align-items:flex-start;gap:0;min-width:max-content}}

/* Root node */
.root{{flex-shrink:0;width:220px;background:#0a0a0a;color:#fff;padding:16px 18px;border-radius:8px;font:600 12px/1.5 'Inter';position:relative}}
.root .ps-label{{font:700 9px/1 'JetBrains Mono';letter-spacing:1.5px;text-transform:uppercase;color:#ff3b3b;margin-bottom:6px}}
.root p{{font:400 11.5px/1.5 'Inter';color:#ccc}}

/* Connector from root to branches column */
.connector{{flex-shrink:0;width:32px;display:flex;align-items:center;justify-content:center;position:relative}}
.connector::after{{content:'';width:100%;height:2px;background:#d1d5db}}

/* Branches column */
.branches{{display:flex;flex-direction:column;gap:3px;position:relative}}
.branches::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:#d1d5db}}

/* Branch = bucket node + its leaves */
.branch{{display:flex;align-items:flex-start;gap:0;position:relative}}
.branch::before{{content:'';position:absolute;left:0;top:15px;width:12px;height:2px;background:#d1d5db}}

/* Bucket node */
.bnode{{flex-shrink:0;margin-left:12px;padding:6px 12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:5px;font:600 11px/1.4 'Inter';color:#1e40af;cursor:default;white-space:nowrap;position:relative}}
.bnode:hover{{background:#dbeafe}}
.bnum{{font:800 10px/1 'JetBrains Mono';color:#2563eb;margin-right:4px}}

/* Connector from bucket to leaves */
.branch>.leaves{{display:flex;flex-direction:column;gap:2px;margin-left:0;position:relative}}
.branch>.leaves::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:#e5e7eb}}

/* Leaf = sub-question */
.leaf{{margin-left:12px;padding:4px 10px;background:#f9fafb;border:1px solid #f0f0f0;border-radius:4px;font:400 10px/1.4 'Inter';color:#555;cursor:default;white-space:nowrap;position:relative;max-width:340px;overflow:hidden;text-overflow:ellipsis}}
.leaf::before{{content:'';position:absolute;left:-12px;top:11px;width:12px;height:2px;background:#e5e7eb}}
.leaf:hover{{background:#fef3c7;border-color:#fcd34d;color:#1a1a1a;white-space:normal;max-width:500px;z-index:10;position:relative;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
.lid{{font:700 9px/1 'JetBrains Mono';color:#2563eb;margin-right:3px}}

.foot{{max-width:880px;margin:0 auto;padding:20px 24px;font:400 11px/1.5 'Inter';color:#aaa;text-align:center;border-top:1px solid #eee}}
</style>
</head>
<body>

<div class="header">
<div class="tabs">
<a class="tab" href="report.html">Report</a>
<a class="tab active" href="tree.html">Issue Tree</a>
</div>
<h1>Issue Tree</h1>
<div class="meta">Horizontal MECE decomposition. Hover any node for the full question.</div>
</div>

<div class="tree-wrap">
<div class="tree">

<div class="root">
<div class="ps-label">Problem Statement</div>
<p>What should RIL (Jamnagar, 1.4 mbpd) decide in 72 hours on crude sourcing, run-rates, exports, and balance sheet &mdash; to capture $4&ndash;6/bbl GRM uplift at $156/bbl basket?</p>
</div>

<div class="connector"></div>

<div class="branches">
{branches}
</div>

</div>
</div>

<div class="foot">Developed by Parth Reddy</div>

</body>
</html>'''

with open("ps1_reliance/tree.html", "w", encoding="utf-8") as f:
    f.write(page)
print(f"Tree: {len(page):,} chars")

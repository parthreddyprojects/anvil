#!/usr/bin/env python3
"""
Step 1: Research pipeline v2.
  - Uses keyword-based dedup (no LLM needed for grouping)
  - Parallel research agents via ThreadPoolExecutor
  - Saves each theme's research as a separate file

Usage:
    python run_research_v2.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
ROOT = Path(__file__).parent
OUTPUTS = ROOT.parent / "outputs"
MECE_DIR = OUTPUTS / "mece_3ps"
RESEARCH_DIR = OUTPUTS / "research"
BRIEFS_DIR = RESEARCH_DIR / "briefs"

# ---------------------------------------------------------------------------
# Research Theme Definitions (manual 80/20 grouping)
# ---------------------------------------------------------------------------

RESEARCH_THEMES = [
    # ---- COMMON THEMES (apply across PS1/PS2/PS3) ----
    {
        "theme_id": "C01",
        "title": "Crude Oil Prices, Forward Curves & Indian Basket",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["crude price", "indian basket", "brent", "dubai", "forward curve", "futures", "$156", "$142", "price trajectory", "price collapse"],
        "research_brief": (
            "Find current and forward crude oil prices as of late March 2026:\n"
            "1. Brent spot, WTI spot, Dubai/Oman spot ($/bbl)\n"
            "2. Indian basket price (0.72*Dubai + 0.28*Brent) — current and 30/60/90 day forwards\n"
            "3. Brent futures curve shape — contango or backwardation, and by how much\n"
            "4. Crack spreads: Singapore diesel, jet fuel, naphtha vs Brent\n"
            "5. Historical parallels: what happened to crude prices in past Hormuz/Gulf crises\n"
            "6. Price scenarios: if Hormuz reopens in 7/30/90 days, estimated price impact\n"
            "Sources: EIA, Platts, Argus, ICE futures, CME, Reuters, Bloomberg"
        ),
    },
    {
        "theme_id": "C02",
        "title": "Russia Sanctions Waiver — Status, Probability, Implications",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["russia", "waiver", "OFAC", "sanctions", "april 3", "ESPO", "urals", "rosneft", "secondary sanctions", "waiver expir"],
        "research_brief": (
            "Research the India-Russia crude oil sanctions waiver:\n"
            "1. Current status of OFAC waiver for Indian purchases of Russian crude — exact expiry date, scope, entities covered\n"
            "2. US administration signals on renewal/extension — State Dept, Treasury statements\n"
            "3. Volume of Russian crude currently flowing to India (mbpd) by grade (ESPO, Urals, Sokol)\n"
            "4. Which Indian refiners are most dependent on Russian crude (% of intake)\n"
            "5. Urals-to-Brent and ESPO-to-Brent discount currently offered\n"
            "6. Legal consequences of purchasing without waiver — secondary sanctions mechanism, banking risk\n"
            "7. Historical precedent: how have India/China handled similar sanctions deadlines\n"
            "8. Alternative payment mechanisms (rupee-ruble, UAE intermediary)\n"
            "Sources: OFAC notices, US Treasury, Reuters, S&P Global Platts, Indian MoPNG statements"
        ),
    },
    {
        "theme_id": "C03",
        "title": "Hormuz Strait Status — Military Situation & Reopening Scenarios",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["hormuz", "strait", "mine", "mining", "military", "iran", "israel", "ceasefire", "escalat", "march 28", "strike pause", "reopening"],
        "research_brief": (
            "Research the Iran-Israel Hormuz crisis military and diplomatic status:\n"
            "1. Current status of Strait of Hormuz — confirmed mining, shipping lane closures, naval deployments\n"
            "2. March 28 strike-pause deadline — what happens if not extended\n"
            "3. Diplomatic channels active — UN, US mediation, Gulf state positions\n"
            "4. Three scenarios with probability estimates:\n"
            "   a) Rapid diplomatic resolution (Hormuz reopens <14 days)\n"
            "   b) Prolonged standoff (30-90 day partial closure)\n"
            "   c) Escalation (full closure, tanker attacks, regional spread)\n"
            "5. Historical mine-clearing timeline (Iran-Iraq war precedent: 2-6 months)\n"
            "6. Insurance and shipping industry response — which routes are declared no-go\n"
            "Sources: Reuters, Al Jazeera, CENTCOM, Lloyd's List, Maritime security advisories"
        ),
    },
    {
        "theme_id": "C04",
        "title": "Alternative Crude Sources — Availability, Price, Delivery Windows",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["alternative crude", "west africa", "nigeria", "angola", "bonny light", "US crude", "WTI", "brazil", "guyana", "north sea", "caspian", "CPC", "spot", "non-hormuz", "available"],
        "research_brief": (
            "Research non-Hormuz, non-Russian crude availability for Indian refiners:\n"
            "1. West Africa: Nigerian Bonny Light, Forcados, Escravos; Angolan Girassol, Dalia — spot availability, Dated Brent differentials, loading windows\n"
            "2. US Gulf: WTI Midland, Eagle Ford — freight to India ($4-6/bbl?), USGC tanker availability\n"
            "3. Latin America: Brazilian Tupi/Lula, Colombian Castilla, Mexican Maya — availability and compatibility with Indian refineries\n"
            "4. North Sea: Johan Sverdrup, Ekofisk — typically premium but now competitive?\n"
            "5. Caspian: CPC Blend from Novorossiysk — non-sanctioned? volume available?\n"
            "6. North Africa: Libyan Es Sider, Algerian Saharan Blend\n"
            "7. Middle East non-Hormuz: Saudi via Yanbu (Red Sea), Iraqi Kirkuk via Ceyhan (Turkey), ADNOC via Fujairah pipeline\n"
            "8. Domestic India: ONGC Bombay High, OIL Assam, Cairn Rajasthan — current production and allocation flexibility\n"
            "9. Overall global spare crude supply vs demand from India, Korea, Japan, Europe all competing\n"
            "Sources: Platts, Argus, Kpler vessel tracking, EIA International, OPEC Monthly Report"
        ),
    },
    {
        "theme_id": "C05",
        "title": "Indian Strategic Petroleum Reserve (SPR) — Inventory & Release Mechanisms",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["SPR", "strategic petroleum", "ISPRL", "vizag", "padur", "mangaluru", "strategic reserve", "emergency release"],
        "research_brief": (
            "Research India's Strategic Petroleum Reserve status:\n"
            "1. Current inventory at 3 SPR sites: Vizag (1.33 MMT), Mangaluru (1.5 MMT), Padur (2.5 MMT)\n"
            "2. Total SPR capacity vs current fill level (days of import cover)\n"
            "3. Release mechanism — who authorizes, what is the legal process, timeline from decision to delivery\n"
            "4. Has GoI signaled willingness to release? Any MoPNG/Cabinet statements?\n"
            "5. Crude grade stored in each facility — is it compatible with nearby refineries?\n"
            "6. Phase 2 SPR expansion status (Chandikhol, Padur expansion)\n"
            "7. IEA coordinated release — has India participated before, is one being discussed now?\n"
            "Sources: ISPRL, MoPNG, PIB press releases, IEA emergency response, Indian Express/ET Energy"
        ),
    },
    {
        "theme_id": "C06",
        "title": "MRPL Shutdown — Cause, Duration, Product Gap, Cascading Effects",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["MRPL", "mangalore", "shutdown", "product gap", "karnataka", "competitor shutdown"],
        "research_brief": (
            "Research the MRPL Mangalore refinery shutdown:\n"
            "1. What triggered the shutdown — crude inventory exhaustion, LC refusal, or board decision?\n"
            "2. MRPL capacity (300 kbpd) — what products and volumes were they producing?\n"
            "3. Which domestic markets depended on MRPL output (Karnataka, Goa, southern India)?\n"
            "4. Duration estimate — how long until restart? What are the restart conditions?\n"
            "5. Product gap by grade: diesel, petrol, ATF, LPG, naphtha\n"
            "6. Are any other Indian refineries at risk of similar shutdown? Which ones, how soon?\n"
            "7. Financial impact on MRPL — losses, debt covenants, government support\n"
            "Sources: MRPL filings, BSE/NSE announcements, MoPNG, Karnataka state government, news"
        ),
    },
    {
        "theme_id": "C07",
        "title": "War-Risk Insurance & Freight — Arabian Sea/Gulf of Oman",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["war risk", "insurance", "P&I", "freight", "tanker", "VLCC", "Arabian Sea", "shipping", "vessel"],
        "research_brief": (
            "Research war-risk insurance and freight market for Indian crude imports:\n"
            "1. Current war-risk insurance premium for Gulf/Arabian Sea transits (% of cargo value or $/bbl)\n"
            "2. Which P&I clubs and insurers are still providing cover vs which have excluded the zone?\n"
            "3. VLCC and Suezmax freight rates: Gulf-to-India vs West Africa-to-India vs USGC-to-India\n"
            "4. Available tanker tonnage for non-Gulf routes — is there a shortage?\n"
            "5. At what premium does war-risk insurance make Hormuz-adjacent routes uneconomic?\n"
            "6. Indian Navy escort or security arrangements — any announced?\n"
            "7. Comparison with Red Sea/Houthi crisis insurance response (2024)\n"
            "Sources: Lloyd's List, TradeWinds, maritime insurers, Clarksons, Baltic Exchange"
        ),
    },
    {
        "theme_id": "C08",
        "title": "Indian Refinery Inventory Levels & Days of Cover",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["inventory", "days of cover", "crude stock", "tank", "storage", "depletion", "minimum operational"],
        "research_brief": (
            "Research current crude and product inventory at Indian refineries:\n"
            "1. Industry-wide crude inventory in days of cover (PPAC monthly data, most recent)\n"
            "2. Refinery-by-refinery crude stock estimates where available (IOCL, BPCL, HPCL annual reports for baseline)\n"
            "3. India's total crude import dependence (85%+) and normal inventory policy (15-20 days)\n"
            "4. At current import disruption level, estimated depletion timeline by refinery segment\n"
            "5. Product inventory at retail/depot level — is there separate data from OMC reports?\n"
            "6. Crude storage capacity utilization at Jamnagar, Vadinar, Paradip, Mumbai, Kochi\n"
            "Sources: PPAC monthly, MoPNG, IOCL/BPCL/HPCL/RIL quarterly reports, CRISIL"
        ),
    },
    {
        "theme_id": "C09",
        "title": "GRM Economics at $156/bbl — Margin Analysis by Refinery Type",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["GRM", "gross refining margin", "under-recovery", "margin", "crack spread", "negative margin", "contribution margin"],
        "research_brief": (
            "Research refining margins for Indian refineries at $156/bbl crude:\n"
            "1. Singapore benchmark GRM (latest) — what does it imply for Indian refiners?\n"
            "2. Reported GRM for IOCL, BPCL, HPCL, RIL, Nayara (most recent quarter)\n"
            "3. Under-recovery per barrel at frozen retail prices (diesel, petrol) for PSU refiners\n"
            "4. Which product streams are positive margin vs negative at $156 basket?\n"
            "5. Historical GRM during past crude spikes (2022 Ukraine, 2008 crisis)\n"
            "6. Nelson Complexity Index by refinery — which can extract more value from same crude?\n"
            "7. At what crude price does the average Indian refinery hit zero GRM? Negative?\n"
            "Sources: PPAC, company quarterly results, CRISIL/ICRA reports, Platts"
        ),
    },
    {
        "theme_id": "C10",
        "title": "Government Policy — Fuel Pricing, Subsidies, ESMA, Export Controls",
        "scope": "COMMON",
        "depth": "TIER_1",
        "keywords": ["government", "MoPNG", "price freeze", "retail price", "subsidy", "oil bond", "ESMA", "export duty", "excise", "windfall", "rationing"],
        "research_brief": (
            "Research Indian government energy policy response to the crisis:\n"
            "1. Current retail fuel pricing status — are prices frozen? Since when? Any signal of revision?\n"
            "2. ESMA (Essential Services Maintenance Act) — is it invoked? What does it mandate for LPG?\n"
            "3. Subsidy/compensation mechanisms available: oil bonds, direct budget transfer, excise reduction\n"
            "4. Export duty on petroleum products — current status, any new restrictions proposed?\n"
            "5. Windfall tax status — is it still in effect, any changes?\n"
            "6. SPR release authorization — has MoPNG or Cabinet acted?\n"
            "7. Fuel rationing framework — does India have one? Has it ever been invoked?\n"
            "8. Government statements on crisis response (PM, Petroleum Minister, Finance Minister)\n"
            "Sources: MoPNG, PIB, Ministry of Finance, Parliament Q&A, ET/BS/Mint news"
        ),
    },
    {
        "theme_id": "C11",
        "title": "Crude Compatibility & Refinery Configuration Constraints",
        "scope": "COMMON",
        "depth": "TIER_2",
        "keywords": ["crude compatibility", "API gravity", "sulfur", "CDU", "configuration", "Nelson complexity", "diet", "process", "desalter", "metallurg"],
        "research_brief": (
            "Research Indian refinery configuration and crude diet flexibility:\n"
            "1. Nelson Complexity Index for major Indian refineries (RIL, Nayara, IOCL Paradip, BPCL Kochi, HPCL Mumbai, MRPL, CPCL)\n"
            "2. Design crude diet for each major refinery (API/sulfur range, typical grades)\n"
            "3. Which refineries can process light sweet (WAF, US) vs which need heavy sour (Gulf, Russian)?\n"
            "4. Maximum light crude percentage before reformer/desulfurizer constraints bind\n"
            "5. Condensate processing capability at each refinery\n"
            "6. Minimum throughput rates below which units face technical damage\n"
            "Sources: Company annual reports, CRISIL refinery profiles, Hydrocarbon Processing, Oil & Gas Journal"
        ),
    },
    {
        "theme_id": "C12",
        "title": "Indian Domestic Crude Production & Pipeline Infrastructure",
        "scope": "COMMON",
        "depth": "TIER_2",
        "keywords": ["domestic crude", "ONGC", "OIL", "Bombay High", "Rajasthan", "Assam", "pipeline", "Koyali", "Bina", "Numaligarh"],
        "research_brief": (
            "Research domestic Indian crude production and inland infrastructure:\n"
            "1. Total domestic crude production (ONGC + OIL + private) — current mbpd\n"
            "2. Major producing fields: Bombay High, Rajasthan (Cairn/Vedanta), KG Basin, Assam\n"
            "3. Can domestic production be increased in an emergency? By how much, how fast?\n"
            "4. Crude pipeline network: which refineries are pipeline-connected to which sources?\n"
            "5. IOCL Bina — pipeline-fed from Koyali, what crude grades can reach it?\n"
            "6. NRL Numaligarh — Assam crude allocation, pipeline from Paradip\n"
            "7. Product pipeline network and coastal shipping capacity\n"
            "Sources: DGH, PPAC, ONGC/OIL annual reports, MoPNG"
        ),
    },
    {
        "theme_id": "C13",
        "title": "Financial Stress — Working Capital, Covenants, Credit Ratings, FX",
        "scope": "COMMON",
        "depth": "TIER_2",
        "keywords": ["working capital", "credit", "covenant", "LC", "letter of credit", "bank", "SBI", "liquidity", "debt", "rating", "INR", "FX", "forex", "rupee"],
        "research_brief": (
            "Research financial stress indicators for Indian oil companies:\n"
            "1. IOCL, BPCL, HPCL, RIL, Nayara — latest reported debt/equity, working capital, credit lines\n"
            "2. LC (letter of credit) capacity — are banks tightening crude import financing?\n"
            "3. Credit rating actions — any downgrades or watchlist placements?\n"
            "4. INR/USD rate and trend — forex impact on crude import bill\n"
            "5. RBI/government support measures for oil company financing\n"
            "6. Historical precedent: how did oil companies manage working capital in 2022 spike?\n"
            "Sources: BSE/NSE filings, rating agency reports (CRISIL, ICRA, Moody's), RBI data"
        ),
    },
    # ---- PS1-SPECIFIC THEMES ----
    {
        "theme_id": "S1A",
        "title": "RIL Jamnagar & Nayara Vadinar — Capacity, Configuration, Export Capability",
        "scope": "PS1",
        "depth": "TIER_1",
        "keywords": ["RIL", "Reliance", "Jamnagar", "Nayara", "Vadinar", "SEZ", "DTA", "Sikka", "1.4 mbpd", "400 kbpd", "petrochemical"],
        "research_brief": (
            "Research RIL and Nayara refinery specifics:\n"
            "1. Jamnagar DTA capacity, configuration, Nelson complexity, product slate\n"
            "2. Jamnagar SEZ capacity, export orientation rules, product mix\n"
            "3. Nayara Vadinar capacity (400 kbpd), configuration, Rosneft ownership structure\n"
            "4. Rosneft's 49.13% stake in Nayara — sanctions implications post-April 3\n"
            "5. RIL petrochemical complex integration — naphtha/ethane cracker capacity, feedstock flexibility\n"
            "6. Sikka port and Vadinar port — VLCC handling, SBM capacity, product export jetties\n"
            "7. Recent RIL and Nayara GRM reported, export volumes, domestic supply share\n"
            "Sources: RIL annual report, Nayara annual report, BSE filings, Platts, CRISIL"
        ),
    },
    {
        "theme_id": "S1B",
        "title": "Product Export Opportunities & Competitor Displacement",
        "scope": "PS1",
        "depth": "TIER_1",
        "keywords": ["export", "crack spread", "Singapore", "product tanker", "ATF", "diesel export", "naphtha export", "competitor shut"],
        "research_brief": (
            "Research product export market opportunities from India:\n"
            "1. Current Singapore/Rotterdam crack spreads: diesel, jet fuel, naphtha, LSFO, gasoline\n"
            "2. Which regional refineries (Middle East, Singapore, South Korea) are curtailed due to Hormuz?\n"
            "3. Product tanker availability and rates from India to key export markets\n"
            "4. India's export duty/restrictions on petroleum products — current status\n"
            "5. Domestic product supply obligations — what must RIL/Nayara supply locally before exporting?\n"
            "6. SEZ export rules — can Jamnagar SEZ redirect to domestic during crisis?\n"
            "Sources: Platts, Argus, Vortexa, Kpler, RIL investor presentations"
        ),
    },
    # ---- PS2-SPECIFIC THEMES ----
    {
        "theme_id": "S2A",
        "title": "IOCL & HMEL Refinery Profiles — Paradip, Panipat, Gujarat, Bathinda",
        "scope": "PS2",
        "depth": "TIER_1",
        "keywords": ["IOCL", "Paradip", "Panipat", "Gujarat", "HMEL", "Bathinda", "PSU refin"],
        "research_brief": (
            "Research IOCL and HMEL refinery specifics:\n"
            "1. IOCL Paradip (300 kbpd) — configuration, crude slate, NCI, port infrastructure\n"
            "2. IOCL Panipat (300 kbpd) — configuration, pipeline-fed crude sources\n"
            "3. IOCL Gujarat (274 kbpd) — Koyali refinery configuration\n"
            "4. HMEL Bathinda (180 kbpd) — HPCL-Mittal JV, crude sourcing, pipeline connections\n"
            "5. Each refinery's recent GRM, throughput utilization, product slate\n"
            "6. ESMA LPG production obligations for each\n"
            "7. Inter-refinery product transfer mechanisms within IOCL system\n"
            "Sources: IOCL annual report, HMEL filings, PPAC, CRISIL"
        ),
    },
    {
        "theme_id": "S2B",
        "title": "PSU Under-Recovery Economics & Government Compensation Mechanisms",
        "scope": "PS2",
        "depth": "TIER_1",
        "keywords": ["under-recovery", "oil bond", "subsidy", "DBTL", "cash burn", "MoF", "compensation", "frozen price"],
        "research_brief": (
            "Research PSU refiner under-recovery and government support:\n"
            "1. Current under-recovery per litre on diesel, petrol, LPG at $156 crude\n"
            "2. Total daily cash burn for IOCL, BPCL, HPCL at current prices and throughput\n"
            "3. Oil bond mechanism — history, amounts, timeline from approval to cash\n"
            "4. DBTL (Direct Benefit Transfer for LPG) — reimbursement cycle time\n"
            "5. Excise duty reduction room — current central excise on diesel/petrol\n"
            "6. Historical government response: 2022 crude spike, 2018 crude spike\n"
            "7. PSU refiner dividend obligations and capex commitments at risk\n"
            "Sources: MoF budget documents, PPAC, IOCL/BPCL/HPCL quarterly filings, rating agency reports"
        ),
    },
    # ---- PS3-SPECIFIC THEMES ----
    {
        "theme_id": "S3A",
        "title": "Low-Complexity PSU Refineries — HPCL Mumbai, BPCL Mumbai/Kochi, CPCL, Bina, NRL",
        "scope": "PS3",
        "depth": "TIER_1",
        "keywords": ["HPCL Mumbai", "BPCL Mumbai", "BPCL Kochi", "CPCL", "Manali", "Bina", "NRL", "Numaligarh", "low complexity", "low NCI"],
        "research_brief": (
            "Research low-complexity PSU refinery specifics:\n"
            "1. Each refinery's nameplate capacity, NCI, crude diet limitations\n"
            "   - HPCL Mumbai (150 kbpd), BPCL Mumbai (120 kbpd), BPCL Kochi (310 kbpd)\n"
            "   - CPCL Manali (210 kbpd), IOCL Bina (156 kbpd), NRL Numaligarh (60 kbpd)\n"
            "2. Minimum safe operating throughput for each\n"
            "3. Regional supply importance — which states depend on each refinery\n"
            "4. Crude sourcing: pipeline-fed vs coastal — vulnerability to Hormuz\n"
            "5. MRPL's configuration for comparison (what made it shut first?)\n"
            "6. Recent financial performance — GRM, profitability, debt levels\n"
            "Sources: HPCL/BPCL/CPCL/NRL annual reports, PPAC, CRISIL"
        ),
    },
    {
        "theme_id": "S3B",
        "title": "Shutdown/Restart Economics & Regional Supply Contingency",
        "scope": "PS3",
        "depth": "TIER_1",
        "keywords": ["shutdown", "restart", "cold shutdown", "hot idle", "catalyst", "regional supply", "rationing", "stock-out"],
        "research_brief": (
            "Research refinery shutdown/restart costs and regional supply impact:\n"
            "1. Cost and timeline to restart an Indian refinery from cold shutdown vs hot idle\n"
            "2. Technical risks of shutdown: catalyst deactivation, corrosion, furnace integrity\n"
            "3. Historical Indian refinery shutdowns — any precedents for cost/timeline?\n"
            "4. Regional product supply contingency — if MRPL + one more shuts, which states face shortfall?\n"
            "5. Product import feasibility — can India import diesel/petrol/LPG at scale? From where?\n"
            "6. Demand-side rationing mechanisms — does India have a framework? Historical use?\n"
            "7. Northeast India supply vulnerability if NRL Numaligarh shuts\n"
            "Sources: Hydrocarbon Processing, refinery engineering literature, MoPNG contingency plans, news"
        ),
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_client() -> anthropic.Anthropic:
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        for p in [ROOT.parent / ".env", ROOT.parent.parent / "oil-dashboard" / ".env"]:
            if p.exists():
                for line in p.read_text().splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            if api_key:
                break
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    raise RuntimeError("No text content")


def load_scored_questions() -> list[dict]:
    path = RESEARCH_DIR / "1a_scored_questions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def print_divider(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}\n")


# ---------------------------------------------------------------------------
# Map questions to themes by keyword matching
# ---------------------------------------------------------------------------


def map_questions_to_themes(scored_qs: list[dict]) -> dict[str, list[dict]]:
    """Map each T1/T2 question to the best-matching theme."""
    research_qs = [q for q in scored_qs if q["tier"] in (1, 2)]
    theme_map: dict[str, list[dict]] = {t["theme_id"]: [] for t in RESEARCH_THEMES}
    unmatched = []

    for q in research_qs:
        qtext = q["question"].lower()
        best_theme = None
        best_score = 0

        for theme in RESEARCH_THEMES:
            # Check scope match
            if theme["scope"] not in ("COMMON", q["ps"]):
                continue

            score = sum(1 for kw in theme["keywords"] if kw.lower() in qtext)
            if score > best_score:
                best_score = score
                best_theme = theme["theme_id"]

        if best_theme and best_score > 0:
            theme_map[best_theme].append(q)
        else:
            unmatched.append(q)

    return theme_map, unmatched


# ---------------------------------------------------------------------------
# Execute research for one theme
# ---------------------------------------------------------------------------

RESEARCH_SYSTEM = """\
You are a senior energy analyst conducting rapid desk research for a crisis \
briefing on the Iran-Israel Hormuz crisis and its impact on Indian refineries. \
The Indian basket is at $156/bbl. MRPL Mangalore has shut down. The Russia \
sanctions waiver expires April 3, 2026.

Write factual, sourced, data-rich research findings. For every number, cite the \
source. Flag confidence level (HIGH: confirmed data, MEDIUM: analyst estimate, \
LOW: extrapolation). Flag data recency (how old is this number). \
Use bullet points. No fluff."""

RESEARCH_USER = """\
RESEARCH THEME: {title}
DEPTH: {depth}

BRIEF:
{research_brief}

SPECIFIC QUESTIONS THIS RESEARCH MUST HELP ANSWER:
{questions_formatted}

Write a comprehensive research report for this theme. For each data point in the \
brief, provide:
- The finding (number, fact, or assessment)
- Source (publication, date)
- Confidence: HIGH / MEDIUM / LOW
- Recency: when was this data published

If a data point cannot be found, say "NOT FOUND" and suggest where it might exist.

Keep the report under 2000 words. Focus on NUMBERS, not narrative."""


def execute_research_theme(
    client: anthropic.Anthropic, theme: dict, questions: list[dict]
) -> str:
    """Execute research for a single theme."""
    questions_fmt = "\n".join(
        f"  [{q['ps']}/{q['question_id']}] {q['question'][:150]}"
        for q in questions[:15]  # Cap at 15 to fit context
    )

    prompt = RESEARCH_USER.format(
        title=theme["title"],
        depth=theme["depth"],
        research_brief=theme["research_brief"],
        questions_formatted=questions_fmt,
    )

    return call_claude(client, RESEARCH_SYSTEM, prompt)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    client = get_client()
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

    # Load scored questions
    scored_qs = load_scored_questions()
    t1_count = sum(1 for q in scored_qs if q["tier"] == 1)
    t2_count = sum(1 for q in scored_qs if q["tier"] == 2)
    t3_count = sum(1 for q in scored_qs if q["tier"] == 3)

    print_divider("STEP 1: RESEARCH PIPELINE")
    print(f"  Questions: {len(scored_qs)} total ({t1_count} T1, {t2_count} T2, {t3_count} T3)")
    print(f"  Themes defined: {len(RESEARCH_THEMES)}")

    # Map questions to themes
    theme_map, unmatched = map_questions_to_themes(scored_qs)

    print(f"\n  Question -> Theme mapping:")
    total_mapped = 0
    for theme in RESEARCH_THEMES:
        tid = theme["theme_id"]
        qs = theme_map[tid]
        total_mapped += len(qs)
        print(f"    [{tid}] {theme['title'][:55]:55s} | {len(qs):3d} questions | {theme['depth']}")

    print(f"\n  Total mapped: {total_mapped}")
    print(f"  Unmatched:    {len(unmatched)}")
    if unmatched:
        print(f"  Unmatched examples:")
        for q in unmatched[:5]:
            print(f"    [{q['ps']}/{q['question_id']}] {q['question'][:80]}")

    # Save mapping
    mapping_data = {
        tid: [{"ps": q["ps"], "qid": q["question_id"], "tier": q["tier"]} for q in qs]
        for tid, qs in theme_map.items()
    }
    mapping_data["_unmatched"] = [
        {"ps": q["ps"], "qid": q["question_id"], "tier": q["tier"]} for q in unmatched
    ]
    (RESEARCH_DIR / "1b_question_theme_map.json").write_text(
        json.dumps(mapping_data, indent=2), encoding="utf-8"
    )

    # Execute research in parallel
    print_divider("EXECUTING RESEARCH (parallel)")

    # Filter to themes that have questions
    active_themes = [(t, theme_map[t["theme_id"]]) for t in RESEARCH_THEMES if theme_map[t["theme_id"]]]
    print(f"  Active themes: {len(active_themes)} (skipping {len(RESEARCH_THEMES) - len(active_themes)} with no questions)")

    results = {}
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for theme, qs in active_themes:
            future = executor.submit(execute_research_theme, client, theme, qs)
            futures[future] = theme

        for future in as_completed(futures):
            theme = futures[future]
            tid = theme["theme_id"]
            try:
                research_text = future.result()
                results[tid] = research_text

                # Save individual brief
                brief_path = BRIEFS_DIR / f"{tid}_{theme['title'][:40].replace(' ', '_').replace('/', '_')}.md"
                brief_path.write_text(
                    f"# {theme['title']}\n\n"
                    f"**Scope:** {theme['scope']} | **Depth:** {theme['depth']}\n\n"
                    f"---\n\n{research_text}\n",
                    encoding="utf-8",
                )
                elapsed = time.time() - t_start
                print(f"  [{elapsed:5.0f}s] {tid} done - {theme['title'][:50]}")
            except Exception as e:
                print(f"  ERROR on {tid}: {e}")
                results[tid] = f"RESEARCH FAILED: {e}"

    t_end = time.time()

    # Compile all research into one document
    print_divider("COMPILING RESEARCH")

    compiled_parts = []
    for theme in RESEARCH_THEMES:
        tid = theme["theme_id"]
        if tid in results:
            compiled_parts.append(
                f"# {tid}: {theme['title']}\n"
                f"**Scope:** {theme['scope']} | **Depth:** {theme['depth']} | "
                f"**Questions covered:** {len(theme_map.get(tid, []))}\n\n"
                f"{results[tid]}\n"
            )

    compiled = "\n\n---\n\n".join(compiled_parts)
    compiled_path = RESEARCH_DIR / "1c_compiled_research.md"
    compiled_path.write_text(compiled, encoding="utf-8")

    # Summary
    print_divider("RESEARCH COMPLETE")
    print(f"  Themes researched: {len(results)}")
    print(f"  Time: {t_end - t_start:.0f}s")
    print(f"  Compiled: {compiled_path} ({len(compiled) // 1024}KB)")
    print(f"  Individual briefs: {BRIEFS_DIR}/")

    # Coverage stats
    covered_qs = set()
    for tid, qs in theme_map.items():
        if tid in results:
            for q in qs:
                covered_qs.add(f"{q['ps']}/{q['question_id']}")

    print(f"\n  T1+T2 questions covered by research: {len(covered_qs)} / {t1_count + t2_count}")
    print(f"  T3 questions (extrapolate, no research): {t3_count}")
    print(f"  Unmatched questions: {len(unmatched)}")


if __name__ == "__main__":
    main()

# Anvil v0.2: Now You Can Start With the Answer

Most strategic analysis tools assume you don't know the answer. They walk you through research, decomposition, synthesis — and eventually, after hours of work, arrive at a recommendation.

But senior leaders rarely start from zero. They walk in with a thesis. "I think we should do X." What they need isn't exploration — it's stress-testing. Does the data support this? What would kill it? What am I missing?

Anvil v0.2 adds a second mode for exactly this.

---

## Two Ways to Solve a Problem

**Issue-Driven** — you don't have an answer yet. Anvil decomposes the problem into research buckets, scans 120+ sources, builds a working document, synthesizes patterns, generates hypotheses from the data, and stress-tests them. The answer emerges from the research. ~20-45 minutes, ~$2-3.

**Hypothesis-Driven** — you already have a Day 1 answer. Anvil challenges it against real-time landscape data, decomposes it into necessary conditions ("what must be true for this to hold?"), runs deep targeted search on every condition, and either confirms, revises, or kills your thesis. ~10-15 minutes, ~$1-2.

Same engine. Same rigor. Different starting point.

---

## How Hypothesis-Driven Mode Works

You give Anvil a problem statement and your Day 1 answer:

```
PS: What must NVIDIA do in the next 12 months to defend its AI infrastructure 
    monopoly as AMD, custom silicon, and open-source inference erode its moat?

Day 1: NVIDIA should pivot from selling chips to selling full-stack AI factories 
       — bundling hardware, networking, software, and managed inference — locking 
       customers into ecosystem contracts before hyperscaler custom silicon reaches 
       production scale in Q3 2027.
```

### Step 1: The Challenge

Anvil doesn't accept your hypothesis. It challenges it.

It runs a two-tier landscape scan — 120+ search snippets, 12+ full articles — and uses what it finds to poke holes in your thesis:

> **Challenges to your hypothesis:**
> - NVIDIA's DGX Cloud already bundles hardware + software + managed inference. If the pivot is "sell AI factories," the question is why the existing bundle isn't locking customers in. Azure and GCP are offering NVIDIA hardware with their own orchestration layers — the lock-in may be at the cloud layer, not the chip layer.
> - Hyperscaler custom silicon (Google TPU v6, Amazon Trainium2) is already in production for internal workloads. Q3 2027 may be the date it reaches *external customers*, but the competitive pressure starts now.
> - Open-source inference (vLLM, TensorRT-LLM alternatives) is reducing the software moat faster than the hardware moat. Bundling software may not be defensible.
>
> **For this hypothesis to hold, these must be true:**
> - Enterprise buyers prefer single-vendor AI stacks over best-of-breed
> - NVIDIA's software layer (CUDA, NIM, NeMo) creates switching costs that survive hardware commoditization
> - Hyperscaler custom silicon doesn't reach price-performance parity for fine-tuning workloads before Q3 2027

Your hypothesis stays unchanged. You decide what to revise based on the challenges.

### Step 2: Decomposition

Your hypothesis gets decomposed into a tree of necessary conditions — each one testable:

```
GOVERNING: NVIDIA should pivot to full-stack AI factories with ecosystem lock-in

├─ H1: Enterprise buyers will pay premium for single-vendor AI stacks
│  ├─ H1.1: Current multi-vendor friction costs exceed 15% of AI infrastructure spend
│  ├─ H1.2: NVIDIA NIM adoption exceeds 500 enterprise deployments by Q4 2026
│  └─ H1.3: At least 3 Fortune 100 companies have signed multi-year DGX Cloud contracts
│
├─ H2: CUDA/NIM create durable switching costs
│  ├─ H2.1: Migration cost from CUDA to ROCm/Triton exceeds 6 months of engineering time
│  └─ H2.2: No open-source inference framework matches TensorRT-LLM performance within 20%
│
├─ H3: Hyperscaler custom silicon doesn't reach parity before Q3 2027
│  ├─ H3.1: Google TPU v6 price-performance for fine-tuning is >30% worse than H100
│  └─ H3.2: Amazon Trainium2 external availability is Q2 2027 or later
```

### Step 3: Deep Test

Every leaf gets hit with targeted web search — not just the uncertain ones, every single one. 2-3 queries per leaf, 8 results per query, full article fetches. Sonnet evaluates the evidence and assigns verdicts:

- **GREEN** — evidence supports this condition
- **AMBER** — mixed or thin evidence
- **RED** — evidence contradicts this condition

Red leaves kill their parent branch. Kill propagation ripples up. The governing hypothesis gets revised from survivors — always bottom-up, never invented.

### Step 4: The Brief

A 3-5 page strategic document. Headlines are the story. Governing hypothesis front and center. Decisions required with deadlines and costs. Killed hypotheses shown for rigor. Data gaps identified for follow-up.

---

## Three Examples

We ran three hypothesis-driven analyses to demonstrate the mode:

### NVIDIA: Defending the AI Infrastructure Monopoly

**Problem:** What must NVIDIA do in the next 12 months as AMD, custom silicon, and open-source inference erode its moat?

**Day 1 Hypothesis:** Pivot from selling chips to selling full-stack AI factories with ecosystem lock-in contracts before hyperscaler custom silicon reaches production scale.

**What Anvil Found:** The "lock customers into ecosystem contracts" thesis was killed — hyperscalers already have custom silicon in production (Google TPU v6, Amazon Trainium2) and NVIDIA's software platform couldn't generate defensible lock-in independent of GPU hardware advantage. 4 of 8 branches killed. The governing hypothesis revised to: "Ship Vera Rubin to hyperscalers by Q4 2025, price it below custom ASIC TCO at scale, and accept software margin loss to hold training dominance." The answer shifted from ecosystem lock-in to hardware execution speed.

### European Automakers: Surviving the Chinese EV Price War

**Problem:** What actions must European automakers take in the next 18 months — restructure manufacturing, partner with Chinese battery suppliers, or retreat to luxury?

**Day 1 Hypothesis:** Abandon mass-market EVs entirely, cede the sub-35K segment to BYD and SAIC, concentrate all capital on luxury EVs and autonomous driving.

**What Anvil Found:** The "retreat to luxury" thesis was partially killed — the luxury segment can't absorb redirected capital (Mercedes EQS sales dropped 50% in some markets), and ceding sub-35K triggers a volume death spiral that destroys supplier economics. 6 of 10 branches killed. The revised governing hypothesis became a three-tier strategy: exit sub-35K, partner with Chinese tech firms on software stacks (not just battery supply), and defend 35K-55K mid-market with platform-shared EVs. The answer shifted from full retreat to selective retreat with alliance.

### Workday: Defending HCM Dominance Against AI-Native Competitors

**Problem:** What must Workday do in the next 18 months as Rippling commoditizes core HR/payroll and buyers demand AI-first workflows?

**Day 1 Hypothesis:** Acquire 2-3 AI-native workflow companies, rebuild core platform around agent-based automation by Q3 2027, convert contracts from per-seat to per-outcome pricing.

**What Anvil Found:** The most aggressive stress-test of the three. 13 of 14 branches killed. The acquisition thesis failed (AI-native targets are priced at 40-60x revenue — unaffordable). The platform rebuild timeline was unrealistic (18 months to rebuild a 20-year-old platform). The per-outcome pricing model had no actuarial basis. Only one branch survived: Workday's unified HCM-finance data layer is a genuine moat. The governing hypothesis collapsed to: "Instrument the data layer with measurable customer-specific metrics and sell the data advantage, not the workflow." Sometimes the most valuable output is discovering your thesis is wrong.

---

## What Else is New in v0.2

**Dashboard overhaul.** Two separate pipeline visualizations — issue-driven shows the full 8-step U-shape, hypothesis-driven shows the compressed 7-step line. Progressive reveal: only PS visible during step 0, full panel after mode selection. LIVE/STALE badge. Hypothesis-driven mode shows Day 1 answer and locked governing hypothesis.

**Document structure.** Governing hypothesis is now an explicit labeled section — bold, front and center. Decisions required moved up before the deep dives (answer + beliefs + asks first, evidence second). Process scaffolding stripped: no more `(per synthesis findings, financial_and_structural:)` leaking into the final brief.

**Charts that don't crash.** Appendix generation split into two steps — claim identification (Sonnet) then chart data per slide in parallel (Haiku). No more JSON truncation on large outputs.

**Resume detection.** Pipeline now detects hypothesis-driven mode from state.json on resume, so `--resume` works correctly without re-passing `--hypothesis`.

**User data injection.** Guided mode asks "Do you have internal data?" before the landscape scan. Files or pasted data flow into landscape scan, hypothesis challenge, deep testing, and the final brief as HIGH confidence sources.

---

## What's Next

- **LinkedIn carousel export** — `anvil carousel --run <name>` generates 1080x1080 slides from any completed run. Two LLM review passes (strategy partner + content manager) before rendering.
- **pip install** — `pip install anvil-engine` from GitHub
- **Website** — single page, amber aesthetic, waitlist

---

*Anvil is a strategic problem-solving engine. It takes a question and an audience, runs live web research, builds a hypothesis tree, stress-tests it, and produces a sourced strategic brief with proof charts. Built by Parth Reddy.*

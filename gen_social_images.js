const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const delay = ms => new Promise(r => setTimeout(r, ms));

  // 1. Hero card — LinkedIn/Substack cover (1200x630)
  const p1 = await browser.newPage();
  await p1.setViewport({width: 1200, height: 630});
  await p1.setContent(`
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=Inter:wght@400;700;800;900&display=swap');
      body { margin:0; background:#0C0C0C; display:flex; align-items:center; justify-content:center; height:630px; font-family:'IBM Plex Mono',monospace; }
      .card { text-align:center; }
      .logo { color:#F5A623; font-size:13px; line-height:1.35; white-space:pre; text-shadow:0 0 12px rgba(245,166,35,0.35); margin-bottom:28px; }
      .title { font-family:'Inter',sans-serif; font-size:38px; font-weight:900; color:#EFEFEF; max-width:750px; line-height:1.15; letter-spacing:-1px; margin:0 auto 14px; }
      .sub { font-size:14px; color:#9B6A14; letter-spacing:1.5px; margin-bottom:24px; }
      .tag { display:flex; gap:10px; justify-content:center; }
      .tag span { font-size:10px; padding:5px 12px; border:1px solid #2A2A2A; color:#777; letter-spacing:1px; }
      .tag span.hl { border-color:#F5A623; color:#F5A623; }
    </style>
    <div class="card">
      <pre class="logo">  ▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄
  █   A N V I L                █
  ▀▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▀
       ╲▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄╱</pre>
      <div class="title">Strategic Problem-Solving Engine</div>
      <div class="sub">PROBLEM → MECE → RESEARCH → SYNTHESIS → HYPOTHESES → BRIEF</div>
      <div class="tag">
        <span class="hl">~45 LLM CALLS</span>
        <span class="hl">50+ ARTICLES</span>
        <span class="hl">20 MIN</span>
        <span>$2-4 PER RUN</span>
        <span>OPEN SOURCE</span>
      </div>
    </div>
  `);
  await delay(1500);
  await p1.screenshot({path: 'screenshots/social_hero.png'});
  console.log('1/4 hero');

  // 2. Pipeline flow card
  const p2 = await browser.newPage();
  await p2.setViewport({width: 1200, height: 630});
  await p2.setContent(`
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=Inter:wght@400;700;800&display=swap');
      body { margin:0; background:#0C0C0C; display:flex; flex-direction:column; align-items:center; justify-content:center; height:630px; font-family:'IBM Plex Mono',monospace; color:#EFEFEF; }
      .badge { font-size:10px; letter-spacing:3px; color:#F5A623; border:1px solid #9B6A14; padding:5px 14px; margin-bottom:24px; }
      .flow { font-size:14px; line-height:2; white-space:pre; color:#555; margin-bottom:28px; }
      .done { color:#22C55E; font-weight:700; }
      .active { color:#FFD080; font-weight:700; text-shadow:0 0 8px rgba(245,166,35,0.5); }
      .insight { max-width:680px; text-align:center; }
      .q { font-family:'Inter'; font-size:20px; font-weight:800; color:#FFD080; margin-bottom:10px; }
      .a { font-family:'Inter'; font-size:13px; color:#888; line-height:1.6; }
      .ft { position:absolute; bottom:20px; font-size:9px; color:#444; letter-spacing:2px; }
    </style>
    <div class="badge">ANVIL PIPELINE</div>
    <div class="flow"><span class="done">✓ PROBLEM</span> ─── <span class="done">✓ MECE</span> ─── <span class="done">✓ RESEARCH</span> ─── <span class="done">✓ W.DOC</span> ───┐
                                                         │
<span class="active">▸ CHARTS</span>  ─── <span class="done">✓ FINAL</span>  ─── <span class="done">✓ HYPOTHESES</span> ─── <span class="done">✓ SYNTH</span>  ──┘</div>
    <div class="insight">
      <div class="q">"The Hormuz Endgame"</div>
      <div class="a">10 buckets · 76 questions · 135 snippets · 58 articles · 50 findings · 8 patterns · 8 hypotheses stress-tested · 6 proof charts</div>
    </div>
    <div class="ft">OPEN SOURCE · RUNS ON CLAUDE · github.com/parthreddyprojects/anvil</div>
  `);
  await delay(1500);
  await p2.screenshot({path: 'screenshots/social_pipeline.png'});
  console.log('2/4 pipeline');

  // 3. Hypothesis graveyard card
  const p3 = await browser.newPage();
  await p3.setViewport({width: 1200, height: 630});
  await p3.setContent(`
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;700;800&display=swap');
      body { margin:0; background:#0C0C0C; display:flex; flex-direction:column; align-items:center; justify-content:center; height:630px; font-family:'Inter',sans-serif; color:#EFEFEF; padding:40px 60px; }
      .badge { font-family:'IBM Plex Mono'; font-size:10px; letter-spacing:3px; color:#EF4444; border:1px solid #7F1D1D; padding:5px 14px; margin-bottom:24px; }
      .title { font-size:24px; font-weight:800; margin-bottom:28px; text-align:center; line-height:1.3; }
      .hyp { background:#111; border:1px solid #1F1F1F; border-left:3px solid #EF4444; padding:18px 22px; margin-bottom:14px; max-width:780px; width:100%; }
      .label { font-family:'IBM Plex Mono'; font-size:10px; color:#EF4444; letter-spacing:2px; margin-bottom:6px; }
      .text { font-size:14px; color:#CCC; line-height:1.6; }
      .note { font-size:12px; color:#666; margin-top:20px; max-width:650px; text-align:center; line-height:1.6; }
      .note strong { color:#F5A623; }
    </style>
    <div class="badge">HYPOTHESIS GRAVEYARD</div>
    <div class="title">Anvil Killed These. A Chatbot Would Have Presented Them as Options.</div>
    <div class="hyp">
      <div class="label">REJECTED</div>
      <div class="text">Allied coalition will hold beyond 30 days. Historical precedent from 2003 and 2011 shows allied patience erodes within 2-4 weeks when domestic energy costs spike.</div>
    </div>
    <div class="hyp">
      <div class="label">REJECTED</div>
      <div class="text">Proprietary AI platforms constitute a durable competitive moat. AI efficiency gains transfer to clients within 1-2 contract cycles — the marketing of AI speed is the mechanism that accelerates this transfer.</div>
    </div>
    <div class="note">The most valuable output is often what got <strong>rejected</strong>. Each kill reason teaches you more than a confirmed hypothesis.</div>
  `);
  await delay(1500);
  await p3.screenshot({path: 'screenshots/social_graveyard.png'});
  console.log('3/4 graveyard');

  // 4. Guided mode card
  const p4 = await browser.newPage();
  await p4.setViewport({width: 1200, height: 630});
  await p4.setContent(`
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;700;800&display=swap');
      body { margin:0; background:#0C0C0C; display:flex; flex-direction:column; align-items:center; justify-content:center; height:630px; font-family:'Inter',sans-serif; color:#EFEFEF; padding:40px 60px; }
      .badge { font-family:'IBM Plex Mono'; font-size:10px; letter-spacing:3px; color:#06B6D4; border:1px solid #164E63; padding:5px 14px; margin-bottom:24px; }
      .title { font-size:26px; font-weight:800; margin-bottom:32px; text-align:center; line-height:1.3; max-width:680px; }
      .title span { color:#F5A623; }
      .steps { display:grid; grid-template-columns:1fr 1fr; gap:10px; max-width:780px; width:100%; }
      .step { background:#111; border:1px solid #1F1F1F; padding:14px 18px; border-left:3px solid #F5A623; }
      .num { font-family:'IBM Plex Mono'; font-size:9px; color:#9B6A14; letter-spacing:2px; margin-bottom:4px; }
      .act { font-size:13px; color:#FFD080; font-weight:700; margin-bottom:3px; }
      .you { font-size:11px; color:#888; line-height:1.4; }
      .you strong { color:#06B6D4; }
      .ft { position:absolute; bottom:20px; font-family:'IBM Plex Mono'; font-size:9px; color:#444; letter-spacing:2px; }
    </style>
    <div class="badge">GUIDED MODE</div>
    <div class="title">Claude Runs the Method. <span>You Bring the Judgment.</span></div>
    <div class="steps">
      <div class="step"><div class="num">STEP 0</div><div class="act">Problem Statement</div><div class="you"><strong>You:</strong> iterate until framing is sharp</div></div>
      <div class="step"><div class="num">STEP 1</div><div class="act">MECE Decomposition</div><div class="you"><strong>You:</strong> add missing buckets, flag overlap</div></div>
      <div class="step"><div class="num">STEP 2</div><div class="act">Deep Research</div><div class="you"><strong>You:</strong> inject proprietary data, internal reports</div></div>
      <div class="step"><div class="num">STEP 3</div><div class="act">Working Document</div><div class="you"><strong>You:</strong> correct numbers, add context</div></div>
      <div class="step"><div class="num">STEP 4</div><div class="act">Synthesis</div><div class="you"><strong>You:</strong> spot connections Claude missed</div></div>
      <div class="step"><div class="num">STEP 5</div><div class="act">Hypotheses</div><div class="you"><strong>You:</strong> add your own, provide kill evidence</div></div>
      <div class="step"><div class="num">STEP 6</div><div class="act">Final Brief</div><div class="you"><strong>You:</strong> sharpen with specific feedback</div></div>
      <div class="step"><div class="num">STEP 7</div><div class="act">Proof Charts</div><div class="you"><strong>You:</strong> review, done</div></div>
    </div>
    <div class="ft">ANVIL · OPEN SOURCE · /anvil IN CLAUDE CODE</div>
  `);
  await delay(1500);
  await p4.screenshot({path: 'screenshots/social_guided.png'});
  console.log('4/4 guided');

  await browser.close();
  console.log('Done — 4 social images in screenshots/');
})();

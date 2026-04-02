const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.setViewport({width: 1200, height: 630});
  await page.setContent(`
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
      <div class="title">Strategic Problem-Solving Co-Pilot</div>
      <div class="sub">PROBLEM → MECE → RESEARCH → SYNTHESIS → HYPOTHESES → BRIEF</div>
      <div class="tag">
        <span class="hl">GUIDED</span>
        <span class="hl">AUTOPILOT</span>
        <span class="hl">20 MIN</span>
        <span>$2-3 PER RUN</span>
        <span>OPEN SOURCE</span>
      </div>
    </div>
  `);
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({path: 'screenshots/social_hero.png'});
  console.log('Done');
  await browser.close();
})();

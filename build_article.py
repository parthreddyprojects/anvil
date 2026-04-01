"""Convert substack_article.md to substack_article.html with Substack styling."""
import re
from pathlib import Path

md = Path("substack_article.md").read_text(encoding="utf-8")

# Image mapping
IMG_MAP = {
    "final brief": ("report.png", "The final strategic brief — every claim sourced, every assumption surfaced."),
    "Claude Code": ("claude_anvil_launch.jpg", "Anvil running inside Claude Code. Type /anvil and the pipeline begins."),
    "inside Claude": ("claude_anvil_launch.jpg", "Anvil running inside Claude Code."),
    "issue tree": ("tree.png", "The MECE issue tree — 10 buckets, 76 sub-questions."),
    "MECE": ("tree.png", "The MECE issue tree — investigative, not prescriptive."),
    "hypothesis": ("claude_hypotheses.jpg", "8 hypotheses tested. Each stress-tested against 6 failure modes."),
    "stress test": ("claude_hypotheses.jpg", "Hypothesis stress test — confirmed, uncertain, killed."),
    "appendix": ("appendix.png", "Appendix: one claim, one chart, one conclusion."),
    "proof chart": ("appendix.png", "Proof chart — sources cited at the bottom."),
    "complete": ("claude_complete.jpg", "Pipeline complete. Claude narrates findings, reads headlines, opens output."),
    "5-tab": ("output_tabs.png", "The 5-tab output: Report, Appendix, Issue Tree, Synthesis, Debrief."),
    "dashboard": ("dashboard.png", "Live dashboard — tracks every step, every KPI, every dollar."),
}

def find_image(desc):
    desc_l = desc.lower()
    for key, (filename, caption) in IMG_MAP.items():
        if key.lower() in desc_l:
            return filename, caption
    return "output_tabs.png", desc

# Process markdown to HTML
body = md

# Code blocks
def replace_code(m):
    code = m.group(1).strip()
    if "╔" in code or "║" in code:
        return f'<div class="logo-block"><pre>{code}</pre></div>'
    return f'<pre><code>{code}</code></pre>'

body = re.sub(r'```\w*\n(.*?)```', replace_code, body, flags=re.DOTALL)

# Image placeholders
def replace_img(m):
    desc = m.group(1)
    fname, caption = find_image(desc)
    return f'<div class="img-block"><img src="screenshots/{fname}" alt="{desc}"><div class="img-caption">{caption}</div></div>'

body = re.sub(r'\*\[Image: (.*?)\]\*', replace_img, body)

# Headers
body = re.sub(r'^### (.+)$', r'<h3>\1</h3>', body, flags=re.MULTILINE)
body = re.sub(r'^## (.+)$', r'<h2>\1</h2>', body, flags=re.MULTILINE)
body = re.sub(r'^# (.+)$', r'<h1>\1</h1>', body, flags=re.MULTILINE)

# HR
body = re.sub(r'^---$', '<hr>', body, flags=re.MULTILINE)

# Blockquotes
lines = body.split('\n')
out = []
in_q = False
for line in lines:
    if line.startswith('> '):
        if not in_q:
            out.append('<blockquote>')
            in_q = True
        c = line[2:]
        c = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c)
        c = re.sub(r'\*(.+?)\*', r'<em>\1</em>', c)
        out.append(f'<p>{c}</p>')
    else:
        if in_q:
            out.append('</blockquote>')
            in_q = False
        out.append(line)
if in_q:
    out.append('</blockquote>')
body = '\n'.join(out)

# Bold/italic
body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', body)
body = re.sub(r'\*(.+?)\*', r'<em>\1</em>', body)

# Inline code
body = re.sub(r'`([^`]+?)`', r'<code>\1</code>', body)

# Unordered lists
body = re.sub(r'^- (.+)$', r'<li>\1</li>', body, flags=re.MULTILINE)
body = re.sub(r'((?:<li>.*</li>\n?)+)', lambda m: '<ul>\n' + m.group(0) + '</ul>\n', body)

# Paragraphs
lines = body.split('\n')
result = []
for line in lines:
    s = line.strip()
    if s and not s.startswith('<') and not s.startswith('```'):
        result.append(f'<p>{s}</p>')
    else:
        result.append(line)
body = '\n'.join(result)
body = re.sub(r'<p>\s*</p>', '', body)

# Build HTML
STYLE = """<style>
  @import url('https://fonts.googleapis.com/css2?family=Charter:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;600;700;800&display=swap');
  :root { --bg:#fff; --text:#1a1a1a; --text-sec:#555; --text-muted:#888; --accent:#F5A623; --border:#e5e7eb; --code-bg:#0C0C0C; --quote-bg:#faf9f7; --link:#c97800; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Charter',Georgia,serif; background:var(--bg); color:var(--text); line-height:1.85; font-size:18px; -webkit-font-smoothing:antialiased; }
  .container { max-width:680px; margin:0 auto; padding:60px 24px 100px; }
  .logo-block { background:var(--code-bg); border-radius:8px; padding:28px 32px 24px; margin-bottom:48px; overflow-x:auto; }
  .logo-block pre { font-family:'IBM Plex Mono',monospace; font-size:13px; line-height:1.35; color:var(--accent); text-shadow:0 0 10px rgba(245,166,35,0.3); margin:0; }
  h1 { font-family:'Inter',sans-serif; font-size:34px; font-weight:800; line-height:1.2; letter-spacing:-0.5px; margin-bottom:16px; }
  .subtitle { font-size:19px; color:var(--text-sec); margin-bottom:40px; line-height:1.6; }
  p { margin:0 0 20px; }
  p strong { color:var(--text); }
  h2 { font-family:'Inter',sans-serif; font-size:24px; font-weight:800; margin:56px 0 20px; letter-spacing:-0.3px; }
  h3 { font-family:'Inter',sans-serif; font-size:18px; font-weight:700; margin:36px 0 12px; }
  hr { border:none; border-top:1px solid var(--border); margin:44px 0; }
  blockquote { background:var(--quote-bg); border-left:3px solid var(--accent); padding:20px 24px; margin:24px 0; font-style:italic; color:var(--text-sec); border-radius:0 4px 4px 0; }
  blockquote p { margin:0 0 8px; } blockquote p:last-child { margin:0; }
  pre { background:var(--code-bg); color:#e0e0e0; padding:20px 24px; border-radius:6px; font-family:'IBM Plex Mono',monospace; font-size:14px; line-height:1.5; overflow-x:auto; margin:24px 0; }
  code { font-family:'IBM Plex Mono',monospace; font-size:0.88em; background:#f3f4f6; padding:2px 6px; border-radius:3px; color:#c97800; }
  pre code { background:none; padding:0; color:inherit; }
  ul,ol { margin:16px 0 20px; padding-left:28px; } li { margin-bottom:8px; }
  .img-block { margin:32px 0; border-radius:8px; overflow:hidden; border:1px solid var(--border); box-shadow:0 2px 12px rgba(0,0,0,0.06); }
  .img-block img { width:100%; display:block; }
  .img-caption { font-family:'Inter',sans-serif; font-size:13px; color:var(--text-muted); text-align:center; padding:10px 16px; background:#fafafa; border-top:1px solid var(--border); }
  .byline { font-family:'Inter',sans-serif; font-size:14px; color:var(--text-muted); margin-top:48px; padding-top:24px; border-top:1px solid var(--border); }
  .byline a { color:var(--link); text-decoration:none; }
  @media(max-width:640px) { h1{font-size:26px;} body{font-size:17px;} .container{padding:40px 18px 80px;} }
</style>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anvil — Strategic Problem Engine</title>
{STYLE}
</head>
<body>
<div class="container">
{body}
<div class="byline">
<p><em>Built by Parth Reddy. Anvil is open-source and runs on Claude.</em></p>
<p><a href="https://github.com/parthreddyprojects/anvil">github.com/parthreddyprojects/anvil</a></p>
</div>
</div>
</body>
</html>"""

Path("substack_article.html").write_text(html, encoding="utf-8")
print("Done — substack_article.html rebuilt")

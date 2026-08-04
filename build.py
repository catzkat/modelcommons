#!/usr/bin/env python3
"""Model Commons — site builder.

Inputs:
  - Constitution markdown (env CONSTITUTION_MD, default /tmp/claude-constitution/20260120-constitution.md)
  - Model Spec markdown (env MODEL_SPEC_MD, default /tmp/model-spec/model_spec.md; optional)
  - responses.json (approved public responses, produced by fetch_responses.py; optional)

Outputs (to env OUT_DIR, default: this script's directory):
  - index.html                 the landing page (archive overview)
  - claude-constitution.html   the constitution reader
  - openai-model-spec.html     the OpenAI Model Spec reader (only if its source is present)
  - responses.html   approved responses, grouped by clause, with support counts
  - .github/DISCUSSION_TEMPLATE/responses.yml  (clause dropdown kept in sync)

Note: the public-response / annotation layer currently applies only to the constitution.
Other archived documents are rendered read-only.
"""

import json, math, os, re, html, pathlib, datetime
from urllib.parse import quote
import markdown

HERE = pathlib.Path(__file__).parent
SRC = pathlib.Path(os.environ.get("CONSTITUTION_MD", "/tmp/claude-constitution/20260120-constitution.md"))
MODEL_SPEC_MD = pathlib.Path(os.environ.get("MODEL_SPEC_MD", "/tmp/model-spec/model_spec.md"))
OUT_DIR = pathlib.Path(os.environ.get("OUT_DIR", str(HERE)))
REPO = os.environ.get("GITHUB_REPOSITORY", "catzkat/modelcommons")  # owner/repo
RESPONSES = HERE / "responses.json"
INCLUDE_HYPOTHESIS = False   # set True to re-enable the Hypothes.is annotation layer
MAX_INLINE = 3               # max highly-supported responses shown inline per section
CONSTITUTION_HTML = "claude-constitution.html"  # filename for the constitution reader (index.html is the landing page)
MODEL_SPEC_HTML = "openai-model-spec.html"      # filename for the OpenAI Model Spec reader
MODEL_SPEC_VERSION = "December 18, 2025 (v2025.12.18)"

OUT_DIR.mkdir(parents=True, exist_ok=True)
today = datetime.date.today().strftime("%B %-d, %Y")

# ---------------- constitution markdown -> html ----------------
raw = SRC.read_text(encoding="utf-8")
lines = raw.splitlines()
body_start = next(i for i, ln in enumerate(lines[1:], start=1) if ln.startswith("# "))
text = "\n".join(ln.rstrip() for ln in lines[body_start:])

md = markdown.Markdown(extensions=["toc", "sane_lists"],
                       extension_configs={"toc": {"toc_depth": "1-4"}})
content_html = md.convert(text)
toc_tokens = md.toc_tokens

def flatten(tokens, depth=1):
    for t in tokens:
        yield t["id"], t["name"], depth
        yield from flatten(t.get("children") or [], depth + 1)

sections = list(flatten(toc_tokens))            # (id, name, depth)
section_names = {sid: name for sid, name, _ in sections}

# ---------------- responses ----------------
try:
    responses = json.loads(RESPONSES.read_text(encoding="utf-8"))
except FileNotFoundError:
    responses = []

by_anchor: dict[str, list] = {}
for r in responses:
    by_anchor.setdefault(r.get("anchor") or "general", []).append(r)
for v in by_anchor.values():
    v.sort(key=lambda r: (-r.get("votes", 0), r.get("created", "")))

votes_all = sorted((r.get("votes", 0) for r in responses), reverse=True)
if len(votes_all) >= 8:
    p75 = votes_all[max(0, math.ceil(len(votes_all) * 0.25) - 1)]
    THRESHOLD = max(3, p75)
else:
    THRESHOLD = 3

new_discussion = f"https://github.com/{REPO}/discussions/new?category=responses"

# ---------------- shared chrome ----------------
CSS = r"""
:root{
  --bg:#ffffff; --fg:#16181d; --muted:#6b7280; --faint:#9ca3af;
  --line:#e5e7eb; --accent:#2563eb; --accent-soft:#eff6ff;
  --sidebar-w:300px; --content-w:46rem;
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#0f1115; --fg:#e7e9ee; --muted:#9aa1ad; --faint:#6b7280;
         --line:#23262d; --accent:#7aa2ff; --accent-soft:#161c2a; }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header.site{position:fixed;top:0;left:0;right:0;height:56px;z-index:40;
  display:flex;align-items:center;gap:14px;padding:0 20px;
  background:color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.wordmark{font-weight:700;letter-spacing:-.01em;color:var(--fg);font-size:15px;white-space:nowrap}
.wordmark span{color:var(--muted);font-weight:400}
.doc-crumb{color:var(--muted);font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hdr-links{margin-left:auto;display:flex;gap:16px;align-items:center;font-size:13.5px}
#menu-btn{display:none;border:1px solid var(--line);background:none;color:var(--fg);
  border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer}
#progress{position:fixed;top:56px;left:0;height:2px;background:var(--accent);width:0;z-index:41}
.wrap{display:flex;max-width:1200px;margin:0 auto}
nav.toc{position:fixed;top:56px;bottom:0;width:var(--sidebar-w);overflow-y:auto;
  padding:28px 8px 40px 20px;border-right:1px solid var(--line);background:var(--bg)}
nav.toc ol{list-style:none;margin:0;padding:0}
.toc-l1>li{margin:2px 0 10px}
.toc-l1>li>a{font-weight:600;font-size:13.5px;color:var(--fg)}
.toc-l2{margin-top:4px !important;border-left:1px solid var(--line);padding-left:12px !important;margin-left:2px !important}
.toc-l2 a{font-size:13px;color:var(--muted);display:block;padding:2.5px 8px;border-radius:6px;line-height:1.45}
nav.toc a:hover{text-decoration:none;color:var(--accent)}
nav.toc a.active{color:var(--accent);background:var(--accent-soft)}
main{margin-left:var(--sidebar-w);padding:88px 40px 120px;flex:1;min-width:0}
article{max-width:var(--content-w);margin:0 auto}
.prov{border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:0 0 40px;
  font-size:13.5px;color:var(--muted);line-height:1.6}
.prov dl{display:grid;grid-template-columns:auto 1fr;gap:2px 18px;margin:10px 0 0}
.prov dt{font-weight:600;color:var(--fg)}
.prov dd{margin:0}
.badge{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 10px;
  font-size:12px;color:var(--muted)}
.doc-title{font-size:34px;line-height:1.2;letter-spacing:-.02em;font-weight:750;margin:0 0 6px}
.doc-sub{color:var(--muted);margin:0 0 28px;font-size:15px}
article h1{font-size:26px;letter-spacing:-.015em;line-height:1.25;margin:64px 0 16px;
  padding-top:18px;border-top:1px solid var(--line)}
article h2{font-size:20px;letter-spacing:-.01em;margin:44px 0 12px}
article h3{font-size:16.5px;margin:32px 0 10px}
article h4{margin:26px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;font-size:13px}
article p{margin:0 0 1.15em}
article li{margin:.35em 0}
article ul,article ol{padding-left:1.4em}
article blockquote{margin:1.2em 0;padding:.2em 1.2em;border-left:3px solid var(--line);color:var(--muted)}
article code{background:var(--accent-soft);border-radius:4px;padding:.1em .35em;font-size:.9em}
.anchor{opacity:0;margin-left:8px;font-size:.8em;color:var(--faint)}
h1:hover .anchor,h2:hover .anchor,h3:hover .anchor{opacity:1}
.hmeta{display:inline-flex;gap:10px;margin-left:10px;font-size:12.5px;font-weight:400;
  letter-spacing:0;text-transform:none;vertical-align:2px}
.hmeta a{color:var(--faint);border:1px solid var(--line);border-radius:999px;padding:1px 9px;white-space:nowrap}
.hmeta a:hover{color:var(--accent);border-color:var(--accent);text-decoration:none}
.hmeta a.has{color:var(--accent);background:var(--accent-soft);border-color:transparent}
footer.site{margin-left:var(--sidebar-w);border-top:1px solid var(--line);
  padding:28px 40px 48px;color:var(--muted);font-size:13.5px}
footer.site .inner{max-width:var(--content-w);margin:0 auto}
/* responses page */
.resp-controls{display:flex;gap:10px;align-items:center;margin:0 0 26px;flex-wrap:wrap}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.seg button{border:0;background:none;color:var(--muted);padding:7px 14px;font-size:13.5px;cursor:pointer}
.seg button.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
.method{border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:0 0 34px;
  font-size:13.5px;color:var(--muted);line-height:1.65}
.clause-group{margin:0 0 40px}
.clause-group>h2{font-size:15px;color:var(--muted);font-weight:600;margin:0 0 12px;
  padding-bottom:8px;border-bottom:1px solid var(--line)}
.clause-group>h2 a{color:inherit}
.resp{border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:0 0 14px}
.resp.hidden{display:none}
.resp-head{display:flex;gap:12px;align-items:baseline;font-size:13px;color:var(--muted);margin-bottom:8px;flex-wrap:wrap}
.resp-head .author{font-weight:600;color:var(--fg)}
.votes{margin-left:auto;font-variant-numeric:tabular-nums;border:1px solid var(--line);
  border-radius:999px;padding:1px 10px;font-size:12.5px;white-space:nowrap}
.votes.hot{color:var(--accent);border-color:var(--accent)}
.resp-body{font-size:15px}
.resp-body p{margin:0 0 .9em}
.resp-foot{font-size:12.5px}
.tag{display:inline-block;border-radius:6px;padding:0 8px;font-size:11.5px;font-weight:600;
  letter-spacing:.03em;text-transform:uppercase}
.tag.amendment{background:var(--accent-soft);color:var(--accent)}
.empty{border:1px dashed var(--line);border-radius:12px;padding:34px;text-align:center;color:var(--muted)}
/* text highlights + annotation rail */
mark.hl{background:var(--accent-soft);color:inherit;border-bottom:2px solid var(--accent);
  cursor:pointer;padding:0 1px;border-radius:2px}
mark.hl:hover{background:color-mix(in srgb, var(--accent) 20%, var(--bg))}
mark.hl.flash{outline:2px solid var(--accent);outline-offset:1px}
#notes-btn{border:1px solid var(--line);background:none;color:var(--fg);
  border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer;white-space:nowrap}
#notes-btn b{color:var(--accent);font-weight:600}
aside.notes{position:fixed;top:56px;right:0;bottom:0;width:350px;max-width:92vw;
  background:var(--bg);border-left:1px solid var(--line);overflow-y:auto;z-index:60;
  transform:translateX(105%);transition:transform .22s ease;box-shadow:-12px 0 40px rgba(0,0,0,.12)}
aside.notes.open{transform:none}
.notes-head{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;align-items:center;gap:8px;
  padding:14px 16px;border-bottom:1px solid var(--line);font-weight:600;font-size:14px}
.notes-head span{color:var(--muted);font-weight:400}
#notes-close{margin-left:auto;border:0;background:none;color:var(--muted);font-size:20px;cursor:pointer;line-height:1}
.notes-sec{padding:16px 16px 4px;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint)}
.note{margin:6px 12px;border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:13.5px}
.note.flash{outline:2px solid var(--accent);outline-offset:1px}
.note-head{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;color:var(--muted);font-size:12.5px;margin-bottom:6px}
.note-head .author{font-weight:600;color:var(--fg)}
.note-head .votes{margin-left:auto}
.note-quote{border-left:3px solid var(--accent);padding:2px 10px;margin:8px 0;
  color:var(--muted);font-style:italic;font-size:12.5px}
.note-body p{margin:0 0 .8em}
.notes-empty{padding:30px 20px;color:var(--muted);font-size:13.5px;text-align:center}
@media (max-width: 920px){
  nav.toc{transform:translateX(-105%);transition:transform .2s ease;z-index:50;box-shadow:0 0 40px rgba(0,0,0,.15)}
  nav.toc.open{transform:none}
  main,footer.site{margin-left:0}
  main{padding:80px 22px 90px}
  #menu-btn{display:block}
}
/* admonition / commentary blocks (e.g. OpenAI Model Spec) */
.admonition{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:10px;
  margin:1.4em 0;padding:2px 18px;background:color-mix(in srgb, var(--accent-soft) 45%, var(--bg))}
.admonition-title{margin:14px 0 4px;font-size:12px;font-weight:600;color:var(--muted);
  text-transform:uppercase;letter-spacing:.05em}
.admonition p{font-size:14.5px}
.admonition>:last-child{margin-bottom:14px}
/* landing */
article.landing{max-width:52rem}
.eyebrow{text-transform:uppercase;letter-spacing:.09em;font-size:12px;color:var(--faint);margin:0 0 16px;font-weight:600}
.landing .doc-title{font-size:40px;line-height:1.12;max-width:15em;margin-bottom:18px}
.landing .doc-sub{font-size:17px;line-height:1.55;max-width:33em;margin-bottom:52px}
.collection-h{font-size:12.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);font-weight:600;margin:0 0 16px}
.doc-card{display:flex;flex-wrap:wrap;gap:18px 28px;align-items:flex-start;justify-content:space-between;
  border:1px solid var(--line);border-radius:14px;padding:22px 24px;margin:0 0 14px;color:inherit;
  transition:border-color .15s ease,background .15s ease}
.doc-card:hover{text-decoration:none;border-color:var(--accent);background:var(--accent-soft)}
.doc-card-title{font-size:20px;font-weight:700;letter-spacing:-.012em;color:var(--fg)}
.doc-card-meta{font-size:13px;color:var(--muted);margin-top:4px}
.doc-card-desc{font-size:14.5px;color:var(--muted);margin:12px 0 0;max-width:34em}
.doc-card-stats{display:flex;flex-direction:column;gap:9px;align-items:flex-end;text-align:right;
  font-size:13px;color:var(--muted);white-space:nowrap}
.doc-card-go{color:var(--accent);font-weight:600}
.landing-hint{color:var(--faint);font-size:13px;margin:2px 0 0}
.landing-about{border-top:1px solid var(--line);padding-top:30px;margin-top:56px}
.landing-about p{color:var(--muted);font-size:14.5px;line-height:1.6;max-width:38em}
@media (max-width:920px){
  .landing .doc-title{font-size:32px}
  .doc-card-stats{align-items:flex-start;text-align:left}
}
"""

def header(crumb, toc_btn=True, notes_btn=False, links=None):
    btn = '<button id="menu-btn" aria-label="Toggle contents">Contents</button>' if toc_btn else ""
    nbtn = (f'<button id="notes-btn" aria-label="Toggle annotations">Annotations <b>{len(responses)}</b></button>'
            if notes_btn else "")
    if links is None:  # constitution / default nav
        links = f'<a href="/responses.html">Responses</a><a href="{new_discussion}" rel="noopener">Respond</a>'
    return f"""<header class="site">
  <a class="wordmark" href="/">Model Commons&nbsp;<span>/ the archive</span></a>
  <div class="doc-crumb">{crumb}</div>
  <div class="hdr-links">{links}{nbtn}{btn}</div>
</header>
<div id="progress"></div>"""

FOOTER = f"""<footer class="site">
  <div class="inner">
    <strong style="color:var(--fg)">Model Commons</strong> &mdash; the public record of AI&rsquo;s governing documents.<br>
    An independent archive, not affiliated with or endorsed by the publishers of the documents it archives.
    Document text reproduced verbatim under
    <a href="https://creativecommons.org/publicdomain/zero/1.0/" rel="noopener">CC0 1.0</a>.
    Found an error? <a href="mailto:hello@modelcommons.org">hello@modelcommons.org</a>
  </div>
</footer>"""

BASE_JS = r"""
(function(){
  var btn=document.getElementById('menu-btn'),toc=document.getElementById('toc');
  if(btn&&toc){btn.addEventListener('click',function(){toc.classList.toggle('open')});
    toc.addEventListener('click',function(e){if(e.target.tagName==='A')toc.classList.remove('open')});}
  var bar=document.getElementById('progress');
  function prog(){var h=document.documentElement,max=h.scrollHeight-h.clientHeight;
    bar.style.width=(max>0?(h.scrollTop/max)*100:0)+'%'}
  addEventListener('scroll',prog,{passive:true});prog();
  if(!toc)return;
  var links=[].slice.call(toc.querySelectorAll('a[data-target]'));
  var map={};links.forEach(function(a){map[a.getAttribute('data-target')]=a});
  var heads=[].slice.call(document.querySelectorAll('article h1[id],article h2[id],article h3[id]'))
    .filter(function(h){return map[h.id]});
  var current=null;
  function spy(){
    var y=scrollY+90,active=heads[0];
    for(var i=0;i<heads.length;i++){if(heads[i].offsetTop<=y)active=heads[i];else break}
    if(active&&active.id!==current){
      current=active.id;
      links.forEach(function(a){a.classList.remove('active')});
      var a=map[current];if(a){a.classList.add('active');
        var r=a.getBoundingClientRect(),t=toc.getBoundingClientRect();
        if(r.top<t.top+40||r.bottom>t.bottom-40)a.scrollIntoView({block:'center'})}
    }
  }
  addEventListener('scroll',spy,{passive:true});spy();
})();
"""

# ---------------- index.html ----------------
def toc_html(tokens):
    out = ["<ol class='toc-l1'>"]
    for t in tokens:
        out.append(f"<li><a href='#{t['id']}' data-target='{t['id']}'>{html.escape(t['name'])}</a>")
        kids = t.get("children") or []
        if kids:
            out.append("<ol class='toc-l2'>")
            for k in kids:
                out.append(f"<li><a href='#{k['id']}' data-target='{k['id']}'>{html.escape(k['name'])}</a></li>")
            out.append("</ol>")
        out.append("</li>")
    out.append("</ol>")
    return "\n".join(out)

def md_inline(s):
    return markdown.markdown(html.escape(s))

for _i, _r in enumerate(responses):
    _r["_id"] = _i

def inject_highlights(html_in):
    """Wrap each response's quoted passage (if found verbatim in the document) in a <mark>."""
    n = 0
    for r in responses:
        q = re.sub(r"\s+", " ", (r.get("quote") or "")).strip()
        if len(q) < 12:
            continue
        pat = r"\s+".join(re.escape(t) for t in q.split())
        try:
            m = re.search(pat, html_in)
        except re.error:
            continue
        if not m or "<" in m.group(0):
            continue
        s, e = m.span()
        html_in = (html_in[:s]
                   + f"<mark class=\"hl\" data-rid=\"{r['_id']}\" title=\"Annotated — click to view\">"
                   + html_in[s:e] + "</mark>" + html_in[e:])
        r["_hl"] = True
        n += 1
    return html_in, n

def rail_cards():
    """Annotation rail: all approved responses in document order, grouped by section."""
    order = {sid: i for i, (sid, _, _) in enumerate(sections)}
    rs = sorted(responses, key=lambda r: (order.get(r.get("anchor"), 9999), -r.get("votes", 0)))
    out, last = [], None
    for r in rs:
        sec = section_names.get(r.get("anchor"), "General")
        if sec != last:
            out.append(f"<div class='notes-sec'>{html.escape(sec)}</div>")
            last = sec
        votes = r.get("votes", 0)
        hot = votes >= THRESHOLD
        tag = "<span class='tag amendment'>Proposed amendment</span>" if r.get("type") == "amendment" else ""
        jump = (f"<a href='#' class='jump' data-rid='{r['_id']}'>Jump to text</a> &middot; "
                if r.get("_hl") else "")
        qtext = re.sub(r"\s+", " ", r.get("quote") or "")[:180]
        quote = f"<div class='note-quote'>{html.escape(qtext)}</div>" if qtext else ""
        out.append(f"""<div class="note" id="note-{r['_id']}">
  <div class="note-head">{tag}<span class="author">{html.escape(r.get('author',''))}</span>
    <span>{html.escape((r.get('created') or '')[:10])}</span>
    <span class="votes{' hot' if hot else ''}">&#9650; {votes}</span></div>
  {quote}
  <div class="note-body">{md_inline(r.get('body',''))}</div>
  <div class="resp-foot">{jump}<a href="{html.escape(r.get('url','#'))}" rel="noopener">Discuss on GitHub &rarr;</a></div>
</div>""")
    return "".join(out)

def heading_extras(m):
    tag, hid, inner = m.group(1), m.group(2), m.group(3)
    n = len(by_anchor.get(hid, []))
    chip = (f"<a class='has' href='responses.html#c-{hid}'>{n} response{'s' if n != 1 else ''}</a>") if n else ""
    respond = f"<a href='{new_discussion}&title={quote('Re: ' + re.sub('<[^>]+>', '', inner))}' rel='noopener'>respond</a>"
    return (f"<{tag} id=\"{hid}\">{inner}"
            f"<a class=\"anchor\" href=\"#{hid}\" aria-label=\"Link to this section\">&para;</a>"
            f"<span class=\"hmeta\">{chip}{respond}</span></{tag}>")

content_html = re.sub(r'<(h[12]) id="([^"]+)">(.*?)</\1>', heading_extras, content_html)
content_html = re.sub(
    r'<(h3) id="([^"]+)">(.*?)</\1>',
    r'<\1 id="\2">\3<a class="anchor" href="#\2" aria-label="Link to this section">&para;</a></\1>',
    content_html)
content_html, HL_COUNT = inject_highlights(content_html)

index_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude&rsquo;s Constitution &mdash; Model Commons</title>
<meta name="description" content="The full text of Claude's Constitution (Anthropic, January 2026), preserved with public responses by Model Commons — the public record of AI's governing documents.">
<style>{CSS}</style>
</head>
<body>
{header("Anthropic &middot; Claude&rsquo;s Constitution &middot; v. 2026-01-20", notes_btn=True)}
<div class="wrap">
<nav class="toc" id="toc" aria-label="Table of contents">
{toc_html(toc_tokens)}
</nav>
<main id="main">
<article>
  <h1 class="doc-title">Claude&rsquo;s Constitution</h1>
  <p class="doc-sub">Anthropic&rsquo;s foundational description of Claude&rsquo;s intended values and behavior.</p>
  <div class="prov">
    <span class="badge">Official text &middot; unmodified</span>
    <span class="badge">License: CC0 1.0</span>
    <dl>
      <dt>Publisher</dt><dd>Anthropic PBC</dd>
      <dt>Version</dt><dd>January 20, 2026 (current)</dd>
      <dt>Source</dt><dd><a href="https://github.com/anthropics/claude-constitution" rel="noopener">github.com/anthropics/claude-constitution</a> &middot; <a href="https://www.anthropic.com/constitution" rel="noopener">anthropic.com/constitution</a></dd>
      <dt>Archive updated</dt><dd>{today}</dd>
    </dl>
  </div>
{content_html}
</article>
</main>
</div>
<aside class="notes" id="notes" aria-label="Public annotations">
  <div class="notes-head">Annotations <span>{len(responses)}</span><button id="notes-close" aria-label="Close">&times;</button></div>
  {rail_cards() or f'<div class="notes-empty">No approved responses yet.<br><br><a href="{new_discussion}" rel="noopener">Be the first to respond &rarr;</a></div>'}
</aside>
{FOOTER}
<script>{BASE_JS}</script>
<script>
(function(){{
  var notes=document.getElementById('notes');
  var nbtn=document.getElementById('notes-btn');
  function open(){{notes.classList.add('open')}}
  function flash(el){{el.classList.add('flash');setTimeout(function(){{el.classList.remove('flash')}},1600)}}
  if(nbtn)nbtn.addEventListener('click',function(){{notes.classList.toggle('open')}});
  document.getElementById('notes-close').addEventListener('click',function(){{notes.classList.remove('open')}});
  [].slice.call(document.querySelectorAll('mark.hl')).forEach(function(m){{
    m.addEventListener('click',function(){{
      open();
      var c=document.getElementById('note-'+m.getAttribute('data-rid'));
      if(c){{c.scrollIntoView({{block:'center',behavior:'smooth'}});flash(c);}}
    }});
  }});
  [].slice.call(document.querySelectorAll('.note .jump')).forEach(function(j){{
    j.addEventListener('click',function(e){{
      e.preventDefault();
      var m=document.querySelector('mark.hl[data-rid="'+j.getAttribute('data-rid')+'"]');
      if(m){{m.scrollIntoView({{block:'center',behavior:'smooth'}});flash(m);}}
    }});
  }});
}})();
</script>
{'<script type="application/json" class="js-hypothesis-config">{"openSidebar": false, "showHighlights": true}</script><script src="https://hypothes.is/embed.js" async></script>' if INCLUDE_HYPOTHESIS else ''}
</body>
</html>
"""

# ---------------- responses.html ----------------
groups = []
ordered = [sid for sid, _, _ in sections if sid in by_anchor]
extras = [a for a in by_anchor if a not in section_names]
for a in ordered + extras:
    rs = by_anchor[a]
    name = section_names.get(a, "General")
    cards = []
    for r in rs:
        votes = r.get("votes", 0)
        hot = votes >= THRESHOLD
        tag = "<span class='tag amendment'>Proposed amendment</span> " if r.get("type") == "amendment" else ""
        cards.append(f"""<div class="resp{'' if hot else ''}" data-votes="{votes}">
  <div class="resp-head">{tag}<span class="author">{html.escape(r.get('author','anonymous'))}</span>
    <span>{html.escape((r.get('created') or '')[:10])}</span>
    <span class="votes{' hot' if hot else ''}" title="Support signals from GitHub accounts">&#9650; {votes}</span></div>
  <div class="resp-body">{md_inline(r.get('body',''))}</div>
  <div class="resp-foot"><a href="{html.escape(r.get('url','#'))}" rel="noopener">Discuss / support on GitHub &rarr;</a></div>
</div>""")
    link = f"{CONSTITUTION_HTML}#{a}" if a in section_names else CONSTITUTION_HTML
    groups.append(f"""<section class="clause-group" id="c-{a}">
  <h2><a href="{link}">&sect; {html.escape(name)}</a></h2>
  {''.join(cards)}
</section>""")

empty_state = f"""<div class="empty">No approved responses yet.<br><br>
<a href="{new_discussion}" rel="noopener">Be the first to respond &rarr;</a></div>"""

responses_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Public Responses &mdash; Model Commons</title>
<meta name="description" content="Approved public responses and proposed amendments to Claude's Constitution, ranked by community support.">
<style>{CSS}</style>
</head>
<body>
{header("Public responses &middot; Claude&rsquo;s Constitution", toc_btn=False)}
<main style="margin-left:0">
<article>
  <h1 class="doc-title">Public Responses</h1>
  <p class="doc-sub">Reader responses and proposed amendments to Claude&rsquo;s Constitution, attached to the clauses they address.</p>

  <div class="method">
    <strong style="color:var(--fg)">How this works.</strong>
    Responses are submitted through <a href="{new_discussion}" rel="noopener">GitHub Discussions</a> and appear here
    only after editorial review for substance and civility. &#9650; counts are support signals from GitHub accounts on the
    linked discussion &mdash; they rank responses for readability; they are not a poll, a vote, or a claim about public
    opinion. &ldquo;Most supported&rdquo; currently means {THRESHOLD}+ signals. Responses marked
    <span class="tag amendment">Proposed amendment</span> include exact replacement language for a specific clause.
  </div>

  <div class="resp-controls">
    <div class="seg" role="tablist">
      <button class="on" data-min="0">All responses</button>
      <button data-min="{THRESHOLD}">Most supported</button>
    </div>
    <span style="font-size:13px;color:var(--muted)">{len(responses)} approved response{'s' if len(responses)!=1 else ''}</span>
  </div>

  {''.join(groups) if groups else empty_state}
</article>
</main>
{FOOTER}
<script>{BASE_JS}</script>
<script>
(function(){{
  var btns=[].slice.call(document.querySelectorAll('.seg button'));
  btns.forEach(function(b){{b.addEventListener('click',function(){{
    btns.forEach(function(x){{x.classList.remove('on')}});b.classList.add('on');
    var min=+b.getAttribute('data-min');
    [].slice.call(document.querySelectorAll('.resp')).forEach(function(c){{
      c.classList.toggle('hidden', +c.getAttribute('data-votes')<min)}});
    [].slice.call(document.querySelectorAll('.clause-group')).forEach(function(g){{
      var any=g.querySelector('.resp:not(.hidden)');g.style.display=any?'':'none'}});
  }})}});
}})();
</script>
</body>
</html>
"""

# ---------------- discussion form (clause dropdown kept in sync) ----------------
clause_opts = "\n".join(f'        - "#{sid} — {name}"' for sid, name, depth in sections if depth <= 2)
form = f"""title: "Response: <short summary>"
labels: []
body:
  - type: markdown
    attributes:
      value: |
        Thanks for responding to Claude's Constitution. Substantive responses are reviewed and, if approved,
        published at modelcommons.org with attribution to your GitHub username. Upvote this discussion to
        support it once posted.
  - type: dropdown
    id: clause
    attributes:
      label: Clause
      description: Which section of the constitution does this respond to?
      options:
        - "#general — the document as a whole"
{clause_opts}
    validations:
      required: true
  - type: dropdown
    id: type
    attributes:
      label: Response type
      options:
        - Comment
        - Proposed amendment (includes exact replacement wording)
    validations:
      required: true
  - type: textarea
    id: quoted
    attributes:
      label: Quoted passage (optional)
      description: Paste the exact sentence(s) from the constitution your response addresses. If it matches, your response will be anchored as a highlight in the document text. Quote plain text without formatting.
    validations:
      required: false
  - type: textarea
    id: response
    attributes:
      label: Response
      description: For proposed amendments, quote the current wording and give your exact proposed wording, then the rationale.
    validations:
      required: true
"""

# ---------------- openai-model-spec.html (read-only reader) ----------------
try:
    ms_raw = MODEL_SPEC_MD.read_text(encoding="utf-8")
except FileNotFoundError:
    ms_raw = None

model_spec_page = None
if ms_raw:
    ms_md = markdown.Markdown(extensions=["toc", "sane_lists", "attr_list", "admonition", "smarty"],
                              extension_configs={"toc": {"toc_depth": "1-3"}})
    ms_content = ms_md.convert(ms_raw)
    ms_toc = ms_md.toc_tokens
    # anchor links on headings (no response chips — the response layer is constitution-only)
    ms_content = re.sub(
        r'<(h[123]) id="([^"]+)">(.*?)</\1>',
        r'<\1 id="\2">\3<a class="anchor" href="#\2" aria-label="Link to this section">&para;</a></\1>',
        ms_content, flags=re.S)
    # version label: track the top of the repo CHANGELOG (e.g. "## v2025.12.18"); fall back to constant
    ms_date, ms_vtag = MODEL_SPEC_VERSION.split(" (")[0], "v2025.12.18"
    try:
        cl = (MODEL_SPEC_MD.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        m = re.search(r'^##\s*v(\d{4})\.(\d{2})\.(\d{2})', cl, re.M)
        if m:
            ms_vtag = f"v{m.group(1)}.{m.group(2)}.{m.group(3)}"
            ms_date = datetime.date(*map(int, m.groups())).strftime("%B %-d, %Y")
    except FileNotFoundError:
        pass
    ms_version = f"{ms_date} ({ms_vtag})"
    ms_links = ('<a href="/">Archive</a>'
                '<a href="https://model-spec.openai.com/" rel="noopener">Official version</a>')
    model_spec_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenAI Model Spec &mdash; Model Commons</title>
<meta name="description" content="The full text of the OpenAI Model Spec ({ms_version}), OpenAI's specification of intended model behavior, preserved by Model Commons — the public record of AI's governing documents.">
<style>{CSS}</style>
</head>
<body>
{header(f"OpenAI &middot; Model Spec &middot; {ms_vtag}", links=ms_links)}
<div class="wrap">
<nav class="toc" id="toc" aria-label="Table of contents">
{toc_html(ms_toc)}
</nav>
<main id="main">
<article>
  <h1 class="doc-title">OpenAI Model Spec</h1>
  <p class="doc-sub">OpenAI&rsquo;s specification of the intended behavior for the models behind its products and API.</p>
  <div class="prov">
    <span class="badge">Official text &middot; unmodified</span>
    <span class="badge">License: CC0 1.0</span>
    <dl>
      <dt>Publisher</dt><dd>OpenAI</dd>
      <dt>Version</dt><dd>{ms_version}</dd>
      <dt>Source</dt><dd><a href="https://github.com/openai/model_spec" rel="noopener">github.com/openai/model_spec</a> &middot; <a href="https://model-spec.openai.com/" rel="noopener">model-spec.openai.com</a></dd>
      <dt>Archive updated</dt><dd>{today}</dd>
    </dl>
  </div>
{ms_content}
</article>
</main>
</div>
{FOOTER}
<script>{BASE_JS}</script>
</body>
</html>
"""

# ---------------- index.html (landing) ----------------
n_resp = len(responses)
resp_label = f"{n_resp} public response{'s' if n_resp != 1 else ''}"

# archive cards (constitution always present; model spec only if its source built)
constitution_card = f"""  <a class="doc-card" href="/{CONSTITUTION_HTML}">
    <div class="doc-card-main">
      <div class="doc-card-title">Claude&rsquo;s Constitution</div>
      <div class="doc-card-meta">Anthropic PBC &middot; Version January 20, 2026</div>
      <p class="doc-card-desc">Anthropic&rsquo;s foundational description of Claude&rsquo;s intended values and behavior.</p>
    </div>
    <div class="doc-card-stats">
      <span class="badge">CC0 1.0</span>
      <span>{resp_label}</span>
      <span class="doc-card-go">Read &rarr;</span>
    </div>
  </a>"""
model_spec_card = f"""  <a class="doc-card" href="/{MODEL_SPEC_HTML}">
    <div class="doc-card-main">
      <div class="doc-card-title">OpenAI Model Spec</div>
      <div class="doc-card-meta">OpenAI &middot; Version {ms_date}</div>
      <p class="doc-card-desc">OpenAI&rsquo;s specification of the intended behavior for the models behind its products and API.</p>
    </div>
    <div class="doc-card-stats">
      <span class="badge">CC0 1.0</span>
      <span class="doc-card-go">Read &rarr;</span>
    </div>
  </a>""" if model_spec_page else ""
archive_cards = "\n".join(c for c in (constitution_card, model_spec_card) if c)

landing_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model Commons &mdash; the public record of AI&rsquo;s governing documents</title>
<meta name="description" content="Model Commons preserves the foundational documents that define how AI systems are meant to behave — reproduced verbatim and opened to public response. Archiving Claude's Constitution and the OpenAI Model Spec.">
<style>{CSS}
footer.site{{margin-left:0}}
</style>
</head>
<body>
{header("", toc_btn=False)}
<main style="margin-left:0">
<article class="landing">
  <p class="eyebrow">An independent archive</p>
  <h1 class="doc-title">The public record of AI&rsquo;s governing documents.</h1>
  <p class="doc-sub">Model Commons preserves the foundational documents that define how AI systems are meant to
  behave &mdash; reproduced verbatim, and opened to public response, clause by clause.</p>

  <h2 class="collection-h">In the archive</h2>
{archive_cards}
  <p class="landing-hint">More documents as they&rsquo;re published.</p>

  <div class="landing-about">
    <h2 class="collection-h">How it works</h2>
    <p>Each document is reproduced in full from its official source. Readers respond to specific clauses through
    GitHub Discussions; substantive, civil responses are reviewed and published alongside the text they address.
    Nothing here is a poll or an endorsement &mdash; it is a durable, public record of the arguments.</p>
    <p><a href="/responses.html">Browse public responses &rarr;</a> &nbsp;&middot;&nbsp;
       <a href="{new_discussion}" rel="noopener">Add a response &rarr;</a></p>
  </div>
</article>
</main>
{FOOTER}
<script>{BASE_JS}</script>
</body>
</html>
"""

# ---------------- write ----------------
(OUT_DIR / "index.html").write_text(landing_page, encoding="utf-8")
(OUT_DIR / CONSTITUTION_HTML).write_text(index_page, encoding="utf-8")
(OUT_DIR / "responses.html").write_text(responses_page, encoding="utf-8")
if model_spec_page:
    (OUT_DIR / MODEL_SPEC_HTML).write_text(model_spec_page, encoding="utf-8")
tpl_dir = OUT_DIR / ".github" / "DISCUSSION_TEMPLATE"
tpl_dir.mkdir(parents=True, exist_ok=True)
(tpl_dir / "responses.yml").write_text(form, encoding="utf-8")

print(f"index.html      {len(landing_page):,} bytes (landing)")
print(f"{CONSTITUTION_HTML}  {len(index_page):,} bytes (constitution reader)")
if model_spec_page:
    print(f"{MODEL_SPEC_HTML}  {len(model_spec_page):,} bytes (model spec reader)")
else:
    print(f"{MODEL_SPEC_HTML}  skipped (source {MODEL_SPEC_MD} not found)")
print(f"responses.html  {len(responses_page):,} bytes ({len(responses)} responses, threshold {THRESHOLD})")
print(f"sections: {len(sections)}; anchors with responses: {len(by_anchor)}")

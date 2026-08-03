#!/usr/bin/env python3
"""Model Commons — site builder.

Inputs:
  - Constitution markdown (env CONSTITUTION_MD, default /tmp/claude-constitution/20260120-constitution.md)
  - responses.json (approved public responses, produced by fetch_responses.py; optional)

Outputs (to env OUT_DIR, default: this script's directory):
  - index.html       the constitution reader
  - responses.html   approved responses, grouped by clause, with support counts
  - .github/DISCUSSION_TEMPLATE/responses.yml  (clause dropdown kept in sync)
"""

import json, math, os, re, html, pathlib, datetime
from urllib.parse import quote
import markdown

HERE = pathlib.Path(__file__).parent
SRC = pathlib.Path(os.environ.get("CONSTITUTION_MD", "/tmp/claude-constitution/20260120-constitution.md"))
OUT_DIR = pathlib.Path(os.environ.get("OUT_DIR", str(HERE)))
REPO = os.environ.get("GITHUB_REPOSITORY", "catzkat/modelcommons")  # owner/repo
RESPONSES = HERE / "responses.json"
INCLUDE_HYPOTHESIS = False   # set True to re-enable the Hypothes.is annotation layer
MAX_INLINE = 3               # max highly-supported responses shown inline per section

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
    THRESHOLD = 1

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
/* inline annotations in the reader */
.annots{margin:14px 0 22px}
.annot{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:10px;
  margin:0 0 10px;background:color-mix(in srgb, var(--accent-soft) 45%, var(--bg))}
.annot summary{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;cursor:pointer;
  padding:10px 14px;font-size:13px;color:var(--muted);list-style:none}
.annot summary::-webkit-details-marker{display:none}
.annot summary .author{font-weight:600;color:var(--fg)}
.annot summary .excerpt{flex-basis:100%;color:var(--muted);font-style:italic}
.annot[open] summary .excerpt{display:none}
.annot .tag{background:var(--bg);border:1px solid var(--line);color:var(--muted)}
.annot .tag.amendment{background:var(--accent-soft);color:var(--accent);border-color:transparent}
.annot .votes{margin-left:0}
.annot-body{padding:2px 16px 12px;font-size:14.5px}
.annot-body p{margin:0 0 .8em}
@media (max-width: 920px){
  nav.toc{transform:translateX(-105%);transition:transform .2s ease;z-index:50;box-shadow:0 0 40px rgba(0,0,0,.15)}
  nav.toc.open{transform:none}
  main,footer.site{margin-left:0}
  main{padding:80px 22px 90px}
  #menu-btn{display:block}
}
"""

def header(crumb, toc_btn=True):
    btn = '<button id="menu-btn" aria-label="Toggle contents">Contents</button>' if toc_btn else ""
    return f"""<header class="site">
  <a class="wordmark" href="/">Model Commons&nbsp;<span>/ constitutions</span></a>
  <div class="doc-crumb">{crumb}</div>
  <div class="hdr-links"><a href="/responses.html">Responses</a><a href="{new_discussion}" rel="noopener">Respond</a>{btn}</div>
</header>
<div id="progress"></div>"""

FOOTER = f"""<footer class="site">
  <div class="inner">
    <strong style="color:var(--fg)">Model Commons</strong> &mdash; the public record of AI&rsquo;s governing documents.<br>
    An independent archive. Not affiliated with or endorsed by Anthropic. Document text reproduced verbatim under
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

def annot_cards(hid):
    """Inline annotation cards for highly-supported responses on this section."""
    hot = [r for r in by_anchor.get(hid, []) if r.get("votes", 0) >= THRESHOLD][:MAX_INLINE]
    if not hot:
        return ""
    cards = []
    for r in hot:
        excerpt = re.sub(r"\s+", " ", r.get("body", "")).strip()
        excerpt = (excerpt[:110] + "…") if len(excerpt) > 110 else excerpt
        tag = "<span class='tag amendment'>Proposed amendment</span>" if r.get("type") == "amendment" else "<span class='tag'>Response</span>"
        cards.append(f"""<details class="annot">
  <summary><span class="votes hot">&#9650; {r.get('votes',0)}</span> {tag}
    <span class="author">{html.escape(r.get('author',''))}</span>
    <span class="excerpt">{html.escape(excerpt)}</span></summary>
  <div class="annot-body">{md_inline(r.get('body',''))}
    <p class="resp-foot"><a href="{html.escape(r.get('url','#'))}" rel="noopener">Discuss / support on GitHub &rarr;</a>
    &middot; <a href="responses.html#c-{hid}">All responses to this section &rarr;</a></p></div>
</details>""")
    return f"<div class='annots' aria-label='Highly supported public responses'>{''.join(cards)}</div>"

def heading_extras(m):
    tag, hid, inner = m.group(1), m.group(2), m.group(3)
    n = len(by_anchor.get(hid, []))
    chip = (f"<a class='has' href='responses.html#c-{hid}'>{n} response{'s' if n != 1 else ''}</a>") if n else ""
    respond = f"<a href='{new_discussion}&title={quote('Re: ' + re.sub('<[^>]+>', '', inner))}' rel='noopener'>respond</a>"
    return (f"<{tag} id=\"{hid}\">{inner}"
            f"<a class=\"anchor\" href=\"#{hid}\" aria-label=\"Link to this section\">&para;</a>"
            f"<span class=\"hmeta\">{chip}{respond}</span></{tag}>"
            f"{annot_cards(hid)}")

content_html = re.sub(r'<(h[12]) id="([^"]+)">(.*?)</\1>', heading_extras, content_html)
content_html = re.sub(
    r'<(h3) id="([^"]+)">(.*?)</\1>',
    r'<\1 id="\2">\3<a class="anchor" href="#\2" aria-label="Link to this section">&para;</a></\1>',
    content_html)

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
{header("Anthropic &middot; Claude&rsquo;s Constitution &middot; v. 2026-01-20")}
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
{FOOTER}
<script>{BASE_JS}</script>
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
    link = f"index.html#{a}" if a in section_names else "index.html"
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
    id: response
    attributes:
      label: Response
      description: For proposed amendments, quote the current wording and give your exact proposed wording, then the rationale.
    validations:
      required: true
"""

# ---------------- write ----------------
(OUT_DIR / "index.html").write_text(index_page, encoding="utf-8")
(OUT_DIR / "responses.html").write_text(responses_page, encoding="utf-8")
tpl_dir = OUT_DIR / ".github" / "DISCUSSION_TEMPLATE"
tpl_dir.mkdir(parents=True, exist_ok=True)
(tpl_dir / "responses.yml").write_text(form, encoding="utf-8")

print(f"index.html      {len(index_page):,} bytes")
print(f"responses.html  {len(responses_page):,} bytes ({len(responses)} responses, threshold {THRESHOLD})")
print(f"sections: {len(sections)}; anchors with responses: {len(by_anchor)}")

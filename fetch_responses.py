#!/usr/bin/env python3
"""Model Commons — pull approved responses from GitHub Discussions into responses.json.

Requires env: GITHUB_TOKEN (Actions provides one), GITHUB_REPOSITORY (owner/repo).
A discussion is published iff it has the label 'approved' and is in the 'Responses' category.
Upvotes = the discussion's native upvote count.
"""

import glob, json, os, re, sys, urllib.request

TOKEN = os.environ["GITHUB_TOKEN"]
OWNER, REPO = os.environ.get("GITHUB_REPOSITORY", "catzkat/modelcommons").split("/")
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "responses.json")


def constitution_version_iso():
    """ISO date of the current constitution version, from its dated source filename
    (mirrors build.py's resolution). Used to stamp responses with the version in effect."""
    env = os.environ.get("CONSTITUTION_MD")
    if env:
        name = os.path.basename(env)
    else:
        files = sorted(glob.glob("/tmp/claude-constitution/*-constitution.md"))
        name = os.path.basename(files[-1]) if files else "20260120-constitution.md"
    m = re.match(r"(\d{4})(\d{2})(\d{2})", name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "2026-01-20"


CURRENT_VERSION = constitution_version_iso()

# Freeze the version stamp at first sight: keep any version already recorded for a
# discussion, so a later constitution update doesn't retroactively re-stamp old responses.
prev_versions = {}
try:
    with open(OUT_PATH, encoding="utf-8") as f:
        for _r in json.load(f):
            if _r.get("url") and _r.get("version"):
                prev_versions[_r["url"]] = _r["version"]
except (FileNotFoundError, json.JSONDecodeError):
    pass

QUERY = """
query($owner:String!, $repo:String!, $cursor:String) {
  repository(owner:$owner, name:$repo) {
    discussions(first:100, after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        title body url createdAt upvoteCount
        author { login }
        category { slug }
        labels(first:20) { nodes { name } }
      }
    }
  }
}
"""

def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        out = json.loads(r.read())
    if "errors" in out:
        sys.exit(f"GraphQL errors: {out['errors']}")
    return out["data"]

def parse_fields(body):
    """Extract clause anchor, response type, quoted passage, and response text from the discussion-form body."""
    anchor, rtype, quote = "general", "comment", ""
    m = re.search(r"###\s*Clause\s*\n+\s*\"?#([\w\-]+)", body)
    if m:
        anchor = m.group(1)
    m = re.search(r"###\s*Response type\s*\n+\s*(.+)", body)
    if m and "amendment" in m.group(1).lower():
        rtype = "amendment"
    m = re.search(r"###\s*Quoted passage[^\n]*\n(.*?)(?=\n###\s|\Z)", body, re.S)
    if m:
        quote = m.group(1).strip()
        if quote.lower() in ("_no response_", "no response"):
            quote = ""
    m = re.search(r"###\s*Response\s*\n(.*)", body, re.S)
    text = m.group(1).strip() if m else body.strip()
    return anchor, rtype, quote, text

responses, cursor = [], None
while True:
    data = gql(QUERY, {"owner": OWNER, "repo": REPO, "cursor": cursor})
    conn = data["repository"]["discussions"]
    for d in conn["nodes"]:
        labels = {l["name"] for l in d["labels"]["nodes"]}
        if "approved" not in labels:
            continue
        if (d["category"] or {}).get("slug") != "responses":
            continue
        anchor, rtype, quote, text = parse_fields(d["body"])
        responses.append({
            "title": d["title"],
            "author": (d["author"] or {}).get("login", "ghost"),
            "url": d["url"],
            "created": d["createdAt"],
            "votes": d["upvoteCount"],
            "anchor": anchor,
            "type": rtype,
            "quote": quote[:600],
            "body": text[:4000],
            "version": prev_versions.get(d["url"], CURRENT_VERSION),
        })
    if not conn["pageInfo"]["hasNextPage"]:
        break
    cursor = conn["pageInfo"]["endCursor"]

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(responses, f, indent=2, ensure_ascii=False)
print(f"wrote {len(responses)} approved responses to {OUT_PATH} (version stamp: {CURRENT_VERSION})")

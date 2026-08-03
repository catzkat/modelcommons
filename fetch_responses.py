#!/usr/bin/env python3
"""Model Commons — pull approved responses from GitHub Discussions into responses.json.

Requires env: GITHUB_TOKEN (Actions provides one), GITHUB_REPOSITORY (owner/repo).
A discussion is published iff it has the label 'approved' and is in the 'Responses' category.
Upvotes = the discussion's native upvote count.
"""

import json, os, re, sys, urllib.request

TOKEN = os.environ["GITHUB_TOKEN"]
OWNER, REPO = os.environ.get("GITHUB_REPOSITORY", "catzkat/modelcommons").split("/")

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
        })
    if not conn["pageInfo"]["hasNextPage"]:
        break
    cursor = conn["pageInfo"]["endCursor"]

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "responses.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(responses, f, indent=2, ensure_ascii=False)
print(f"wrote {len(responses)} approved responses to {out}")

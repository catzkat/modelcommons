# Model Commons

The public record of AI's governing documents. Currently archiving **Claude's Constitution**
(Anthropic, Jan 2026) with clause-anchored public responses.

Live at [modelcommons.org](https://www.modelcommons.org).

## How it works

- `build.py` renders the site from the [official constitution repo](https://github.com/anthropics/claude-constitution) (CC0) plus `responses.json`.
- Readers submit responses via **GitHub Discussions** (category: `Responses`, structured form).
- You review each discussion; adding the **`approved`** label publishes it.
- `fetch_responses.py` (run by the Action) pulls approved discussions + their native upvote counts.
- The Action rebuilds on discussion changes, daily (cron picks up upvote changes and upstream
  constitution edits), and on manual dispatch.
- `responses.html` shows all approved responses grouped by clause, with an
  "All / Most supported" toggle. Threshold = max(3, 75th percentile of votes) — computed at build time.

## One-time setup

1. **Copy these files** into the repo that serves GitHub Pages (keep your existing `CNAME` file).
2. **Enable Discussions**: Settings → General → Features → check Discussions.
3. **Create the category**: Discussions → pencil icon next to Categories → New →
   name `Responses` (format: Open-ended discussion). The slug must be `responses` —
   this makes the form in `.github/DISCUSSION_TEMPLATE/responses.yml` apply.
4. **Create the label**: Issues → Labels → New label → `approved`.
5. **Allow the Action to push**: Settings → Actions → General → Workflow permissions →
   "Read and write permissions".
6. Commit everything, then Actions → Build site → **Run workflow** once to generate the site.

## Moderation flow

New discussion arrives → read it → if substantive and civil, add the `approved` label →
the Action rebuilds and it appears on the site. Remove the label to unpublish.
Nothing appears on modelcommons.org without the label.

## Editorial standards (suggested starting point)

Approve responses that: address a specific clause, make an argument (not just a reaction),
and are civil. Mark nothing as endorsed — approval means "substantive," not "correct."
Vote counts are support signals, not polls; the site's methodology note says so.

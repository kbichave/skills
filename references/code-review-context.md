# Code Review — context auto-discovery

Loaded by the `code-review` skill at step 2 when the user picks
**Auto-discover**. Produces the `review_context` block the panel reviews
against.

## Establish what is connected

Do not assume a server is present or absent. Check the available tool list for
MCP servers (issue tracker, wiki, docs, roadmap) and `gh auth status` for
GitHub. Search only what you actually find.

## Search order

Stop once you have a spec.

1. **Ticket key** from the branch name (`CDA-1234-add-margin-model`), the
   commit messages, or the PR title/body (`#123`, `Closes #45`, `ABC-987`).
   Resolve it against the issue tracker MCP (Jira/Linear) or `bd show`.
   Branch names carry the key more reliably than commit messages do, so look
   there first.
2. **The PR itself**: `gh pr view <n> --json title,body,comments` for the
   description plus the conversation.
3. **Prior review rounds on this PR**:
   `gh api repos/<owner>/<repo>/pulls/<n>/comments`. What a human already
   raised is context, not noise. It tells you what was discussed and resolved,
   and re-raising a settled point wastes the author's time. Note any finding
   the panel later duplicates.
4. **Linked docs** named in the ticket or PR: wiki pages (Confluence MCP),
   shared documents and decks (SharePoint/M365 MCP), roadmap items (Airfocus
   MCP). Follow explicit links; do not search these broadly.
5. **In-repo spec**: a PRD or design doc under `docs/`, `specs/`, or the
   planning dir matching the branch/feature name.
6. Nothing found: proceed spec-less, and the report notes "no spec available".

## Bound the search

Two or three lookups that hit the linked ticket and PR beat ten speculative
searches, and every MCP round-trip is latency before the panel starts. Do not
full-text-search a wiki for a feature name on the chance something matches.

## Output

Summarize into a `review_context` block, ≤40 lines. Record which sources
answered, which were unavailable, and which you skipped, so the report
distinguishes "no spec exists" from "the wiki was not connected".

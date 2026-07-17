---
name: code-review
description: Standalone code review using the plugin's pack-scoped code-reviewer agent, outside of /deep implement. Reviews a diff, branch, or set of files against the quality rule-packs, gathers context interactively or via MCP auto-discovery, and web-verifies framework-behavior claims against current documentation. Use when the user asks to review code, review a diff/branch/PR, or check changes against the quality packs.
---

# Code Review (standalone)

Entry point to the same review machinery `/deep implement` Phase 5 uses —
without needing a planning session.

## Flow

### 1. Scope

Determine what to review:
- User named a base (`main`, a commit, a tag): `git diff <base>...HEAD --name-only`.
- User named files: use those.
- Nothing named: default to uncommitted + staged changes (`git diff HEAD --name-only`);
  if clean, ask for a base.

### 2. Context gathering

Ask once (AskUserQuestion):
1. **Provide** — user pastes ticket text, spec, or constraints.
2. **Skip** — review the code on its own terms.
3. **Auto-discover** — enumerate available MCPs and tooling, then pull
   context: issue keys from branch name / commit messages → issue tracker
   (Jira via Atlassian MCP, or `bd show`); PR description via `gh pr view`;
   linked specs via Confluence MCP. Summarize into a `review_context` block
   (≤40 lines). Use whatever is available; note what was skipped.

### 3. Resolve packs + languages

```python
from lib.pack_router import resolve_packs, detect_signals  # scripts/lib
```
If `pack_router` or a blueprint is unavailable, fall back to
`active_packs=["core"]` and infer languages from changed-file extensions.

### 4. Spawn the reviewer

Write a prompt file (temp) containing: changed files, section spec path
(or "none — standalone review"), `active_packs`, `languages`,
`review_context`. Spawn `deep-plan-enhanced:code-reviewer` with it.

### 5. Verify claims

The agent web-verifies framework-behavior claims it is unsure of (rule 10
in the agent definition). After the JSON returns, spot-check: any `high`
finding whose `fix` cites no tool output and no documentation URL gets one
verification pass — WebSearch the claim against current official docs.
Downgrade to `medium` + note if the docs contradict or don't support it.

### 6. Render the report

Translate the JSON for the user (the JSON is machine-facing):
- Verdict line: pass/fail + one-sentence summary.
- Findings grouped by severity — `high` 🔴 / `medium` 🟡 / `low` 🟢 —
  each as `file:line — issue → fix (rule_id)`, with verification sources
  where used.
- Praise entries, if any.
- Gates table (lint/types/security).
- Dead-code report (report-only — never auto-delete).

Offer to fix `high` findings; apply fixes only on user confirmation.

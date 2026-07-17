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

Fail fast before any agent spawns: `git rev-parse <base>` must resolve and the
diff must be non-empty. A bad ref or empty diff dies here, not inside a
sub-agent.

### 2. Context gathering

Ask once (AskUserQuestion):
1. **Provide** — user pastes ticket text, spec, or constraints.
2. **Skip** — review the code on its own terms.
3. **Auto-discover** — enumerate available MCPs and tooling, then pull
   context. Spec-source search order:
   1. Issue references in commit messages (`#123`, `Closes #45`, issue keys)
      → issue tracker (Jira via Atlassian MCP, or `bd show`).
   2. PR description via `gh pr view`; linked specs via Confluence MCP.
   3. A PRD/spec file under `docs/`, `specs/`, or the planning dir matching
      the branch/feature name.
   4. Nothing found → proceed spec-less; the report notes "no spec available".
   Summarize into a `review_context` block (≤40 lines). Use whatever is
   available; note what was skipped.

### 3. Resolve packs + languages

```python
from lib.pack_router import resolve_packs, detect_signals  # scripts/lib
```
If `pack_router` or a blueprint is unavailable, fall back to
`active_packs=["core"]` and infer languages from changed-file extensions.

### 4. Spawn the reviewer

Write a prompt file (temp) containing: changed files, section spec path
(or "none — standalone review"), `active_packs`, `languages`,
`review_context`. Spawn `deep:code-reviewer` with it.

### 5. Verify claims

The agent web-verifies framework-behavior claims it is unsure of (rule 10
in the agent definition). After the JSON returns, spot-check: any `high`
finding whose `fix` cites no tool output and no documentation URL gets one
verification pass — WebSearch the claim against current official docs.
Downgrade to `medium` + note if the docs contradict or don't support it.

### 6. Render the report

Translate the JSON for the user (the JSON is machine-facing). Report on
**two separate axes** — do not merge or rerank across them, so a clean
standards pass can't mask a spec miss (and vice versa):

- **`## Spec`** — SPEC-COMPLIANCE findings: missing/partial requirements,
  scope creep, implemented-but-wrong. Quote the spec/`review_context` line
  per finding. No spec → "no spec available".
- **`## Standards`** — everything else (rule-pack findings). Documented repo
  standards override judgment-call heuristics: where a repo convention
  endorses something a heuristic would flag, suppress the finding. Design
  smells (see `references/quality/cross-cutting/code-quality-universal.md`)
  are always labelled judgment calls, never hard violations.

Within each axis:
- Verdict line: pass/fail + one-sentence summary.
- Findings grouped by severity — `high` 🔴 / `medium` 🟡 / `low` 🟢 —
  each as `file:line — issue → fix (rule_id)`, with verification sources
  where used.
- Praise entries, if any.
- Gates table (lint/types/security).
- Dead-code report (report-only — never auto-delete).

Offer to fix `high` findings; apply fixes only on user confirmation.

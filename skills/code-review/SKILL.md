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

**Mandatory gate — do not spawn the reviewer without completing this step.**
Skip the question ONLY if the invocation itself already carried spec/ticket
context (e.g. the user pasted requirements or named a ticket when calling
the skill); in that case use it as `review_context` and say so.

Otherwise ask (AskUserQuestion):
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

- **`## Improvements`** — the reviewer's advisory `improvements` entries:
  better-way suggestions (logic simplification, architecture alternatives,
  idiomatic/advanced techniques achieving the same behavior). Render each as
  `file:line — current → better (technique): why`. Advisory only — never
  affects either verdict. Omit the section when empty.

Within each axis:
- Verdict line: pass/fail + one-sentence summary.
- Findings grouped by severity — `high` 🔴 / `medium` 🟡 / `low` 🟢 —
  each as `file:line — issue → fix (rule_id)`, with verification sources
  where used.
- Praise entries, if any.
- Gates table (lint/types/security).
- Dead-code report (report-only — never auto-delete).

Offer to fix `high` findings; apply fixes only on user confirmation.

### 7. Write the report file

Always persist the full report to the reviewed repo, then echo the path in
chat. Path: `.reviews/code-review-<branch>-<YYYY-MM-DD>.md` at the repo root
(create `.reviews/` if missing; slugify the branch name; append `-2`, `-3`,
… if the file already exists). If `.reviews/` is not in `.gitignore`, note
that to the user — do not edit `.gitignore` unasked.

File format:

```markdown
---
repo: <repo name>
branch: <branch>
base: <base ref or "uncommitted">
date: <YYYY-MM-DD>
packs: [<active_packs>]
languages: [<languages>]
spec: <spec source or "none">
verdict_spec: <pass|fail|n/a>
verdict_standards: <pass|fail>
---

# Code Review — <branch> (<date>)

## Spec
<verdict line, then findings>

## Standards
<verdict line, then findings>

## Findings table

| Severity | File | Line | Rule | Issue | Fix |
|----------|------|------|------|-------|-----|
| high | src/auth.py | 42 | core.error-handling | ... | ... |

## Improvements

| File | Line | Current | Better | Technique | Why |
|------|------|---------|--------|-----------|-----|
| src/api/users.py | 51 | manual dict loop | `Counter(...)` | collections.Counter | one tested line replaces 6 |

## Gates
<lint/types/security table>

## Dead code
<report-only list>
```

Every finding row carries the exact `file` path (repo-relative) and `line`
from the reviewer JSON — never omit or approximate them. Findings fixed
during step 6 stay in the table, marked `(fixed)` in the Fix column.

### 8. Insert review markers in source

After the report file is written, annotate the reviewed source files with
greppable comment markers at each finding's line:

- `issues` (high/medium, not yet fixed) →
  `CODECHANGE(review): <rule_id> — <one-line fix>`
- `improvements` and `low` issues →
  `RECOMMENDATION(review): <technique> — <one-line why>`

Placement rules:
- Insert as a full-line comment directly **above** the flagged line, using
  the file's comment syntax (`#` Python/shell, `//` TS/JS/Go, `<!-- -->`
  HTML/MD). Match the flagged line's indentation.
- Process each file **bottom-up** so earlier insertions don't shift later
  line numbers.
- Skip: findings already fixed in step 6, generated/vendored files, and any
  line that already carries a `CODECHANGE(review)`/`RECOMMENDATION(review)`
  marker (no duplicates on re-review).
- Markers go only in files the review covered — never elsewhere.

Append a `## Markers inserted` list (`file:line — marker text`) to the
report file, and tell the user markers are greppable via
`grep -rn "(review):" <paths>`. Markers are working annotations — the user
removes them as they address each one; they are not meant to be committed.

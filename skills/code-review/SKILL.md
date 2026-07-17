---
name: code-review
description: Standalone multi-expert code review, outside of /deep implement. Routes the diff to a panel of specialist reviewer subagents (core packs, logic, architecture, ML, stats, MLOps, data engineering, prompt engineering), verifies claims against current docs, gates everything through a final review-verifier, writes a .reviews/ report, and walks the user through humanized approve/skip/edit triage before inserting inline CODECHANGE/RECOMMENDATION markers. Use when the user asks to review code, review a diff/branch/PR, or check changes against the quality packs. Do NOT use for writing or fixing code (only reviewing it), for /deep implement Phase 5 (that flow spawns the reviewer itself), for reviewing prose documents/PRDs, or for git operations like merging or resolving conflicts.
---

# Code Review (standalone, expert panel)

Multi-expert review: the diff decides which specialist subagents spawn, two
verifier stages filter their findings, and only user-approved comments land
in the source.

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

**Mandatory gate — do not spawn the panel without completing this step.**
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

### 4. Assemble and spawn the review panel

Route experts from the diff's signals, then spawn ALL selected experts **in
parallel — one message, multiple Agent calls**. Every expert follows
`references/review-panel-protocol.md`.

| Expert | Spawn when |
|---|---|
| `deep:code-reviewer` (core) | Always — packs, security, gates, dead code |
| `deep:logic-reviewer` | Always — correctness deep-dive |
| `deep:architecture-reviewer` | ≥8 changed files, a new module/package, or cross-package import changes |
| `deep:ml-reviewer` | torch / tensorflow / sklearn / xgboost / lightgbm / transformers imports; training/eval scripts; `.ipynb` |
| `deep:stats-reviewer` | scipy.stats / statsmodels; A/B-test, experiment-analysis, metric-definition, or forecasting code |
| `deep:mlops-reviewer` | Dockerfile / K8s manifests; Airflow / Dagster / Prefect; MLflow / W&B; model-serving or feature-store code; ML CI |
| `deep:data-eng-reviewer` | `.sql` files, dbt models, Spark, pandas/polars ETL |
| `deep:skill-reviewer` | `**/SKILL.md`, `agents/*.md`, or hook-prompt files |
| `deep:prompt-reviewer` | LLM/API prompts, prompt templates, inline model instructions in app code |

Detect signals by extension + `grep -l` for the trigger imports across
changed files. When in doubt, spawn — a no-findings expert returns cheaply.
Tell the user which experts were selected and why (one line each).

Each expert's prompt file (temp) contains: `changed_files`, `diff_base`,
`review_context`, its `focus`. The core reviewer additionally gets
`active_packs`, `languages`, and the section spec path (or "none —
standalone review") per its own contract.

### 5. Merge and verify (sequential chain)

1. **Merge** all expert JSONs into one findings set. Keep each finding's
   `expert` tag. Do not dedupe or rerank yourself — the verifiers own that.
2. **`deep:claim-verifier`** — spawn if any finding has
   `needs_verification: true` or any `high` finding cites neither tool
   output nor a documentation URL. It web-verifies each claim against
   current official docs and returns confirmed/contradicted/unresolved
   verdicts with sources. Skip only when nothing qualifies.
3. **`deep:review-verifier`** — ALWAYS spawn, always last. It re-reads the
   actual code for every finding, kills phantoms, fixes wrong file:line
   refs, merges duplicate findings across experts, normalizes severity, and
   applies the claim verdicts. Its approved set is the ONLY set that
   reaches steps 6–8. Relay its rejection count to the user
   ("panel raised N, verifier approved M").
4. **Coverage gaps** — if `verifier_report.coverage_gaps` is non-empty,
   re-spawn the responsible expert(s) once with ONLY the missed files, merge
   their findings, and send the additions back through the review-verifier.
   One retry round max; still-open gaps are listed in the report under
   `## Coverage gaps` so nothing silently goes unreviewed.

### 6. Render the report

Translate the JSON for the user (the JSON is machine-facing). Report on
**two separate axes** — do not merge or rerank across them, so a clean
standards pass can't mask a spec miss (and vice versa):

- **`## Spec`** — SPEC-COMPLIANCE findings: missing/partial requirements,
  scope creep, implemented-but-wrong. Quote the spec/`review_context` line
  per finding. No spec → "no spec available".
- **`## Standards`** — every non-spec finding from the whole panel: core
  rule-pack findings (`SEC-*`, `ENG-*`, …) AND specialist findings
  (`LOGIC-*`, `ML-*`, `STATS-*`, `MLOPS-*`, `DE-*`, `ARCH-*`, `PROMPT-*`).
  Group by expert, then severity. Documented repo standards override
  judgment-call heuristics: where a repo convention endorses something a
  heuristic would flag, suppress the finding. Design smells (see
  `references/quality/cross-cutting/code-quality-universal.md`) are always
  labelled judgment calls, never hard violations.

- **`## Improvements`** — the panel's advisory `improvements` entries:
  better-way suggestions (logic simplification, architecture alternatives,
  idiomatic/advanced techniques achieving the same behavior). Render each as
  `file:line — current → better (technique): why`. Advisory only — never
  affects either verdict. Omit the section when empty.

Within each axis:
- Verdict line: pass/fail + one-sentence summary.
- Findings grouped by severity — `high` 🔴 / `medium` 🟡 / `low` 🟢 —
  each as `file:line — issue → fix (rule_id or tag) [expert]`, with
  verification sources where used.
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
panel: [<experts spawned>]
verifier: "raised <N>, approved <M>"
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

| Severity | File | Line | Rule/Tag | Expert | Issue | Fix |
|----------|------|------|----------|--------|-------|-----|
| high | src/auth.py | 42 | SEC-003 | core | ... | ... |
| high | src/train.py | 87 | ML-LEAKAGE | ml | ... | ... |

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

### 8. Humanized triage — approve, skip, or comment per finding

After the report file is written, walk the user through every unfixed
finding and improvement, one decision each:

1. **Humanize** each finding's comment text with the `deep:humanizer` skill
   — the marker line the user will live with in their code should read like
   a sharp colleague's note, not agent output. Humanize the one-line marker
   text only; the report file keeps the precise original wording.
2. **Present** findings via AskUserQuestion — batch up to 4 per call,
   ordered high → medium → low → improvements. Each question shows
   `file:line`, the humanized comment, and the code context; options:
   - **Approve** — insert the marker as shown.
   - **Skip** — no marker; report file marks the row `(skipped)`.
   - **Edit comment** — user supplies their own wording (via "Other"/notes);
     insert the marker with the user's text.
3. **Insert markers for approved findings only** (rules below).

### Marker insertion (approved findings only)

Build one approved-markers JSON payload and pipe it to the insertion script —
do NOT do the line arithmetic yourself. The script handles bottom-up ordering,
language-aware comment syntax, indentation, and idempotency deterministically:

```bash
echo '<payload>' | uv run --no-project \
  ${DEEP_PLUGIN_ROOT}/scripts/checks/apply-review-markers.py
```

Payload — one entry per approved finding:
```json
{"markers": [
  {"file": "src/api.py", "line": 34, "kind": "CODECHANGE",
   "text": "<rule_id or tag> — <humanized one-line fix>"},
  {"file": "src/api.py", "line": 51, "kind": "RECOMMENDATION",
   "text": "<technique> — <humanized one-line why>"}
]}
```

- `kind`: `CODECHANGE` for approved high/medium `issues`; `RECOMMENDATION` for
  approved `improvements` and `low` issues.
- Exclude: findings fixed in step 6, skipped findings, and generated/vendored
  files. The script itself skips lines already carrying a `(review):` marker
  (idempotent re-review) and reports `inserted`/`skipped` counts.

Append a `## Markers inserted` list (`file:line — marker text — approved/
edited`) plus a `## Skipped` list to the report file, and tell the user
markers are greppable via `grep -rn "(review):" <paths>`. Markers are
working annotations — the user removes them as they address each one; they
are not meant to be committed.

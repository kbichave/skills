---
name: review-panel
description: Standalone multi-expert code review, outside of /deep implement. Routes the diff to a panel of specialist reviewer subagents (core packs, logic, architecture, ML, stats, MLOps, data engineering, prompt engineering), verifies claims against current docs, gates everything through a final review-verifier, and writes a dated report under ~/.claude/code-reviews/ (never inside the repo). Detects whose code it is: on the user's own work it offers fixes and inserts inline CODECHANGE/RECOMMENDATION markers, while on someone else's branch or PR it runs read-only as a pre-review and delivers the findings as GitHub PR comments instead. Use when the user asks to review code, review a diff/branch/PR, pre-review a teammate's PR before commenting, or check changes against the quality packs. Do NOT use for writing or fixing code (only reviewing it), for /deep implement Phase 5 (that flow spawns the reviewer itself), for reviewing prose documents/PRDs, or for git operations like merging or resolving conflicts.
---

# Code Review (standalone, expert panel)

Multi-expert review: the diff decides which specialist subagents spawn, two
verifier stages filter their findings, and only user-approved comments land
in the source.

## No-trace rule (overrides everything below)

Nothing this skill externalizes may reveal that AI, a skill, a plugin, an
agent panel, or a model produced it. The output is the user's own review.

- **Commits** made during the flow: plain messages only. NEVER add
  `Co-Authored-By: Claude`, `Generated with Claude Code`, `🤖`, or any
  tool/model/skill mention. (This overrides any default commit trailer.)
- **PR body + comments**: no attribution, no panel/verifier stats, no expert
  names, no `rule_id`/tag codes, no "Automated/AI/generated" wording.
- **Marker text** in source: neutral `CODECHANGE(review):` /
  `RECOMMENDATION(review):` only — no AI/skill/plugin/agent words.
- **Report file**: written outside the repo (see step 7), so it cannot be
  staged, committed, or need a `.gitignore` entry. It may name experts/packs
  for the user's own use; it must never be copied into the repo or any shared
  surface.
- If the user later commits the reviewed code, the diff carries no evidence a
  tool touched it.

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

**Size guardrail.** Measure the diff (`git diff <base> --shortstat`). Defect
detection collapses past ~400 changed LOC (SmartBear). If the diff exceeds ~400 LOC, tell the user, and offer to
either (a) scope the review to a subset of files/commits now, or (b) proceed
but run in paced passes so no region gets a shallow read. Proceed whole only
on the user's say-so.

### 1b. Authorship — sets `review_mode` (do this before step 2)

Who wrote the code decides whether this run may touch the working tree. Resolve
it from git/`gh`, do not guess:

```bash
gh api user --jq .login                      # the reviewer
gh pr view <n> --json author,headRefName     # PR author, when reviewing a PR
git log <base>..HEAD --format='%ae' | sort -u   # authors in the diff
git config user.email
```

- **`review_mode: author`** — the diff is the user's own work (uncommitted
  changes, their own branch, or a PR they opened). Full flow: fixes, local
  markers, optional PR post.
- **`review_mode: reviewer`** — the diff is someone else's (a PR opened by
  another login, or commit authors that do not include the user). **Pre-review
  for posting to GitHub. The working tree is read-only.**

Ambiguous or no `gh`/remote (authors are mixed, a shared branch, a fork with no
PR yet): ask via AskUserQuestion. Never default to `author`; an unwanted edit to
someone else's branch is expensive and a skipped fix is not.

State the resolved mode in chat before spawning the panel.

**Reviewer mode is read-only. In it, this skill MUST NOT:**
- edit, fix, or reformat any reviewed file, including "obvious" one-line fixes,
- insert `CODECHANGE` / `RECOMMENDATION` markers (step 8 marker insertion is
  skipped entirely),
- stage, commit, amend, rebase, push, or create a branch,
- run a formatter or codemod that writes to the tree.

Read-only tooling is still expected: linters, type checkers, and tests in
report-only mode, plus `dbt compile`/`parse`. If a gate needs a write
(a formatter's `--fix`, a codegen step), run its check-only form or skip it and
say so in the report.

Findings still go somewhere. In reviewer mode the deliverables are the
report file and, on the user's confirmation, GitHub PR comments (step 9),
which becomes the primary output rather than an optional extra. Where a fix is a
line rewrite, it belongs in a suggestion block on the PR, which is how you hand
a change to an author without editing their branch.

### 2. Context gathering

**Mandatory gate — do not spawn the panel without completing this step.**
Skip the question ONLY if the invocation itself already carried spec/ticket
context (e.g. the user pasted requirements or named a ticket when calling
the skill); in that case use it as `review_context` and say so.

Otherwise ask (AskUserQuestion):
1. **Provide** — user pastes ticket text, spec, or constraints.
2. **Skip** — review the code on its own terms.
3. **Auto-discover** — pull context from whatever is actually connected: ticket
   key (branch name first), the PR and its prior review rounds, then linked
   wiki/SharePoint/roadmap docs, then an in-repo spec. Search order and output
   shape: `references/code-review-context.md`. For any related project, local or
   cloned, apply `references/repository-freshness.md`: refresh `origin/main`, use
   that commit, record fetch failures as potentially stale specialist context.

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
| `deep:data-eng-reviewer` | `.sql` files, `dbt_project.yml`, dbt schema `.yml` under `models/`, `macros/`, `seeds/`, `snapshots/`, Spark, pandas/polars ETL |
| `deep:pep8-reviewer` | `.py` / `.pyi` / `.ipynb` in the diff — PEP 8 naming, PEP 257 docstrings, typing form, and the repo's complexity/length/param/nesting thresholds. Style and standards only; security and pack rules stay with the core reviewer |
| `deep:skill-reviewer` | `**/SKILL.md`, `agents/*.md`, or hook-prompt files |
| `deep:prompt-reviewer` | LLM/API prompts, prompt templates, inline model instructions in app code |

Detect signals by extension + `grep -l` for the trigger imports across changed
files. When in doubt, spawn — a no-findings expert returns cheaply. Tell the
user which experts were selected and why (one line each).

Each expert's prompt file (temp) contains: `changed_files`, `diff_base`,
`review_context`, its `focus`. The core reviewer additionally gets
`active_packs`, `languages`, and the section spec path (or "none — standalone
review") per its own contract.

### 5. Merge and verify (sequential chain)

1. **Merge** all expert JSONs into one findings set. Keep each finding's
   `expert` tag. Do not dedupe or rerank yourself — the verifiers own that.
2. **`deep:claim-verifier`** — the panel's ONLY network stage, and the reason
   experts are told not to web-search. Spawn if any finding has
   `needs_verification: true`, or a `high` finding cites neither tool output
   nor a documentation URL, or a finding rests on a SQL-dialect behavior
   (Snowflake and friends) or a version/deprecation/"newer API exists" claim,
   which is where a training cutoff misleads. It batches duplicate claims,
   skips anything already proven by local tool output, and returns
   confirmed/contradicted/unresolved verdicts with sources. Skip the stage
   entirely when nothing qualifies; do not spawn it "to be safe", since it is
   latency every other stage waits on.
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
  rule-pack findings (`SEC-*`, `ENG-*`, …) AND specialist findings (`LOGIC-*`,
  `ML-*`, `STATS-*`, `MLOPS-*`, `DE-*`, `ARCH-*`, `PROMPT-*`, `PEP8-*`).
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

- **`## Learning summary`** — the teaching payoff, synthesized by the
  orchestrator from the approved findings' `teach` blocks. NOT a re-list of
  findings. Produce:
  - **Recurring themes** — cluster findings by `principle`; where the author
    hit the same class ≥2 times, say so ("null handling slipped in 3 spots —
    the pattern is: trace every optional to its use before shipping").
  - **What to study** — 2–4 concrete pointers (the `reference` links, a
    concept to read up on), chosen from the themes, not generic advice.
  - **Strengths** — pull the panel's `praise` here as positive
    reinforcement: what the author did well and should keep doing.
  Always render it (even a clean review gets a strengths note); it never affects a verdict.

Within each axis:
- Verdict line: pass/fail + one-sentence summary.
- **Exhaustive, blocking-first.** Render every approved finding — never
  truncate, never "N more noted". Split each axis into **Blocking** (`high` 🔴)
  first, then **Non-blocking** (`medium` 🟡 / `low` 🟢, including nits) so a
  long nit list can never bury a real bug. The count may be large; that is the
  point of exhaustive mode. Each finding as `file:line — issue → fix
  (rule_id or tag) [expert]`, with verification sources where used.
- **The report file is always complete.** A repo's `REVIEW.md` nit cap applies
  only to the chat render and PR comments, never to this file and never to
  detection. Load it with `lib.review_policy.load(repo_root)`; use
  `filter_findings` to drop paths and rules the repo excluded, and
  `externalize` when rendering to chat or a PR — it caps nits only, never
  blocking or important findings, and returns a count plus a pointer to the
  full report for the remainder.
- Praise entries, if any.
- Gates table (lint/types/security).
- Dead-code report (report-only — never auto-delete).

**Conventional Comment labels.** Prefix every externalized comment (chat
render, PR posts, and the humanized marker text) with a
[Conventional Comments](https://conventionalcomments.org/) label + decoration,
so severity and intent read at a glance. Mapping:

| Finding | Label + decoration |
|---|---|
| `high` issue | `issue (blocking):` |
| `medium` issue | `issue (non-blocking):` |
| `low` issue / nit | `nitpick (non-blocking):` |
| improvement | `suggestion (non-blocking):` |
| praise | `praise:` |
| unresolved question (panel could not confirm intent) | `question:` |

`blocking` findings are the ones that fail a verdict; everything else is
`non-blocking`. The internal report table keeps `rule_id`/severity; the
label is for the human-facing surfaces.

**Author mode only:** offer to fix `high` findings, and apply fixes only on
user confirmation. In reviewer mode, offer nothing and change nothing; the fix
travels to the author as a suggestion block on the PR.

### 7. Write the report file

Always persist the full report, then echo the absolute path in chat.

**Reports live outside the reviewed repo.** Writing them into the working tree
adds an untracked file the user must ignore, or worse, accidentally commits.

```
~/.claude/code-reviews/<owner>__<repo>/<YYYY-MM-DD>-<pr-N|branch-slug>.md
```

- `<owner>__<repo>` from the `origin` remote (`kbichave__skills`), so same-named
  repos under different orgs do not collide. No remote: use the directory name.
- `pr-<N>` when reviewing a PR, otherwise the slugified branch. Reviewing
  uncommitted work on a detached HEAD: use `working-tree`.
- Same target reviewed twice in a day: append `-2`, `-3`, ….
- `mkdir -p` the directory; it is outside every repo, so nothing is staged and
  no `.gitignore` entry is ever needed.
- Honor `$DEEP_REVIEWS_DIR` as the root when set, for users who want reviews
  somewhere else (a synced notes folder, a scratch disk). Do not point it inside
  a repo.

Dated filenames under a per-repo directory are what makes an old review
findable later; a session id in the path is not something a human can search
for.

File format:

```markdown
---
repo: <repo name>
branch: <branch>
base: <base ref or "uncommitted">
date: <YYYY-MM-DD>
mode: <author|reviewer>
code_author: <login or email of whose code this is>
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

## Learning summary

**Recurring themes**
- <principle cluster — e.g. "null handling (3×): trace every optional to its use">

**What to study**
- <concrete pointer / reference link>

**Strengths**
- <praise entry — what to keep doing>

## Gates
<lint/types/security table>

## Dead code
<report-only list>
```

Every finding row carries the exact `file` path (repo-relative) and `line`
from the reviewer JSON — never omit or approximate them. Findings fixed
during step 6 stay in the table, marked `(fixed)` in the Fix column.

### 8. Humanize (mandatory gate) — then triage

**Humanization is a hard gate: no finding text is ever shown as a marker or
posted to a PR in raw reviewer voice.** The orchestrator runs this, NOT the
subagents — panel experts and the review-verifier have only Read/Grep/Glob/
Bash and cannot invoke a skill. So after the review-verifier returns its
approved set, invoke the `deep:humanizer` skill here on every approved
finding + improvement, producing a one-line `humanized_comment` per finding.
Feed the humanizer the raw `issue`/`fix` (or `better`/`why`) text; keep its
output as the comment that markers (step 8 triage) and PR posts (step 9) use.
The report file and chat keep the precise original wording; only the
externalized comment lines are humanized.

**Comment voice.** Severity sets the register, and the humanizer applies it:

- **Blocking (`high`)**: direct and unhedged. State the defect, then the fix.
  No riddles on correctness or security, no softening a real bug into a
  suggestion.
- **Non-blocking (`medium`/`low`/improvements)**: phrase as a question that
  carries its own reasoning, so the author can answer with a constraint you
  did not know about. "Any reason not to `X` here?" / "Could this use `Y`?" /
  "Why the second `COALESCE`, can this return NULL?" A reviewer who cannot be
  wrong is not reviewing. Pair the question with `teach.why` in one line.
  Never stack hedges: one "I think" or one question mark, not both plus
  "maybe".

**Cite the source.** Where a finding's `teach.reference` holds a canonical URL
(language docs, framework docs, the vendor's SQL reference, a rule-pack guide
path), append it to the externalized comment as a bare link. A claim about what
a library or dialect does carries its citation; an unsourced assertion of
framework behavior is the class of finding the claim-verifier exists to catch.

**Direct mode (opt-out, ask once up front).** Some users want the fix stated,
not asked. When chosen, non-blocking comments become imperatives and only the
citation rule above still applies. The report file keeps the direct
wording either way; voice applies to externalized comments only.

**Reviewer mode skips the rest of step 8.** Local markers annotate the author's
working tree, which is not yours. Humanize the findings, write the report, then
go straight to step 9 and triage each finding as a PR comment instead.

Then (author mode) walk the user through every unfixed finding and improvement,
one decision each:

1. **Present** findings via AskUserQuestion — batch up to 4 per call,
   ordered high → medium → low → improvements. Each question shows
   `file:line`, the humanized comment, and the code context; options:
   - **Approve** — insert the marker as shown.
   - **Skip** — no marker; report file marks the row `(skipped)`.
   - **Edit comment** — user supplies their own wording (via "Other"/notes);
     insert the marker with the user's text.
2. **Insert markers for approved findings only** (rules below).

### Marker insertion (author mode, approved findings only)

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

### 9. Posting to a GitHub PR

**Reviewer mode: this is the deliverable**, so offer it rather than waiting to
be asked. The user still confirms before anything posts, and still confirms
each inline comment.
**Author mode:** only when reviewing a PR AND the user asks to post.

Confirm before posting — a PR comment is visible to others. Then post the
review **as the user's own** via `gh pr review` / `gh pr comment`.

Posting comments is the only write reviewer mode performs, and it targets the
PR conversation, never the branch. Do not push a commit to the head branch, and
do not use `gh pr merge`, `gh pr close`, or a review action beyond the
comment/request-changes/approve set below that the user chose.

**Never `--approve` in author mode.** Separation of duties: whoever wrote the
code does not approve it, and in author mode the code is the user's own. Post
comments and request-changes there; approval is a human's to give on someone
else's PR. `--approve` is available in reviewer mode only, and still only when
the user explicitly picks it.

**Voice — post as if the user reviewed it themselves:**
- NO tool/bot attribution. Never write "Automated", "multi-expert review",
  "/deep:review-panel", "generated by", or any agent/panel branding.
- NO pipeline stats in the PR. "Panel raised N → verifier approved M",
  expert names, and coverage counts stay in chat and the report file —
  they never appear in the PR.
- First person, direct, humanized (reuse the step-8 humanized text). Read
  like a colleague's review, not a report.
- Use Markdown `` `code` `` spans for every code token — filenames, paths,
  symbols, functions, config keys, values, commands, error strings (e.g.
  `` `dbt_project.yml` ``, `` `LT02` ``, `` `{% for kpi %}` ``). Use fenced
  ```` ``` ```` blocks for multi-line snippets or suggested diffs. GitHub
  renders Markdown — never post code as bare prose.

**Suggestion blocks are the default vehicle for a concrete fix.** Where the
fix is a rewrite of the commented lines, post a GitHub ```` ```suggestion ````
block instead of describing the change in prose. The author applies it in one
click, and a block that does not compile is visibly wrong in a way prose is
not.

````
```suggestion
    JOIN dim_site USING (site_id)
```
````

- The block must contain the **complete replacement** for every line the
  comment spans, at the correct indentation. Anchor a multi-line fix with
  `--line`/`--start-line` on the review API so the span matches.
- Deleting lines is an empty suggestion block.
- Prose is for the *why* and stays short; the block carries the *what*. A
  hedged question plus a suggestion block is the normal shape for a
  non-blocking finding.
- Skip the block where the fix is not a local line rewrite (add a test,
  restructure a module, change a materialization strategy). Describe those.
- Strip finding machinery from the visible text: no `rule_id`/tag codes,
  no `[expert]` labels, no severity emoji dumps. Lead with the verdict and
  the blocking issues in plain prose.

**Per-finding gate — ask before posting each inline comment.** Walk the
approved findings (batch via AskUserQuestion, up to 4 per call) and for each
show `file:line` + the humanized comment; options: **Post inline** / **Skip**
/ **Edit then post**. Only findings the user confirms get posted. This is
separate from step-8 local markers — a finding can be marked locally but not
posted, or vice versa.

**Structure of the posted review:**
- Summary comment: verdict (merge-ready or not) + the blocking issues as a
  short prose list, in the user's voice.
- Inline comments: one per **confirmed** finding at its `file:line` via
  `gh pr review --comment` / the review API, phrased as the humanized fix.
- Only approved-and-confirmed findings — never the raw panel set. Batch into
  a single `gh pr review` submission where possible, not N separate comments.

The report file and chat still carry the full machinery for the user;
the PR sees only the human-voiced result.

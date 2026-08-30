# Changelog

All notable changes to deep-plan will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [5.9.0] - 2026-08-30

Playbook Stage 1, plus three bugs found while building it. Two of them had been
silently degrading the plugin for months.

### Fixed
- **The implement hooks had been silently inert since April.** Both
  `impl-post-tool-use.py` and `impl-stop.py` looked up a per-session marker in
  `~/.claude/.deep-implement-sessions/` that **nothing in the codebase has ever
  written**. They fell through to "most recently modified marker", every one of
  those pointed at a directory deleted months ago, and the resolver returned
  `None` — which a hook treats as "nothing to do". The practical effect: the
  Stop hook that enforces "you must write `impl-summary.md` before exiting", one
  of the plugin's advertised guarantees, had not fired since 2026-04-07.
  Session binding now lives in `scripts/lib/session_paths.py`, prefers the
  `session_id` on the hook payload, falls back to `.deep-plan-active` (the one
  marker that is actually maintained), and never returns a path that is not on
  disk. `setup-session.py` now writes the per-session marker it always assumed
  existed.
- **`state.json` and `metrics.json` used a fixed temp filename.** `_save` wrote
  `state.json.tmp` then renamed it, which is atomic for one writer and a
  corruption vector for two: the second writer renames a file the first already
  moved away. Temp names are now pid-scoped and cleaned up on failure. Note this
  makes each *write* atomic; it does not make read-modify-write sequences safe,
  which is tracked separately as a precondition for any future concurrency.
- **The test suite wrote into the developer's real `~/.claude`.** It had
  accumulated 1331 session directories, and once pytest recycled a tmp path the
  project slug collided with an existing one, so a "new session" test resumed
  instead and failed. Invisible in CI, where home is always fresh — the worst
  combination, since CI stayed green while the developer saw red. Session roots
  and marker paths are now resolved lazily through `$DEEP_SESSIONS_ROOT` and
  `$DEEP_STATE_HOME`, and an autouse fixture redirects both.
- A sub-minute session reported its wall clock as `N/A` (`if wc` on an int).

### Added
- **`/deep intent`** — Playbook Stage 1. `scripts/lib/intent.py` (schema,
  validation, decision lifecycle), `scripts/lib/vcs.py` (author resolution,
  single-file commit), `scripts/checks/intent.py` (CLI) and
  `references/intent-capture.md`.

  It is a **separate entry point, not a new step**: `/deep plan @spec.md`
  behaves exactly as before. The distinction it protects is that
  `auto-spec-synthesis.md` interprets an ask into a precise engineering goal,
  which is right at plan time and wrong for an intent — the playbook wants the
  originator's own words, so the spec can be traced back to them.

  - Capture is capped at 6 questions and forbidden from re-deriving anything the
    synthesizer already reads from git and the codebase.
  - The draft is then grilled with `Skill(grilling)`, adapted for intents: is
    this the problem or a symptom, who actually asked, what happens if we do
    nothing, is the metric checkable by someone else. Supplied documents are
    grist — quote the passage, ask what it does not say.
  - `decided_by` is mandatory and must come from a real answer. **Auto mode
    leaves `status: draft` and never writes `accepted`**, enforced by test. A
    decision the agent filled in on the user's behalf looks like an audit trail
    without being one.
  - Terminal statuses are terminal; re-deciding is refused in favour of
    superseding.
  - Publishing into the repo is opt-in (`--publish`, `--commit`), stages exactly
    one file, and never pushes. A test asserts an unrelated staged file is not
    swept into the commit.
  - `source: agent` exists from day one so Stage 6 can raise intents from
    breached control bands without a schema change.
- **`--from-intent`** on `/deep plan`. Deliberately **not** an express path:
  unlike `--from-prd`, an intent carries no engineering content by design, so
  research and the interview still run. It is recorded so the spec can be traced
  back to it.

### Decided
- **Git worktree parallelism: not building it**, neither dispatch nor an
  advisory. Two independent reviews measured a 1.67x speedup with three workers
  on 32 real plans, found that 60% of section files lack a parseable `File:`
  line (so disjointness cannot be computed), and found that `/deep implement`
  has no `--section` flag — meaning an advisory's printed commands would point
  three instances at the same section. The original audit's claim that
  `claude -p --worktree` cannot compose was wrong and is corrected in the record;
  it does not change the verdict. Reports under `sessions/sdlc-audit/`.

## [5.8.0] - 2026-08-30

Playbook Stage 3: the plugin can now block. This is the shared prerequisite for
the Test and Deploy stages, both of which need a `PreToolUse` layer to hang off.

### Added
- **`PreToolUse` guardrails.** `scripts/lib/guard.py` (pure decision logic,
  stdlib only) behind `scripts/hooks/guard-pre-tool-use.py` (thin adapter), wired
  for `Write|Edit|MultiEdit|NotebookEdit`. Credential patterns `deny`; paths a
  repo declares protected `ask`. Config merges plugin defaults ← planning dir ←
  `<repo>/.claude/deep-guard.json` ← `$DEEP_GUARD_CONFIG`, with `"inherit": false`
  to reset. `DEEP_GUARD=off` is the session kill switch.
- **`references/guardrails.md`** documenting the schema, the `ask`-over-`deny`
  policy, glob semantics, the latency budget and what is deliberately not covered.

The design is shaped entirely around not being the feature people rip out:

- **Ships blocking almost nothing.** `protected_paths` and `format_on_edit` are
  empty in the baseline; protected paths are opt-in per repo. Only credentials
  are universal, and every pattern is a vendor-prefixed high-entropy token or a
  structural marker. There is deliberately no generic `password\s*=` rule —
  that class of regex is the biggest source of false-positive frustration, and
  `bandit`/`semgrep` already cover it at Phase 6.
- **`ask`, not `deny`, for paths.** `deny` is reserved for credentials, where no
  override is legitimate. Secrets outrank protected paths when a file is both.
- **Fails open everywhere.** Malformed config layer, bad regex, unparseable
  payload, unexpected exception — all exit 0 silently. The guard must never be
  the reason an edit fails.
- **Every block message names the rule id, the config file and both escape
  hatches.** A block that does not say how to unblock is a bad block.
- **Fast on the hot path.** `python3`, not `uv run` (150-300 ms of resolver
  overhead). Config memoised on `(path, mtime)`, regexes compiled once, scan
  capped at 256 KB, `"timeout": 5`. Measured: 0.1 ms at 1 KB, 1.8 ms at 50 KB,
  9.4 ms at the cap, against a ~25-35 ms interpreter start that the plugin
  already pays on every tool call.

### Fixed
- **`**/*.md` did not match a top-level `README.md`.** `fnmatch` requires the
  separator, so a leading `**/` silently failed to mean "at any depth, including
  none" — which would have exempted nested docs from the secret scan while
  blocking top-level ones. Glob matching now handles both the leading `**/` and
  trailing `/**` cases people expect from gitignore-style patterns.

### Removed
- **The two dead `PreToolUse` scripts.** `scripts/hooks/pre-tool-use.py` and
  `scripts/hooks/impl-pre-tool-use.py` were wired to no hook event, always
  allowed, and emitted the deprecated `{"decision": "allow"}` envelope. Their one
  piece of institutional memory — that stray stdout from a hook breaks Claude
  Code's hook parser — is preserved in `CLAUDE.md` and the new hook's docstring.

## [5.7.0] - 2026-08-30

First wave of alignment with Anthropic's
[AI-Native SDLC Playbook](https://claude.com/blog/the-ai-native-sdlc-playbook).
This release is the foundation the later stages need: continuous integration,
live metrics, and two governance holes closed. Full per-stage audits live in
`~/.claude/marketplace/deep-plan-enhanced/sessions/sdlc-audit/`.

### Fixed
- **The agent could approve its own code.** `code-review` step 9 permitted
  `gh pr review --approve` as a user-chosen action in *author* mode, where the
  code under review is the user's own. The playbook's separation-of-duties rule
  is that whoever writes the code does not approve it. `--approve` is now
  reviewer-mode only; author mode posts comments and request-changes.
- **`active_packs` was never actually resolved, so the reviewer always fell back
  to `["core"]`.** `implement-protocol.md` and `code-reviewer.md` both claimed
  the active packs were "frozen in the blueprint at plan time", but nothing ever
  wrote them — the Phase 6 snippet imported `resolve_packs`/`detect_signals` and
  then referenced undefined variables. Every non-core pack was dead on arrival,
  including the `warehouse` pack shipped in 5.5.0 and repaired in 5.6.1. Phase 6
  now resolves packs itself and reports the resolved set; a dbt or frontend
  target landing on `core` alone is a routing bug, not a quiet default.
- **`MetricsCollector` had zero call sites.** It was tested dead code: a
  repo-wide grep found it only in `deepstate.py` and `test_metrics.py`. Every
  measurement the playbook asks for was blocked behind it. `setup-session.py`
  now opens the metrics file for each new session, best-effort and non-fatal.
- **A sub-minute session reported its wall clock as `N/A`.**
  `format_dashboard` tested `if wc`, so a run that finalized in under a second
  was indistinguishable from one that never finalized.

### Added
- **CI, for the first time.** `.github/workflows/tests.yml` runs the 805-test
  suite on Python 3.11, 3.12 and 3.13 for every push and pull request. 46 test
  files had been running only when someone remembered to. `ruff` runs as a
  second, advisory job — there are ~243 pre-existing violations, so it reports
  without blocking until they are cleared.
- **`scripts/checks/session-metrics.py`** — `record`, `increment`, `finalize`
  and `report` subcommands, so a run can reach its own metrics file.
- **Issue timestamps.** `DeepStateTracker` issues now carry `created_at` and
  `closed_at`. Nothing could measure time-to-anything without them.
- **`CLAUDE.md` is now a real file.** The repo that enforces ruff, mypy
  `--strict`, bandit and a documented complexity budget on everyone else had
  three literal `_Add your…_` placeholders. Documents build/test commands, the
  directory map, the session-state invariant, and the hook conventions
  (`python3` not `uv run`, fail open, never print stray stdout).
- **README: an SDLC alignment section** mapping each playbook stage to its
  `/deep` surface with an honest status, plus the deliberate non-goals — no
  managed settings, no deployer, no chat on-call.

## [5.6.1] - 2026-08-24

### Fixed
- **The `warehouse` pack was invisible to the core reviewer.** `code-reviewer.md`
  listed active rule families ending at `supply`/`iac`/`llm` with no `warehouse`
  entry, and named only python/typescript/go in its reference table. Since its
  Rule 2 drops findings that map to no active family, `/deep implement` Phase 5
  silently reviewed dbt code against nothing, even though `pack_router` correctly
  activated the pack. Adds the `SQL-*`/`DBT-*` family, the `lang/sql.md` trigger row,
  SQL to the description, and `sqlfluff`/`dbt parse`/`dbt compile` to the tool step.
- **Warehouse rule ids were being put in the wrong JSON field.** `data-eng-reviewer`
  was told to cite pack rule ids in `tag` "in place of a `DE-*` tag", but the
  orchestrator groups specialist findings by a fixed tag whitelist, so a `SQL-001`
  finding matched no group and would not render. Rule ids now travel in `rule_id`
  alongside the expert's own `DE-*` tag, which is what `code-reviewer` already did.
- **The core reviewer and `data-eng-reviewer` both enforced every warehouse rule**
  on the same lines. The split is now stated: core does the mechanical rule-id pass,
  the specialist owns findings needing grain, upstream timing, or cross-model context.
- **Eval cases still asserted the old in-repo report path.** Three cases in
  `code-review-cases.yaml` checked for `.reviews/code-review-*.md`, which 5.6.0
  removed, so the suite would have pulled the regression back in. Updated to the
  `~/.claude/code-reviews/` path, plus a new `no_repo_artifacts` check asserting a
  review leaves no untracked file in the reviewed repo.

## [5.6.0] - 2026-08-24

### Added
- **`code-review` resolves authorship and runs read-only on other people's code.**
  A new step 1b compares `gh api user` and the PR author (or the diff's commit
  authors) against `git config user.email` to set `review_mode`. On the user's own
  work nothing changes. On someone else's branch or PR the skill becomes a
  pre-review for posting to GitHub: no fixes, no `CODECHANGE`/`RECOMMENDATION`
  markers, no staging, committing, or pushing, and no write-mode formatters. Gates
  still run in check-only form. Ambiguous authorship asks rather than assuming, since
  an unwanted edit to a colleague's branch costs far more than a skipped fix.
- **PR posting becomes the deliverable in reviewer mode**, offered rather than
  waiting to be asked, with per-comment confirmation unchanged. Line-level fixes
  travel as suggestion blocks, which is how a change reaches an author without
  touching their branch. Posting is the only write reviewer mode performs, and it
  targets the PR conversation; merging, closing, and pushing to the head branch are
  out of scope.
- **Reports record `mode` and `code_author`**, so a report says whose code was
  reviewed and under which rules.

### Changed
- **Context auto-discovery searches what is actually connected.** It now checks the
  live tool list rather than assuming a server exists, extracts the ticket key from
  the branch name (more reliable than commit messages), reads prior review rounds on
  the PR so the panel does not re-raise points a human already settled, and follows
  linked wiki/SharePoint/roadmap documents through the Confluence, M365, and Airfocus
  MCPs. Explicit links only, with the search bounded, since every round-trip is
  latency before the panel starts. The `review_context` block now records which
  sources answered, which were unavailable, and which were skipped, so a report can
  distinguish "no spec exists" from "the wiki was not connected".
- **Review reports moved out of the reviewed repo.** They were written to
  `.reviews/` at the repo root, so every review left an untracked file to ignore
  or accidentally commit, and the skill had to check `.gitignore` each run. Reports
  now go to `~/.claude/code-reviews/<owner>__<repo>/<YYYY-MM-DD>-<pr-N|branch>.md`,
  keyed by owner and repo so same-named repos across orgs do not collide, and dated
  so an old review is findable without knowing a session id. `$DEEP_REVIEWS_DIR`
  overrides the root. Nothing this skill writes lands in the repo any more, and the
  `.gitignore` step is gone.

## [5.5.0] - 2026-08-24

### Added
- **`warehouse` quality pack.** The pack system had no SQL or dbt coverage at all:
  no pack declared a `.sql` glob, and nothing under `references/quality/` mentioned
  dbt, Snowflake, or jinja. `references/quality/warehouse/` adds `SQL-001`…`SQL-012`
  (published-interface discipline, `NOT IN` against nullable subqueries, pass-through
  CTEs, boolean round-trips, `GROUP BY` ordinals, redundant wrappers) and
  `DBT-001`…`DBT-014` (`ref()`/layer discipline, `is_incremental()` guards,
  `unique_key` ordering for partition pruning, materialization justification, schema
  tests and column docs, idempotent warehouse DDL).
- **`references/quality/lang/sql.md`.** The fourth language guide alongside python,
  typescript, and go, which `review-panel-protocol.md` already told experts to consult.
  Holds the rewrite for every warehouse rule plus a Dialect section: Snowflake is the
  assumed default, with the BigQuery/Postgres/DuckDB divergences called out.
- **SQL and dbt signals in `pack_router`.** `.sql` maps to a `sql` language, a
  `dbt_project.yml` marks the target as a `data` project, and `dbt`/`snowflake`/
  `bigquery` spec keywords infer the `data` project and `data-model` task types.

### Changed
- **`data-eng-reviewer` defers to the pack.** Cites `SQL-*`/`DBT-*` rule ids instead of
  restating them, and gains what no rule id can state generically: lookback windows
  against real upstream arrival lag (`DE-LATEBOUND`), contract drift on columns read
  positionally or by wildcard (`DE-CONTRACT`), and mandatory dialect identification
  before any syntax finding.
- **`claim-verifier` covers two more claim classes.** SQL-dialect behavior (engine
  semantics, not general SQL) and version/deprecation/"newer API exists" currency
  claims, the two places a training cutoff misleads most. Its brief now states the
  five triggers exhaustively, so the panel's only network stage is not spawned
  defensively.
- **Review voice.** Severity sets the register: blocking findings stay direct, while
  non-blocking findings and improvements are phrased as questions carrying their own
  reasoning, so an author can answer with a constraint the reviewer did not know.
  Findings carrying a `teach.reference` cite it. GitHub suggestion blocks are now the
  default vehicle for a concrete line-level fix on a PR. The old opt-in Socratic mode
  is replaced by an opt-out direct mode.
- **`code-review` routes dbt schema files.** The `data-eng-reviewer` spawn row now
  names `dbt_project.yml`, schema `.yml` under `models/`, `macros/`, `seeds/`, and
  `snapshots/`, which previously matched no expert.
- **Humanizer default voice profile de-personalized.** The named personal profile is
  now a generic Default Voice Profile; the style rules are unchanged.

### Fixed
- **`pack_router` leaked the enclosing repo's diff into every target.** `_git_changed`
  ran `git diff --name-only HEAD` from the target directory, which reports the whole
  repository's changes whenever the target is a subdirectory. Adding `--relative -- .`
  confines it to the target, fixing pack over-activation (a dirty `agents/` directory
  activated the `llm` pack on unrelated targets) and making subdirectory targets
  resolve honestly. Regression test added.

## [5.4.1] - 2026-08-11

### Added
- **`writing-for-agents` in the mattpocock install set.** `scripts/checks/install-mattpocock-skills.py`
  now installs `skills/productivity/writing-for-agents/` alongside `grilling` and `handoff`.
  It is the upstream reference for authoring documents an agent consumes (skills,
  `AGENTS.md`, `CLAUDE.md`), covering context pointers, the information hierarchy, and progressive
  disclosure, the vocabulary the plugin's `no-op-remover` and `skill-reviewer` already assume.
  `README.md`, `NOTICE`, and `docs/skills-bundled.md` updated to match.

### Removed
- **`grill-me` from the install set.** Upstream reduced it to a stub with
  `disable-model-invocation: true` and a one-line body, "Run a `/grilling` session", so
  installing it only added a second name for a skill already installed. `/grilling` is the
  entry point.
- **`write-a-skill` from the opportunistic global-skill tables** in `README.md` and
  `docs/skills-bundled.md`. Upstream deleted the skill; `writing-for-agents` covers the same
  ground and is now installed directly.

### Fixed
- **Stale `Skill(grill-me)` references.** `docs/quality-pipeline-plan.md` (5 places) and
  `references/implement-protocol.md` now name `Skill(grilling)`, which is what the protocols
  have actually invoked since 5.0.

## [5.4.0] - 2026-08-09

Nominal-style detection and a measurable audit for the `humanizer` skill (2.5.1 → 2.6.0).

### Added
- **Four patterns (#30-#33).** `Verbless Nominal Decks and Tag Lines` covers dropping
  the copula entirely, which #8 missed because it only caught replacing `is` with
  something ornate. `Balanced Doublets and Numeral Anaphora` covers the two-part case
  of #10, which survives editing because it reads as elegant. `Bold Label Openers`
  covers paragraphs that all begin `**Position.**` or `**Read:**`. `Prose-to-Table
  Reflex` covers tables used to signal rigor where two sentences would do.
- **`Non-Prose Surfaces` section.** Per-surface rules for headings, card headers, chart
  labels, table cells, bullets and commit messages, because "restore the finite verb"
  is wrong advice for a chart label. Fragments are a defect in body prose and correct
  in a bar tag.
- **`Mechanical Scan` section.** Nine greppable patterns plus four counted metrics
  (mean sentence length, sentence-length standard deviation, nominalization rate,
  verbless-line share), run before editing and again after. Flat deviation after a
  rewrite means the edit was cosmetic. This replaces relying solely on the model's
  own judgment of its own prose.
- **`Why the tells cluster` section.** Grounds the pattern list in Reinhart et al.,
  PNAS 122(8), 2025, which measured instruction-tuned models as noun-heavy and
  information-dense even when prompted for informal registers. Most of the patterns
  are symptoms of that one habit.

### Changed
- `Your Task` and `Process` now run scan, edit, audit, rescan, and both check which
  surface is being edited before treating fragments as defects.
- `Output Format` reports scan numbers before and after.
- Patterns #8 and #10 cross-reference #30 and #31.
- `Reference` cites the PNAS study alongside the Wikipedia guide.

## [5.3.0] - 2026-07-20

### Added
- **`no-op-remover` skill.** Finds and removes no-ops — instructions a model
  already obeys by default — from instruction/prompt files (`SKILL.md`, agent
  definitions, `CLAUDE.md`/`AGENTS.md`, prompt templates, docs). Resolves scope
  (file / directory / repo / diff, or asks when invoked bare), detects no-ops
  sentence by sentence, and applies delete/strengthen fixes only on user
  approval. Based on Matt Pocock's no-op test.

## [5.2.0] - 2026-07-17

World-class, factual, teaching-oriented upgrade to the `code-review` skill.

### Changed
- **Exhaustive review is now the default.** Removed the per-expert issue and
  improvement caps and the triage-suppression language ("five findings beat
  twenty nitpicks", "style police"). Every real standards deviation is
  surfaced at its true severity — nits included, as `low`/non-blocking. The
  report renders **blocking-first**, splitting Blocking (`high`) from
  Non-blocking so a long nit list can never bury a real bug.
- **Praise is uncapped** — reinforcement of good patterns teaches as much as
  flagging bad ones.

### Added
- **Factual gate.** Every finding must quote the verbatim offending code and
  carry a falsifiable prediction; a new `evidence` field captures tool output.
  The `review-verifier` gains a gate-0 that rejects any finding whose quoted
  snippet it cannot find, and a check-8 that downgrades unverified
  framework/behavior claims lacking tool output, a doc URL, or a claim-verifier
  verdict.
- **Tools where needed.** Panel experts now have an explicit mandate to run the
  language linter/type/security tools, `grep`, and tests to *confirm* findings
  before reporting ("prefer executing to asserting"). Web verification stays
  centralized in an expanded `claim-verifier` (single pass, claim batching).
- **Teaching layer.** Every issue carries a `teach` block — `principle`,
  `why`, `pattern` (the general form to internalize), optional `reference`.
  A new `## Learning summary` report section clusters recurring themes, points
  to concrete study, and surfaces strengths. Optional **Socratic mode** phrases
  non-blocking findings as guiding questions.
- **Standards taxonomy.** OWASP-2021 + CWE-Top-25 crosswalk on every `SEC-*`
  rule, plus new `SEC-011` SSRF (CWE-918), `SEC-012` unsafe deserialization
  (CWE-502), `SEC-013` path traversal (CWE-22), `SEC-014` open redirect
  (CWE-601). Externalized comments adopt **Conventional Comments** labels
  (issue/suggestion/nitpick/praise/question + blocking/non-blocking).
- **Diff-size guardrail** in the scope step: diffs over ~400 LOC trigger a
  warning and an offer to split or run paced passes (SmartBear defect-detection
  threshold).
- **Mandatory detective sweep** in the shared panel protocol — data-flow,
  invariants, hostile inputs, error paths, concurrency/TOCTOU, arithmetic —
  now required of every expert, not just `logic`.
- **`PROMPT-NOOP` check** in the `prompt-reviewer` — flags prompt instructions
  the model already obeys by default (the no-op test), hunted sentence by
  sentence, with delete-don't-trim fixes.
- Eval cases and rubric items for the large-diff guardrail, the learning
  summary, exhaustive blocking-first output, teach blocks, OWASP/CWE citation,
  and Conventional Comment labels.

## [5.1.0] - 2026-07-17

Multi-expert code review, grounded in "Don't Ship Skills Without Evals".

### Added
- **Multi-expert review panel** for the `code-review` skill. The diff routes
  to specialist reviewer subagents — `logic`, `architecture`, `ml`, `stats`,
  `mlops`, `data-eng`, `prompt`, and `skill` — alongside the core
  `code-reviewer`. All share one contract (`references/review-panel-protocol.md`)
  with a coverage contract (every changed file reviewed or skipped-with-reason)
  and a method-appropriateness dimension (`*-METHOD`).
- **`skill-reviewer` agent** applying the Confluence rubric (description-as-
  trigger, lean progressive-disclosure structure, directives over essays,
  negative cases, no-ops, and eval coverage) to SKILL.md / agent files.
- **Verification chain**: `claim-verifier` web-checks framework/statistical
  claims against current docs; `review-verifier` re-reads the code, kills
  phantom findings, dedupes across experts, and audits panel coverage — its
  approved set is the only one that reaches the user.
- **Advisory `improvements` channel** — pack-independent better-way
  suggestions (logic, architecture, idiomatic/advanced techniques).
- **`.reviews/` report file** with frontmatter, findings table (file, line,
  rule/tag, expert), improvements, gates, and dead code.
- **Humanized triage**: each finding's marker text is humanized, presented for
  approve/skip/edit, and only approved comments are inserted as inline
  `CODECHANGE`/`RECOMMENDATION` markers via the new
  `scripts/checks/apply-review-markers.py` + `scripts/lib/comment_markers.py`
  (deterministic bottom-up, language-aware, idempotent).
- **Structural eval harness** — `tests/evals/code-review-cases.yaml` (golden /
  negative / edge cases) + `tests/test_code_review_evals.py` +
  `tests/test_comment_markers.py`, and `tests/evals/README.md` documenting the
  quarterly ablation procedure. `pyyaml` added to dev deps.

### Fixed
- **SessionStart hooks** now run with `uv run --no-project`, so a session
  started inside a uv project with an unresolvable `pyproject.toml` no longer
  fails hook execution with "No solution found when resolving dependencies".
- `pyproject.toml` version corrected from a stale `3.0.0` to match the plugin.

## [5.0.0] - 2026-07-17

**Breaking:** plugin renamed `deep-plan-enhanced` → `deep`;
`skills/mp-zoom-out/` removed. Reinstall required:
`claude plugin uninstall deep-plan-enhanced@kbichave-plugins && claude
plugin install deep@kbichave-skills`. The GitHub repo was also renamed
`kbichave/deep-plan-enhanced` → `kbichave/skills` and the marketplace
`kbichave-plugins` → `kbichave-skills` (old repo URL redirects).

### Changed
- **Plugin name is now `deep`** — bundled skills surface as `deep:deep`,
  `deep:code-review`, `deep:humanizer`. One namespace, no vestigial
  prefixes.
- **No vendored mattpocock skills.** New one-time setup script
  `scripts/checks/install-mattpocock-skills.py` installs `grilling`,
  `grill-me`, and `handoff` verbatim from
  [mattpocock/skills](https://github.com/mattpocock/skills) into
  `~/.claude/skills/` under upstream names, with provenance + hashes
  recorded in `skills-lock.json`. Re-run to update.

### Removed
- **`skills/mp-zoom-out/`** — upstream deleted `zoom-out`; the vendored
  rename is dropped rather than maintained as an orphan fork.

## [4.1.0] - 2026-07-17

### Added
- **`skills/humanizer/`** — user's humanizer skill (v2.5.1) moved into the
  plugin as the single source; global `~/.claude/skills/humanizer` archived.
  `skill-router` already routes prose outputs to it.

## [4.0.0] - 2026-07-17

**Breaking:** `agents/python-code-reviewer.md` deleted (merged into
`code-reviewer`); six vendored mattpocock skills removed in favor of
globally installed equivalents.

### Changed — Unified code reviewer (merged + enriched)
- **`agents/code-reviewer.md` is now the sole code-review agent.**
  `agents/python-code-reviewer.md` deleted; its 7 criteria live on as core-pack
  rule families + `references/quality/lang/python.md`. `--quality=legacy`
  routes to the merged agent with `active_packs=["core"]`,
  `languages=["python"]`.
- **Four-phase review workflow** (context → high-level → line-by-line →
  summary), **five review dimensions → rule-family map**, optional `praise`
  output, and constructive-feedback rules — distilled from
  [awesome-skills/code-review-skill](https://github.com/awesome-skills/code-review-skill)
  (MIT, see NOTICE).
- **Claim verification**: the reviewer gained WebSearch/WebFetch and must
  verify uncertain framework-behavior claims against current docs (cite URL)
  or drop/downgrade the finding.
- **Review context gathering** (implement-protocol Phase 5a): orchestrator
  asks the user provide / skip / auto-discover; auto-discovery pulls ticket +
  PR + spec context via available MCPs and passes `review_context` to the
  reviewer.

### Added — Review reference library + standalone skill
- Vendored (MIT, rule-mapping headers added): 7 cross-cutting guides under
  `references/quality/cross-cutting/` (SQL injection, XSS, N+1, error
  handling, async/concurrency, common bugs, universal quality) and 3 language
  guides under `references/quality/lang/` (python, typescript, go).
- `scripts/pr_analyzer.py` + `tests/test_pr_analyzer.py` — diff triage for
  large reviews (40 tests).
- **`skills/code-review/`** — standalone user-invocable review skill: scope →
  context gathering (incl. MCP auto-discovery) → pack resolution → reviewer
  agent → claim verification → human-readable report.

### Removed — mattpocock skill dedupe
- Six vendored skills removed in favor of globally installed equivalents:
  `grill-me`→`grilling`, `tdd`→`tdd`, `ubiquitous-language`→`domain-modeling`,
  `improve-codebase-architecture`→`codebase-design`, `obsidian-vault`,
  `write-a-skill`. Load-bearing content inlined first
  (`references/architecture-language.md`). `skills/zoom-out` renamed
  `skills/mp-zoom-out` to mark provenance. See `docs/skills-bundled.md`.

### Added — Quality pipeline (conditional rule packs, multi-language)
- **Rule packs** under `references/quality/`: always-on `core` (ENG/SEC/TEST/ERR)
  plus triggered `service`, `delivery`, `perf`, `frontend`, `library`, `supply`,
  `iac`, `llm`. Each pack has `applies_when` frontmatter + family sub-files.
- **`scripts/lib/pack_router.py`** — resolves which packs apply to the *target*
  repo from detected languages / project type / changed globs / task type
  (spec-driven for greenfield). Languages act as an eligibility filter; packs
  activate on project-type/glob/task. Stdlib-only frontmatter parser.
- **`scripts/lib/quality_gate.py`** — composes the implement Phase 6 gate from
  `active packs × languages` via `lint/{python,ts,go}/adapter.json` (per-language
  thresholds; Go relaxed). `--quality=legacy` restores the fixed gate.
- **`agents/code-reviewer.md`** — multi-language, pack-scoped reviewer; rule-ID
  tagged findings, three-layer report-only dead-code. `python-code-reviewer`
  retained for back-compat.
- **`Skill(grill-me)`** now invoked internally by the plan/discovery interview
  and the implement confidence gate (not user-run).
- **Discovery** emits a mandatory audit topic per active quality family
  (`audit-topic-enumeration` Step 3.5).
- **`scripts/lib/quality_artifacts.py`** — pack fingerprint + freshness check;
  deferred (flag-gated) Qodo `best_practices.md` export.
- Tests: `test_pack_router`, `test_quality_gate`, `test_quality_artifacts`.
- Rollout: new always-on SEC/ENG BLOCKs ship as WARN for one release. Plan:
  `docs/quality-pipeline-plan.md`.
- Reimplements (does not vendor) rubrics from `levnikolaevich/claude-code-skills`
  (MIT) — see `NOTICE`.

## [2.0.2] - 2026-05-20

### Added
- **Auto-install of statusLine.** New SessionStart hook `scripts/hooks/auto-install-statusline.py` runs `install-statusline.py` on first session if `~/.claude/settings.json` lacks the deep marker. Idempotent on subsequent sessions. Emits a one-line `additionalContext` notice when it actually installs.
- Opt-out: `export DEEP_DISABLE_STATUSLINE_INSTALL=1`.
- Tests: `tests/test_auto_install_statusline.py` covers already-installed skip, env-var opt-out, installer-failure silence, missing-installer silence, notice emission.

### Changed
- `hooks/hooks.json` — added the auto-install hook alongside `capture-session-id.py` under SessionStart.

## [2.0.1] - 2026-05-20

### Added
- **Context-usage tracker.** Two-layer monitor mirroring GSD's pattern:
  - `scripts/hooks/deep-statusline.py` — Claude Code `statusLine` hook. Renders `deep:{mode} {step} ▰▰▰▱▱▱▱▱▱▱ {used_pct}% [{model}]` or `ctx …` fallback. Writes `/tmp/deep-ctx-{session_id}.json` bridge file.
  - `scripts/hooks/deep-context-monitor.py` — `PostToolUse` hook. Reads bridge, injects `hookSpecificOutput.additionalContext` warnings at WARNING (≥65% used) and CRITICAL (≥75% used). 5-tool-call debounce; escalation bypasses.
  - `scripts/lib/context_metrics.py` — model fallback table (Opus 4.7/Sonnet 4.6 = 1M, Haiku 4.5 = 200k), threshold classifier, debounce state, atomic bridge IO. Stdlib only.
  - `scripts/checks/install-statusline.py` — safe merger for `~/.claude/settings.json`. Backs up existing entry; supports `--check` and `--uninstall`.
  - `docs/context-monitor.md` — install, thresholds, troubleshooting, model-limit override.
- Tests: 79 new pytest cases across `tests/test_context_metrics.py`, `tests/test_deep_statusline.py`, `tests/test_deep_context_monitor.py`, `tests/test_install_statusline.py`.

### Changed
- `hooks/hooks.json` — added second `PostToolUse` entry (no matcher) for `deep-context-monitor.py`.

### Notes
- Plugins cannot register `statusLine` in `hooks/hooks.json` or plugin `settings.json` per Claude Code spec. Users run `uv run scripts/checks/install-statusline.py` once to enable the bar.
- Subagent token usage is not visible in the parent transcript; bridge is per top-level session only. Documented limitation, same as GSD.

## [2.0.0] - 2026-05-20

### Breaking
- **Removed `mempalace` dependency and integration.** All MemPalace MCP wiring, `MemPalaceBackend`, `index_session_in_mempalace`, and the experience-protocol reference are gone. Research topics persist via `FlatFileBackend` only. Migration: existing flat-file artifacts (`research-topics.yaml`, `findings/`) are unchanged. Anyone using mempalace for cross-session intelligence must roll their own.
- **Removed `/deep plan-all` mode.** Multi-phase orchestration is now `auto`-only. `--workflow plan-all` rejected by `setup-session.py`. Migration: use `/deep auto @phases/` instead — it does plan-then-implement per phase in dependency order.

### Added — Tier 1 (matt-style restructure)
- **SKILL.md trimmed** from 342 → 175 lines. Branching question table at top with load-bearing step per mode (discovery: topic enumeration; plan: interview; implement: confidence gate). Detailed workflows live under `references/`.
- **New references**: `implement-protocol.md` (Phase 1-10 per-section discipline), `resume.md` (post-compaction recovery), `INDEX.md` (navigation hub).

### Added — Tier 2 (gsd-style features)
- **Discovery depth flag** — `/deep discovery --depth=quick|standard|deep`. `quick` pre-closes deep-research, coverage-validation, auto-gaps, build-vs-buy, external-review for a 5-10 min audit. `deep` appends a cross-verify pass to research steps.
- **Express paths** — `/deep plan --from-prd @prd.md` or `--from-adr @adrs/` skips research + interview. `write-spec` and `generate-plan` read the structured input directly. Generalizes the ad-hoc `--no-reframe` flag.
- **Coverage gate** — new `scripts/checks/check-coverage.py` parses spec requirements/capabilities and asserts each maps to a section in `sections/index.md`. Blocking — exit 1 with `missing` JSON list when items dropped.
- **Stall detection** — new `scripts/lib/stall_detector.py` for the external-review revision loop. Flags consecutive revisions with <10% diff or recurring findings. Interactive: escalate to user. Auto: accept-with-caveat. Hard cap of 3 iterations regardless.

### Added — Tier 3 (matt-style discipline)
- **Falsifiable predictions in reviews** — `agents/python-code-reviewer.md` adds required `prediction` field per issue. `agents/opus-plan-reviewer.md` requires `**Prediction:**` line on every Critical/Major finding. Format: "After fix, <X> will <Y>."
- **Throwaway scratch artifacts** — new `scripts/lib/scratch.py`. Research notes that informed but should not survive the session land under `{planning_dir}/scratch/` with a `THROWAWAY:` header. Stop hook sweeps `mode-complete` scratch at exit.
- **Post-mortem hand-off** — Stop hook now requires `impl-summary.md` to answer "what would have prevented the rework?" Architectural answer → suggest `Skill(improve-codebase-architecture)`. Spec-clarity answer → log `## Spec gaps observed`. None → say so.

### Notes
- **572 tests pass** (up from 437). New test modules: `test_check_coverage.py` (16), `test_stall_detector.py` (14), `test_scratch.py` (17). Existing modules pruned to remove mempalace + plan-all tests.
- `pyproject.toml` synced to plugin version (was 1.5.0, now 2.0.0).
- Plugin restart / reinstall recommended after upgrade.

## [1.8.0] - 2026-04-27

### Added
- **Bundled Matt Pocock skills** — vendored seven skills from `mattpocock/skills` (MIT) under `skills/`: `grill-me`, `tdd`, `ubiquitous-language`, `improve-codebase-architecture`, `obsidian-vault`, `write-a-skill`, `zoom-out`. Attribution in `NOTICE`.
- **Knowledge vault** — `/deep` now persists glossary terms, ADRs, and curated findings to an Obsidian-flavored vault. Vault path resolves from `$DEEP_OBSIDIAN_VAULT`, then `~/Obsidian/deep-plan/`, otherwise the first `/deep` run prompts once. New `agents/vault-curator.md` decides per-artifact whether to save or skip. Helpers in `scripts/lib/vault.py`.
- **Ubiquitous-language glossary** — always-on audit topic in `/deep discovery`. Extraction + diff-merge in `scripts/lib/glossary.py`; cross-project promotion supported.
- **Architecture audit** — `scripts/lib/architecture_audit.py` detects shallow modules, hypothetical seams, and scattered knowledge. `/deep plan` surfaces a single `AskUserQuestion` to fold a deepening into the plan; `/deep implement` warns at section overlap.
- **Skill-aware routing** — `/deep` consults `agents/skill-router.md` between phases to invoke or surface other installed skills (e.g., `claude-api`, `code-review`, `simplify`). Side-effect skills demoted to MEDIUM. Mute list at `~/.claude/deep/muted-skills.json`. Helper: `scripts/lib/skills_registry.py`.
- New documentation: [`docs/vault.md`](docs/vault.md), [`docs/skills-bundled.md`](docs/skills-bundled.md), [`docs/skill-routing.md`](docs/skill-routing.md).

### Changed
- **Interview style** — sequential decision-tree walk with recommended answers (`grill-me` pattern) is now the default for `/deep plan` and `/deep discovery` interviews. `references/interview-protocol.md` and `references/audit-interview-protocol.md` updated.
- **TDD shape** — `references/coding-standards.md` now codifies the tracer-bullet rule from `skills/tdd/SKILL.md` and the tiniest-possible-commit rule from `skills/request-refactor-plan`. `agents/section-writer.md` and `agents/opus-plan-reviewer.md` cite the same rules.
- **Plan writing** — `references/plan-writing.md` now requires a module-design step before sections, citing `skills/improve-codebase-architecture/SKILL.md` and `skills/tdd/deep-modules.md`.
- **Audit topic enumeration** — `references/audit-topic-enumeration.md` adds `ubiquitous-language` as an always-on category.

### Notes
- Existing tests remain green. Four new test modules: `tests/test_vault.py`, `tests/test_glossary.py`, `tests/test_architecture_audit.py`, `tests/test_skills_registry.py` (29 tests, all passing).
- All new scripts are stdlib-only.

## [0.3.2] - 2026-02-28

### Fixed
- **Plugin root discovery** — SessionStart hook now injects `DEEP_PLUGIN_ROOT` into Claude's context via `additionalContext`, eliminating slow `find` commands for script discovery. Falls back to filename-based search that works with both hyphen and underscore directory naming (fixes marketplace install path mismatch). ([piercelamb/deep-project#3](https://github.com/piercelamb/deep-project/issues/3))

## [0.3.1] - 2026-02-11

### Fixed
- **Section file race condition** — SubagentStop hook now waits for transcript JSONL to finish writing before reading it. Previously, 64% of section files contained garbage because Claude Code fires the hook before the final transcript entries are flushed to disk. The fix polls file size stability (200ms threshold) before reading, with a 5s timeout fallback.

## [0.3.0] - 2026-01-30

### Changed
- **Unified session ID** - Changed `DEEP_PLAN_SESSION_ID` to shared `DEEP_SESSION_ID`
- **Normalized env var** - Changed `CLAUDE_SESSION_ID` to `DEEP_SESSION_ID` in env file writes and all scripts
- SessionStart hook now checks if `DEEP_SESSION_ID` already matches before outputting
- Prevents duplicate output when multiple deep-* plugins run together

## [0.2.0] - 2026-01-30

### Added
- **Parallel section writing** - Sections now written by concurrent `section-writer` subagents (batch size: 7)
- **No external LLMs mode** - Can run with Opus subagent for plan review instead of Gemini/OpenAI
- **SessionStart hook** - Captures session_id reliably via `additionalContext`
- **SubagentStop hook** - Automatically writes section files from subagent output
- New agent definitions: `section-writer.md`, `opus-plan-reviewer.md`
- Batch task generation script: `scripts/checks/generate-batch-tasks.py`
- Transcript parsing utilities: `scripts/lib/transcript_parser.py`, `scripts/lib/transcript_validator.py`
- New reference document: `plan-writing.md`

### Changed
- **TODOs to Tasks** - Migrated to native Claude Code Tasks with dependency tracking
- Tasks written directly to `~/.claude/tasks/` for deterministic state
- Section subagents no longer need Write tool access (more secure via hook capture)
- Updated `section-splitting.md` for parallel subagent batch loop
- Updated `external-review.md` with three review mode paths (external_llm, opus_subagent, skip)
- Updated `section-index.md` for task-based generation
- Updated `context-check.md` for new task system

### Removed
- Legacy `TodoWrite` system (`scripts/lib/todos.py`)
- `generate-section-todos.py` script
- `tests/test_generate_section_todos.py`

## [0.1.0] - 2025-01-01

### Added
- Initial release
- Complete planning workflow: Research -> Interview -> External Review -> TDD Plan
- Section splitting with index generation
- External LLM review via Gemini and OpenAI
- Context check system for token management
- File-based session resumption

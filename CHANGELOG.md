# Changelog

All notable changes to deep-plan will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [5.0.0] - 2026-07-17

**Breaking:** plugin renamed `deep-plan-enhanced` → `deep` (repo name and
URL unchanged); `skills/mp-zoom-out/` removed. Reinstall required:
`claude plugin uninstall deep-plan-enhanced@kbichave-plugins && claude
plugin install deep@kbichave-plugins`.

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

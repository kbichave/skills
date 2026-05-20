# Changelog

All notable changes to deep-plan will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

# Project Instructions for AI Agents

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Build & Test

```bash
uv run --extra dev pytest          # full suite, ~800 tests, ~22s
uv run --extra dev pytest tests/test_pack_router.py -q   # one file
uvx ruff check scripts tests       # advisory: ~243 pre-existing violations
```

Python 3.11+. CI (`.github/workflows/tests.yml`) runs pytest on 3.11/3.12/3.13
as a blocking job and ruff as an advisory one.

**Verification before "done":** the suite must be green. Tests marked
`requires_bd` self-skip when the `bd` CLI is absent, which is how CI passes
without beads installed. Never add a test that fails without `bd`.

## Architecture Overview

A Claude Code plugin, not an application. Almost all behaviour is prose that a
model reads; Python exists to do the things a model should not be trusted to do
by hand (resolve, validate, count, persist).

| Directory | Holds |
|---|---|
| `skills/` | `deep` (discovery/plan/implement/auto), `review-panel`, `humanizer`, `no-op-remover` |
| `references/` | On-demand protocol files loaded by SKILL.md; see `INDEX.md` |
| `references/quality/` | 13 rule packs (core, service, warehouse, llm, iac …) + `lang/` guides |
| `agents/` | Subagent definitions, mostly the review panel |
| `scripts/lib/` | The real logic: `pack_router`, `quality_gate`, `deepstate`, `beads_sync` |
| `scripts/checks/` | CLI entry points the skill invokes |
| `scripts/hooks/` | Hook handlers wired in `hooks/hooks.json` |
| `lint/<lang>/adapter.json` | Maps packs to that language's linters and thresholds |

Session state never lands in the target repo. It goes to
`~/.claude/marketplace/deep-plan-enhanced/sessions/<slug>/<prefix>/.deepstate/`.
Code-review reports go to `~/.claude/code-reviews/`. Treat this as an invariant:
writing into a user's working tree needs an explicit opt-in flag.

## Conventions & Patterns

- **Stdlib only in `scripts/lib/` and `scripts/hooks/`.** The two runtime deps
  (`google-genai`, `openai`) are for external plan review and belong nowhere else.
- **Hooks use `python3`, not `uv run`.** A per-tool-call hook cannot afford the
  150-300 ms uv startup.
- **Hooks fail open.** A crashed hook must never block the user's edit. Wrap the
  body and swallow, the way `impl-post-tool-use.py` does.
- **Never print stray stdout from a hook** — it breaks Claude Code's hook parser.
  This has bitten this repo before; the warning lives in the hook docstrings.
- **Atomic writes for state**: write `.tmp`, then `os.rename`. See
  `DeepStateTracker._save`.
- **New BLOCK rules ship as WARN for one release** before flipping. See
  `docs/quality-pipeline-plan.md`.
- **Rule IDs are the vocabulary.** Findings reference `SEC-003`, `SQL-007`,
  `DBT-011` — never a prose restatement of the rule.
- **Don't add a pack resolver.** There is exactly one: `scripts/lib/pack_router.py`.
  Anything needing pack context calls it rather than re-deriving signals.
- Thresholds this repo holds itself to: complexity ≤10, function ≤50 lines,
  params ≤4, nesting ≤3 (`references/coding-standards.md`).

# Implement Protocol

Per-section execution discipline for `/deep implement` mode.

---

## Phase 1 — Confidence Gate (this is the skill)

**Before writing any code for a section**, rate readiness 1-10 across four factors:

| Factor | Question |
|---|---|
| Spec clarity | Are eval definitions, test stubs, function signatures specific enough to implement without guessing? |
| Dependency readiness | Are all `depends_on` sections complete and their interfaces available? |
| Codebase context | Can you locate the files and modules this section integrates with? |
| Scope | Single-pass implementable (<500 lines of changes)? |

Read prior `section_outcome` blocks from `impl-progress.md` before rating — earlier deviations change the calculus.

**Score interpretation:**

- **8-10:** Proceed normally.
- **5-7:** Proceed with caveats. Log concerns in `impl-findings.md`. Consider AMEND mutation per `plan-mutation-protocol.md`.
- **1-4:** Do NOT proceed.
  - Interactive: resolve the blocking unknowns by invoking `Skill(grill-me)`
    internally (one question at a time, each with a recommended answer) before
    re-rating — do not ask the user to run `/grill-me`.
  - Auto: log reason, apply SKIP or SPLIT mutation, move to next section.

Treat the gate as load-bearing. Cheap to do, prevents the worst class of bugs (implementing against a stale dependency interface).

## Phase 2 — Read spec + standards

1. `sections/{section-name}.md` + `claude-plan-tdd.md`
2. `references/coding-standards.md` before any code

## Phase 3 — Implement (tests first)

1. Write failing tests for capability evals
2. Implement the section
3. Watch tests pass

## Phase 4 — Eval check

After implementation, before review:

- **Capability evals:** Each checkbox item must have a corresponding passing test.
- **Regression evals:** Existing test suite — zero new failures.
- If any eval fails: fix before proceeding to review. If unfixable: log in `impl-findings.md` with reason.

## Phase 5 — Review

- Multi-language / non-Python / any target with resolved quality packs:
  `agents/code-reviewer.md` (pack-scoped, rule-ID tagged, per-language thresholds,
  report-only dead-code). Pass `active_packs` + `languages` from the blueprint.
- Python-only (legacy / `--quality=legacy`): `agents/python-code-reviewer.md`
  (7-criterion) remains for back-compat.
- `agents/opus-plan-reviewer.md` reviews **plans**, not code — not a code reviewer.

## Phase 6 — Quality gate

The gate is composed from the quality packs active for this target (frozen in the
blueprint at plan time) and the target's detected languages:

```python
from lib.pack_router import resolve_quality_mode, resolve_packs, detect_signals
from lib.quality_gate import build_gate
mode = resolve_quality_mode(cli_value=<--quality flag or None>)
plan = build_gate(active_packs, languages, Path("lint"), mode=mode)
# run plan.commands; enforce diff coverage >= plan.diff_coverage_min on changed lines
```

- `active_packs` come from the blueprint (resolved by `pack_router` at plan time);
  re-check drift at implement start.
- Diff coverage ≥85% on **changed lines**; whole-suite coverage must not drop;
  generated/vendored files exempt.
- `--quality=legacy` returns the fixed gate `ruff` + `mypy --strict` + `bandit -r`
  + `pytest --cov ≥85%` (see `references/coding-standards.md`) for rollout opt-out.
- New always-on `SEC-*`/`ENG-*` BLOCKs ship as WARN for one release before
  flipping to BLOCK. See `docs/quality-pipeline-plan.md`.

## Phase 7 — Context chaining

After review passes, append `section_outcome` to `impl-progress.md` under `## Section Outcomes`:

```markdown
## Section Outcomes

### section-01-foundation
- **Files:** src/core/__init__.py, src/core/types.py, tests/test_core_types.py
- **Interfaces:** Result[T] generic, AppError base exception, UserId NewType
- **Deviations:** None
- **Context:** Foundation types at src/core/types.py. All sections should use Result[T] for fallible operations.

### section-02-config
- **Files:** src/config/loader.py, src/config/models.py
- **Interfaces:** load_config(path: Path) -> AppConfig
- **Deviations:** Used TOML instead of YAML — pyproject.toml already in project
- **Context:** Config loading via load_config(). Downstream sections needing config import from src/config/loader.
```

Next section's confidence gate (Phase 1) reads these to assess:

- Whether dependency interfaces actually match what the section spec assumed
- Whether spec deviations invalidate the current section's approach
- Whether an AMEND mutation is needed before proceeding

This prevents drift — later sections account for how earlier sections landed, not just what was planned.

## Phase 8 — Close + mutate if needed

`tracker.close(section_id, reason)`. Apply plan mutations (`references/plan-mutation-protocol.md`) when reality diverges from plan.

## Phase 9 — Rollback (failure path)

If a section fails quality gates after 3 attempts (**3-strike rule**), consult the section's **Rollback Strategy** to undo changes cleanly before moving on.

- Same error 3 times → ask user (interactive) or log and continue with rollback (auto)

## Phase 10 — Post-mortem (terminal step)

Before writing `impl-summary.md`, ask: **what would have prevented the rework that happened in this mode?**

- If the answer is architectural (no good test seam, tangled callers, hidden coupling), append a `## Architectural follow-ups` section to `impl-summary.md` and suggest invoking `Skill(improve-codebase-architecture)` on the next session.
- If the answer is spec clarity (the gate kept firing at 5-7), flag it in `impl-summary.md` under `## Spec gaps observed` so the next plan iteration tightens.
- If the answer is "nothing — went clean", say so explicitly. Do not invent rework.

Make the recommendation **after** all sections land, not preemptively.

---

## Final verification

- Full test suite passes
- No TODOs in implemented files
- `impl-summary.md` written (Stop hook enforces)

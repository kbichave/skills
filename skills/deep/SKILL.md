---
name: deep
description: Discovery, planning, and implementation pipeline. Modes — discovery: system audit → phase specs; plan: implementation blueprint; implement: execute sections; auto: autonomous end-to-end. Accepts @path, inline text, or no argument.
license: MIT
compatibility: Requires uv (Python 3.11+). Optional Gemini or OpenAI API key for external review.
---

# Deep Skill

Pick mode by question:

| Question | Mode | Output | Load-bearing step |
|---|---|---|---|
| "What should we build?" | `discovery` | audit + phase specs | **Topic enumeration** |
| "How do I build phase X?" | `plan` | blueprint + sections | **Interview** (Premise Challenge) |
| "Code section X" | `implement` | tested code | **Confidence gate** |
| "Do it all autonomously" | `auto` | multi-phase plan + implement chain | **Discovery bridge** |

```
/deep discovery @path [--depth=quick|standard|deep]  → audit + phase specs
/deep plan @spec.md [--from-prd @prd.md | --from-adr @adrs/]  → blueprint
/deep implement [@dir]                               → execute sections
/deep auto @phases/                                  → end-to-end
```

**Discovery depth** (`audit` only):
- `quick`: scan + topics + interview + docs + phasing only (5-10 min)
- `standard` (default): all steps
- `deep`: all steps + cross-verify pass on top findings

**Express paths** (`plan` only): when input is already structured, skip research + interview.
- `--from-prd @prd.md`: PRD with requirements + acceptance criteria
- `--from-adr @adrs/`: existing ADR file or directory of ADRs

Also accepts inline text or no argument — see **Resolve Input**.

The load-bearing step in each mode is where most of the value lives. Spend disproportionate effort there. Other steps are mechanical.

---

## First Actions

### 1. Validate environment
```bash
bash ${DEEP_PLUGIN_ROOT}/scripts/checks/validate-env.sh
```
Parse JSON. Map `review_available` to `review_mode` (`full`/`gemini_only`/`openai_only` → `external_llm`; `none` → ask user: opus/sonnet/skip/exit). If `valid == false`: stop.

### 2. Vault init + routing
Lifecycle concerns live in `references/integration-protocol.md`:
- §1 vault resolution (sets `vault_available`)
- §2 skill-router invocation between phases
- §3 architecture-audit prompt (plan + implement)
- §4 end-of-mode vault-curator

### 3. Resolve input

| Argument | Mode |
|---|---|
| `discovery @path` or `@dir` without `claude-plan.md` | `audit` |
| `plan @file.md` or `@file.md` | `plan` |
| `implement [@path]` or `@dir` with `claude-plan.md` + `sections/` | `implement` |
| `auto @path` | `auto` |
| Inline text (no `@`) | Synthesize via `references/auto-spec-synthesis.md` |
| Empty | Ask: `"What do you want to build or audit?"` |

`--no-reframe`: skip Premise Challenge in interview. Auto always skips. Plan skips when spec has >5 concrete file paths or function signatures.

### 4. Setup session

For `audit` / `plan` / `auto`:
```bash
uv run ${DEEP_PLUGIN_ROOT}/scripts/checks/setup-session.py \
  --file "<target>" --plugin-root "${DEEP_PLUGIN_ROOT}" \
  --review-mode "${review_mode}" --session-id "${DEEP_SESSION_ID}" \
  --workflow "<audit | plan | auto>" \
  [--depth "<quick|standard|deep>"] \
  [--from-prd "<path>" | --from-adr "<path>"]
```
`--depth` is `audit`-only. `--from-prd` / `--from-adr` are `plan`-only and mutually exclusive.
Parse JSON: `new` → proceed; `resume` → continue at ready step; `complete` → stop; `success == false` → error.

For `implement`: skip setup-session. Use `@path` (or its parent), else `~/.claude/.deep-plan-active`. Validate `claude-plan.md`, `sections/index.md`, `.deepstate/state.json` exist.

---

## Workflow Loop

```
1. tracker.ready() → next unblocked step
2. Auto mode: if step is human-interactive (user-review,
   context-check-pre-review, context-check-pre-split),
   auto-close with reason "Auto mode: skipped" and repeat
3. Read step's reference file (index below)
4. Execute step
5. tracker.close(issue_id, reason)
6. Auto mode: if step was output-summary (phase complete),
   run implement for that phase before next phase
7. Repeat until all closed
```

---

## Reference Index

### Cross-cutting
| Concern | File |
|---|---|
| Vault, routing, architecture-audit, vault-curator | `references/integration-protocol.md` |
| Discovery findings reuse for auto + plan | `references/discovery-bridge.md` |
| Plan mutation (split/skip/reorder/insert/amend) | `references/plan-mutation-protocol.md` |
| Resume after compaction | `references/resume.md` |

### Discovery (`--workflow audit`)
| Step | Reference |
|---|---|
| Quick Scan, Deep Research | `references/audit-research-protocol.md` |
| Empirical Data | `references/audit-data-collection.md` |
| Topic Enumeration *(load-bearing)* | `references/audit-topic-enumeration.md` |
| Coverage Validation | `references/audit-coverage-validation.md` |
| Stakeholder Interview | `references/audit-interview-protocol.md` |
| Audit Docs | `references/audit-doc-writing.md` |
| Build-vs-Buy | `references/audit-build-vs-buy.md` |
| Phase Specs | `references/audit-phasing.md` |
| External Review | `references/external-review.md` |

### Plan (`--workflow plan`)
| Step | Reference |
|---|---|
| Research | `references/research-protocol.md` |
| Interview *(load-bearing)* | `references/interview-protocol.md` |
| Write Spec, Generate Plan | `references/plan-writing.md` |
| Context Check | `references/context-check.md` |
| External Review | `references/external-review.md` |
| Apply TDD | `references/tdd-approach.md` |
| Section Index, Sections | `references/section-index.md`, `references/section-splitting.md` |

Generate sections step:
```bash
uv run ${DEEP_PLUGIN_ROOT}/scripts/checks/generate-sections.py \
  --planning-dir "${planning_dir}" --session-id "${DEEP_SESSION_ID}"
```

**Coverage gate** (run after sections are written, before `output-summary` closes):
```bash
uv run ${DEEP_PLUGIN_ROOT}/scripts/checks/check-coverage.py \
  --planning-dir "${planning_dir}"
```
Exit 0 = pass, exit 1 = missing items (do NOT close output-summary). Parse JSON `missing` list; either add sections, mark items deferred in spec, or escalate to user.

### Auto (`--workflow auto`)
Multi-phase: parses `phasing-overview.md`, plans each phase in topological order, implements before next dependent phase plans. First phase = full plan workflow; later phases use `references/discovery-bridge.md`. Human-interactive steps auto-close at ready time (do NOT pre-close — breaks dependency chain).

Example: `plan P01 → implement P01 → plan P03 → implement P03 → plan P05 → implement P05`

### Implement
All section-level discipline lives in `references/implement-protocol.md`:
- Phase 1: confidence gate (1-10 rating) *(load-bearing)*
- Phase 2-3: read spec + standards, tests first
- Phase 4: eval check (capability + regression)
- Phase 5-6: review + quality gate (ruff + mypy + bandit + pytest --cov)
- Phase 7: context chaining (`section_outcome` → `impl-progress.md`)
- Phase 9: rollback (3-strike rule)
- Phase 10: post-mortem — answer "what would have prevented the rework?". Architectural answer → suggest `Skill(codebase-design)`. Spec-clarity answer → log under `## Spec gaps observed`. None → say so. Stop hook enforces.

Reads from `.deepstate/state.json`.

---

## Guardrails

1. **Always read the reference file for the current step before executing.**
2. **Never skip a step — `tracker.ready()` determines order.**
3. **Always close the step with `tracker.close()` after completing it.**
4. **Implement mode:** Do not exit until `impl-summary.md` exists (Stop hook enforces).

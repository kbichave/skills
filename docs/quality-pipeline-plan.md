# Quality Pipeline — deep-plan-enhanced

Status: **Spec / plan. No code implemented yet.**
Single source of truth. Supersedes and merges the earlier drafts
(`08-generalize-to-template-and-sdlc`, `09-rule-catalog-and-standards`,
`10-conditional-pack-loading-and-routing`) and all grill + review decisions.

---

## 1. Goal

Give the `/deep` pipeline an explicit, scoped, multi-language standard of "good
code" — rule families, metric thresholds, security checks, dead-code/tech-debt
rubrics — applied to the **target repository** `/deep` operates on, with only the
relevant rule packs loaded per session, and invoked as **internal pipeline steps**
(not user-facing skills).

### Locked decisions
- **D1 Vehicle** — ships inside `deep-plan-enhanced`. No separate repo, no new plugin.
- **D2 Mechanism** — reuse deep's `references/` convention, per-phase loading, and
  the `Skill()` internal-invocation mechanism. A **small net-new resolver**
  (`scripts/lib/pack_router.py`) does target-repo detection + pack matching.
  `skill-router` is NOT reused for packs (it routes skills by keyword and detects
  against the plugin dir, not the target).
- **D3 Borrow style** — reimplement the levnikolaevich rubrics (dead-code
  detection, metric thresholds, gated tech-debt fix) as deep's own reference text;
  do not copy their skill files (coupled to an L3-worker + hex-graph MCP
  framework). MIT attribution in `NOTICE`.
- **D4 Internal** — capabilities are pipeline steps the orchestrator invokes,
  including `Skill(grill-me)` from plan/discovery. Not slash commands users run.
- **D5 Scope** — full catalog v1; adapters for python / typescript / go.
- **Packs (Q5)** — grouped: `core`, `service`, `frontend`, `library`, `delivery`,
  `perf`, plus `supply`, `iac`, `llm`. Each family is a sub-file inside its pack.
- **Cadence (Q6)** — resolve once at plan, freeze into blueprint; cheap drift
  re-check at implement start.
- **Coverage (Q7)** — `TEST-002` = diff coverage ≥85% on changed lines; separate
  whole-suite non-regression; generated/vendored files exempt.
- **Overrides (Q8)** — `SEC-*` + core `ENG-*` BLOCKs non-overridable; others
  downgrade only with logged reason + review flag.
- **Greenfield (Q9)** — when no diff, resolve from spec-derived project/task type.
- **Qodo interop (Q10)** — deferred past v1, behind a flag.
- **Auditor cadence (Q11)** — per-section audit on changed files + one phase-end
  full sweep; auto-fix ≥90% confidence else report-only; token/latency budget cap.

---

## 2. Integration surface (existing deep primitives)

| Phase | Existing hook | Added |
| --- | --- | --- |
| Discovery | topic enumeration | rule families as audit lenses |
| Plan | Premise-Challenge interview | `Skill(grill-me)` internal; pack resolution → blueprint |
| Implement P2 | reads `references/coding-standards.md` | = `core` pack; load active packs for target |
| Implement P5 | review (`python-code-reviewer`) | new multi-lang `code-reviewer` |
| Implement P6 | gate `ruff+mypy+bandit+pytest≥85%` (Python-first) | per-pack × per-language adapter gate |
| Plan hook | — | `pack_router.py` resolves active set |

**Dedup.** Have: confidence gate, TDD, interview, review hook, vault, `Skill()`
mechanism, `coding-standards.md` (Python). Net-new: rule families beyond core,
`pack_router.py` (detection + matching), multi-language adapters, multi-lang
`code-reviewer`, dead-code/metric/tech-debt rubrics, `Skill(grill-me)` wiring.

Note: `opus-plan-reviewer` reviews *plans*, not code — it is not the multi-language
code reviewer; `code-reviewer` is a new agent.

---

## 3. Rule catalog

Each rule: **ID / Trigger / Required behavior / Verification signal**, tagged
severity (`BLOCK`/`WARN`/`ADVISE`) and enforcer (`linter`/`reviewer`/`router`/`human`).

### Always-on (in `core`)
- `ENG-*` — complexity ≤10, fn ≤50 lines, file ≤500, nesting ≤3, params ≤4,
  DRY/KISS/YAGNI, no dead code, layer boundaries.
- `SEC-*` — no secrets, boundary input validation, no injection,
  authz-before-mutation, session/token handling, CSRF, rate-limiting, IDOR
  (object-level authz), no PII/secrets in logs, vetted crypto, fail-closed.
- `TEST-*` — success+failure tests, diff coverage ≥85%, deterministic (no
  sleeps), isolation, behavior-oracle asserts.
- `ERR-*` — no swallowed/bare except, fail closed, actionable messages, validate
  at boundaries.

### Triggered
- `service` pack: `API-*` (stable fields, versioned breaking changes, error
  envelope, pagination, idempotency, additive events), `DATA-*` (reversible
  migrations, transactions, no N+1, indexes, expand/contract), `OBS-*` (structured
  logs, correlation IDs, error context, hot-path metrics, no PII), `CONC-*`
  (guarded shared state, timeouts+bounded retry/backoff, idempotent ops, no
  check-then-act races, resource cleanup).
- `delivery` pack: `DEP-*` (lockfile synced, pinned, license policy, no
  abandoned/typosquat), `CFG-*` (no hardcoded env values, schema-validated, safe
  fail-closed defaults), `DOC-*` (public API documented, ADRs, WHY-comments).
- `perf` pack: `PERF-*` (bounded memory/IO, cache invalidation, pagination).
- `supply` pack: `SUPPLY-*` (lockfile-hash verify, build provenance, no
  postinstall-script abuse, pinned CI actions `@<sha>`).
- `iac` pack: `IAC-*` (Dockerfile non-root/no-`latest`, Terraform/k8s misconfig,
  no public buckets / open security groups).
- `llm` pack: `LLM-*` (untrusted-content-in-prompt isolation, tool-call
  allowlisting, output sanitization).

### Tiering rules
- BLOCK (machine-enforceable): ENG metrics, secrets scan, secrets/PII-in-logs,
  bare-except, lockfile-sync, diff-coverage, injection.
- WARN: most contract/observability/concurrency review findings.
- ADVISE (evidence-gated): DRY/KISS, `PERF-*` — emit only with a named duplicated
  symbol or a measured number (AI reviewers false-positive on these otherwise).
- `DEP` CVE is tiered: BLOCK on reachable critical, WARN otherwise (don't block on
  unfixable transitives).

### Per-language thresholds (in each adapter, not global)
- Python / TS: complexity ≤10, fn ≤50, file ≤500, params ≤4.
- Go: fn ≤70 (err-blocks inflate), file-size ADVISE, params exclude
  `context.Context`/`error`, complexity calibrated to gocyclo (~12–15).

### Borrowed rubrics (D3)
- **Dead-code three-layer detection:** (1) candidate scan, (2) context verify
  (dynamic import/reflection, public-API export, monorepo cross-use, git-blame
  age), (3) entrypoint/framework manifest awareness per language. Hard rule: never
  auto-delete an exported symbol or anything matching a registered
  entrypoint/build-tag/DI pattern, any confidence. Blind spots to cover: Py
  `getattr`/entry-points/Django-Celery handlers/pytest fixtures; TS DI
  decorators/Next.js routes/barrel re-exports/dynamic `import()`; Go `init()`
  side-effect imports/`reflect`/interface satisfaction/build tags. **v1
  report-only;** auto-delete only private single-file no-reflection symbols.
- Tech-debt auto-fix ≥90% confidence, low-risk only; never logic/security/arch.

### Working standards (`WRK-*`, process)
plan-before-code, spec-before-plan, cite rule IDs, TDD, bounded change,
conventional commits, never weaken a gate, guidelines audit pre-PR, resolve
findings, DoD. Mostly already implicit in deep — made explicit.

---

## 4. Pack architecture + router

```
references/quality/
  core/        index.md + family sub-files   # always-on
  service/  delivery/  perf/  frontend/  library/  supply/  iac/  llm/
  _PACK-TEMPLATE.md
lint/
  python/  typescript/  go/                   # per-pack adapter fragments + thresholds
scripts/lib/pack_router.py                     # net-new resolver
```

Each pack `index.md` frontmatter (read by `pack_router.py`):
```yaml
pack: service
applies_when:
  languages: [python, typescript, go]
  project_types: [backend, api]
  changed_globs: ["**/api/**", "**/routes/**", "**/migrations/**"]
  task_types: [add-endpoint, change-api, add-migration]
provides_rules: [API, DATA, OBS, CONC]
skills_eligible: [code-reviewer, dead-code, tech-debt]
lint: { python: lint/python/service.toml, typescript: lint/ts/service.json, go: lint/go/service.yml }
```

**Detection** (`pack_router.py`, takes explicit `target_root` ≠ plugin dir):
`languages` (extensions+manifests), `project_types` (markers), `changed_globs`
(`git diff`), `task_types` (spec/interview). Unknown → `core`; ambiguous → superset.

**Plan-time vs implement-time:** at plan time the target usually has no diff, so
resolution is spec/task-driven; `changed_globs` only refine at the implement-start
re-check. Active set frozen into blueprint (reviewable, reproducible).

**Adapters:** rules are language-neutral; adapter maps each to a tool
(ENG-001 → ruff C901 / eslint complexity / gocyclo; ENG-007 → vulture·ruffF401 /
ts-prune / deadcode; SEC-003 → semgrep / gosec). P6 gate = `active packs ×
detected languages`. New language = add `lint/<lang>/` + rows; rules unchanged.

---

## 5. Internal invocation (D4)

- `Skill(grill-me)` — plan premise challenge + low-confidence implement gate.
- dead-code / tech-debt / metric checks — implement P5 review + P6 gate via
  `code-reviewer`, pack-scoped; per-section on changed files + phase-end sweep,
  budget-capped.
- rule selection + agent summary — produced by `pack_router.py`, embedded in
  blueprint. User sees the result, not a tool to run.

---

## 6. Generated artifacts (no drift)
From the active set, regenerate (never hand-edit): the P6 gate command; (deferred)
Qodo `best_practices.md` / `pr_compliance_checklist.yaml` slices. A
freshness check (source-of-truth hash over packs) fails if an artifact is stale.

---

## 7. Build sequence (each = own PR, tests green)

0. **Test harness + rollback.** Golden-fixture synthetic targets
   (python/ts/go × backend/frontend/greenfield) → assert `pack_router.py` resolves
   the expected active set. Add `--quality=legacy` flag restoring today's fixed
   gate. Land before any behavior change.
1. Scaffold `references/quality/` + `_PACK-TEMPLATE.md`; **additively** author
   `core` (ENG+SEC+TEST+ERR, per-language). Leave `coding-standards.md` as a
   pointer (it backs the live gate); retire only in step 4.
2. Author grouped packs + family sub-files: service, delivery, perf, frontend,
   library, supply, iac, llm.
3. Build `pack_router.py` (target_root detection + `applies_when` matching) +
   pack frontmatter; emit active-context into blueprint.
4. Build `lint/` adapters (py/ts/go, per-language thresholds); P6 gate consumes
   `active × languages`; retire the `coding-standards.md` pointer.
5. New `code-reviewer` agent (multi-language; `python-code-reviewer` kept as
   back-compat / python profile) with dead-code(3-layer, report-only)/metric/
   tech-debt rubrics, pack-scoped.
6. Wire `Skill(grill-me)` internal calls.
7. Discovery: rule families as audit lenses in topic enumeration.
8. Generated artifacts + freshness check. Update `NOTICE`, `CHANGELOG`,
   `docs/skill-routing.md`.

**Rollout / back-compat (cross-cutting):** new always-on `SEC-*`/`ENG-*` BLOCKs
ship as WARN for one release (or opt-in) before flipping to BLOCK, so repos
passing today don't break on upgrade.

---

## 8. Risks
- **Resolver scope creep** — `pack_router.py` must stay detection+matching, not a
  full manifest runtime. Guard with the step-0 fixtures.
- **AI-reviewer false positives** on subjective rules — mitigated by
  evidence-gating DRY/KISS/PERF.
- **Dead-code mis-deletion** — mitigated by 3-layer detection + report-only v1.
- **Token/latency cost** of per-section auditing — mitigated by budget cap +
  optional full sweep in `auto`.
- **Back-compat** — mitigated by WARN-first rollout + `--quality=legacy`.

---

## 9. Still open
1. Pack granularity within `service` — keep API+DATA+OBS+CONC together, or split
   `data` out for data-heavy repos?
2. Freshness-hash mechanism details (what's hashed, where stored).
3. Exact `task_types` vocabulary + how the spec/interview emits it.
4. Whether `code-reviewer` fully replaces `python-code-reviewer` or wraps it.

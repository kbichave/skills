# Reference Index

Navigation hub for `references/`. SKILL.md maps each workflow step to a file; this index groups by topic and flags load-bearing material.

## Cross-cutting

| File | Loaded by |
|---|---|
| `integration-protocol.md` | All modes — vault init, skill-router, architecture-audit, vault-curator |
| `discovery-bridge.md` | Auto + plan when discovery artifacts present |
| `plan-mutation-protocol.md` | Implement when reality diverges from plan |
| `auto-spec-synthesis.md` | All modes when input is inline text |
| `external-review.md` | Plan + Discovery review steps |
| `repository-freshness.md` | Refreshing secondary repositories before cross-project analysis |
| `coding-standards.md` | Implement before any code |
| `guardrails.md` | PreToolUse blocking layer — credentials, protected paths, test lock |
| `claude-md-protocol.md` | Generating and updating a target repo's CLAUDE.md |
| `spec-policy.md` | Plan — projecting quality rules into spec obligations |
| `implement-protocol.md` | Implement (Phase 1-10 per section) |
| `resume.md` | After `/clear` or compaction |
| `question-selection.md` | Any `AskUserQuestion` round — scores candidates by information gain |

## Discovery (`--workflow audit`)

| Phase | File | Notes |
|---|---|---|
| Quick Scan | `audit-research-protocol.md` | Same file as deep research — section per phase inside |
| Empirical Data | `audit-data-collection.md` | |
| **Topic Enumeration** *(load-bearing)* | `audit-topic-enumeration.md` | STORM-style 3-perspective enumeration. Topics drive everything else. |
| Deep Research | `audit-research-protocol.md` | |
| Coverage Validation | `audit-coverage-validation.md` | |
| Stakeholder Interview | `audit-interview-protocol.md` | |
| Audit Docs | `audit-doc-writing.md` | |
| Build-vs-Buy | `audit-build-vs-buy.md` | |
| Phase Specs | `audit-phasing.md` | |

## Plan (`--workflow plan`)

| Phase | File | Notes |
|---|---|---|
| Research | `research-protocol.md` | Source hierarchy: Context7 → official docs → web |
| **Interview** *(load-bearing)* | `interview-protocol.md` | Premise Challenge round catches wrong-problem framings |
| Spec, Plan | `plan-writing.md` | |
| Context Check | `context-check.md` | |
| External Review | `external-review.md` | |
| TDD | `tdd-approach.md` | |
| Section Index | `section-index.md` | |
| Section Splitting | `section-splitting.md` | |

## Goalloop (`--workflow goalloop`)

| Phase | File | Notes |
|---|---|---|
| All seven control steps | `goalloop-protocol.md` | §1 goal · §2 probe · §3 ledger · §4 the iteration · §5 verify |
| Clarification round | `question-selection.md` | Run at `--budget 2` — an unattended mode asks rarely |

The loop's own discipline is in `goalloop-protocol.md`. The SDLC work is
delegated: each iteration runs a nested `plan` and `implement` session, so
`plan-writing.md`, `implement-protocol.md` and the rest apply unchanged.
**§5's three-clause done test is load-bearing** — it is the only thing standing
between an autonomous loop and a run that declares itself finished.

## Implement

All section-level discipline in `implement-protocol.md`. Phases 1-10 with explicit gates. **Phase 1 confidence gate is load-bearing** — cheap, prevents the worst class of bugs.

## Code review

| File | Loaded by |
|---|---|
| `review-panel-protocol.md` | Every panel expert — input, output JSON, detective sweep, rules |
| `code-review-context.md` | `code-review` step 2 when the user picks Auto-discover |
| `quality/` | Rule packs the core reviewer enforces; `quality/lang/` for per-language idioms |

## Anti-patterns reference

| File | Purpose |
|---|---|
| `common-rationalizations.md` | Reviewer cross-check before accepting "fix later" arguments |

## Perspectives library

`perspectives/` — expert viewpoints used by Topic Enumeration to broaden coverage.

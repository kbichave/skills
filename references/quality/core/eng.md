# ENG — Engineering standards

Always-on. Thresholds are per-language (see `lint/<lang>/`); Go relaxes size and
param limits (err-blocks inflate, `context.Context`/`error` excluded from param
count).

### ENG-001: Bound cyclomatic complexity
- **Trigger:** any added or changed function.
- **Required behavior:** complexity within the per-language limit (Python/TS ≤10; Go ~12–15 via gocyclo).
- **Verification signal:** linter (ruff `C901` / eslint `complexity` / gocyclo).
- **Severity:** BLOCK (non-overridable)
- **Enforcer:** linter

### ENG-002: Bound function length
- **Trigger:** any added or changed function.
- **Required behavior:** within per-language limit (Python/TS ≤50 lines; Go ≤70).
- **Verification signal:** linter / reviewer.
- **Severity:** WARN
- **Enforcer:** linter

### ENG-003: Bound file length
- **Trigger:** any added or changed file.
- **Required behavior:** ≤500 lines (ADVISE in Go).
- **Verification signal:** linter.
- **Severity:** WARN (ADVISE in Go)
- **Enforcer:** linter

### ENG-004: Bound nesting depth
- **Trigger:** any added or changed function.
- **Required behavior:** nesting depth ≤3.
- **Verification signal:** linter / reviewer.
- **Severity:** WARN
- **Enforcer:** linter

### ENG-005: Bound parameter count
- **Trigger:** any added or changed function.
- **Required behavior:** ≤4 params (Go excludes `context.Context`/`error`; allow 5).
- **Verification signal:** linter / reviewer.
- **Severity:** WARN
- **Enforcer:** linter

### ENG-006: No needless duplication or abstraction (DRY/KISS/YAGNI)
- **Trigger:** new code that resembles existing code, or new abstraction layers.
- **Required behavior:** no copy-paste of non-trivial logic; no abstraction without ≥2 real call sites.
- **Verification signal:** reviewer cites a **named** duplicated symbol or the speculative seam.
- **Severity:** ADVISE (evidence-gated — emit only with a concrete named instance)
- **Enforcer:** reviewer

### ENG-007: No dead code
- **Trigger:** any change.
- **Required behavior:** no unused imports/vars/functions; no commented-out blocks. Removal uses three-layer detection (scan → context verify → entrypoint/framework awareness); never auto-delete exported symbols or registered entrypoints. v1 report-only except private single-file no-reflection symbols.
- **Verification signal:** linter (ruff `F401` / ts-prune / deadcode) + reviewer for the contextual layers.
- **Severity:** WARN (unused imports BLOCK)
- **Enforcer:** linter + reviewer

### ENG-008: Respect layer/architecture boundaries
- **Trigger:** imports crossing module/layer lines.
- **Required behavior:** no cross-layer leaks (e.g. domain importing transport).
- **Verification signal:** reviewer; import-linter where configured.
- **Severity:** WARN
- **Enforcer:** reviewer

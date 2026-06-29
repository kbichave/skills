# TEST — Testing

Always-on.

### TEST-001: Behavior change has success + failure tests
- **Trigger:** any behavior change.
- **Required behavior:** at least one happy-path and one failure-path test.
- **Verification signal:** new/changed tests exercise both paths.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### TEST-002: Diff coverage ≥85%
- **Trigger:** any code change.
- **Required behavior:** ≥85% coverage on changed lines. Whole-suite coverage must not drop. Generated/vendored/glue files exempt.
- **Verification signal:** diff-coverage tool against changed lines.
- **Severity:** BLOCK (exempt globs excluded)
- **Enforcer:** linter

### TEST-003: Deterministic tests
- **Trigger:** new/changed tests.
- **Required behavior:** no `sleep`/wall-clock waits; no reliance on real time, network, or ordering.
- **Verification signal:** reviewer; flake re-run check.
- **Severity:** WARN
- **Enforcer:** reviewer

### TEST-004: Test isolation
- **Trigger:** new/changed tests.
- **Required behavior:** no shared mutable state; order-independent; mock only at boundaries.
- **Verification signal:** suite passes under random order.
- **Severity:** WARN
- **Enforcer:** reviewer

### TEST-005: Assert on behavior, not implementation
- **Trigger:** new/changed tests.
- **Required behavior:** assert observable behavior/oracle, not private internals.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### TEST-006: No business logic in tests
- **Trigger:** new/changed tests.
- **Required behavior:** tests use literals/fixtures, not reimplemented logic.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

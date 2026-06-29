# CONC — Concurrency & reliability

### CONC-001: No unguarded shared mutable state
- **Trigger:** state shared across threads/tasks/goroutines.
- **Required behavior:** guarded by lock/atomic/channel or made immutable.
- **Verification signal:** reviewer; race detector where available (`go test -race`).
- **Severity:** BLOCK
- **Enforcer:** reviewer

### CONC-002: External calls have timeout + bounded retry
- **Trigger:** network/IO call.
- **Required behavior:** explicit timeout; retries bounded with backoff.
- **Verification signal:** reviewer; test.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### CONC-003: Idempotent or guarded operations
- **Trigger:** operation that may run twice (retry, redelivery).
- **Required behavior:** idempotent or guarded against double-apply.
- **Verification signal:** test for double-run.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### CONC-004: No check-then-act races
- **Trigger:** check followed by dependent mutation.
- **Required behavior:** atomic operation or lock; no TOCTOU gap.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### CONC-005: Release resources
- **Trigger:** acquiring files/connections/locks.
- **Required behavior:** deterministic cleanup (context manager / defer / finally).
- **Verification signal:** linter + reviewer.
- **Severity:** BLOCK
- **Enforcer:** linter + reviewer

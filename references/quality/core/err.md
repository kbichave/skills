# ERR — Error handling

Always-on.

### ERR-001: No swallowed exceptions
- **Trigger:** try/except (catch) blocks.
- **Required behavior:** no bare `except:` / empty catch; handle, re-raise, or log with context.
- **Verification signal:** linter (ruff `BLE001`/`E722` / eslint no-empty).
- **Severity:** BLOCK
- **Enforcer:** linter

### ERR-002: Fail closed
- **Trigger:** error paths in security/payment/state-mutating code.
- **Required behavior:** on error, deny/abort rather than silently continue.
- **Verification signal:** test for the failure path asserts no side effect.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### ERR-003: Actionable error messages
- **Trigger:** raised/returned errors crossing a boundary.
- **Required behavior:** message states what failed and the recovery path.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### ERR-004: Validate at boundaries, trust internals
- **Trigger:** internal function adding defensive checks.
- **Required behavior:** validate at system boundaries; do not re-validate guaranteed internal invariants.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

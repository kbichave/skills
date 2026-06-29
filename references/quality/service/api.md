# API — Contracts

### API-001: Stable response field names + casing
- **Trigger:** changing a public response shape.
- **Required behavior:** keep field names and casing stable; additions are backward-compatible.
- **Verification signal:** contract test; reviewer.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### API-002: Breaking changes require version bump + deprecation
- **Trigger:** removing/renaming a field or changing semantics.
- **Required behavior:** version the endpoint and provide a deprecation path.
- **Verification signal:** reviewer; version present.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### API-003: Uniform error envelope
- **Trigger:** returning an error.
- **Required behavior:** consistent `{code, message, recovery}` shape.
- **Verification signal:** reviewer; test.
- **Severity:** WARN
- **Enforcer:** reviewer

### API-004: Pagination + limits on list endpoints
- **Trigger:** an endpoint returning a collection.
- **Required behavior:** bounded page size with a default cap.
- **Verification signal:** test; reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### API-005: Idempotency on unsafe mutations
- **Trigger:** non-idempotent mutation (create/charge/refund).
- **Required behavior:** require an idempotency key; a retry returns the original result and emits no duplicate event.
- **Verification signal:** test asserts retry returns same payload, one event.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### API-006: Stable, additive event keys
- **Trigger:** emitting/changing domain events.
- **Required behavior:** event keys stable; new events additive.
- **Verification signal:** contract test.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

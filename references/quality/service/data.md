# DATA — Persistence

### DATA-001: Reversible, tested migrations
- **Trigger:** schema migration.
- **Required behavior:** up and down both implemented and tested.
- **Verification signal:** migration test runs up/down.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### DATA-002: Writes in transactions
- **Trigger:** multi-step write.
- **Required behavior:** atomic; no partial commits.
- **Verification signal:** reviewer; test for rollback on mid-failure.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### DATA-003: No N+1 queries on hot paths
- **Trigger:** loops issuing per-item queries.
- **Required behavior:** batch/join instead of per-row queries.
- **Verification signal:** reviewer cites the loop + query count.
- **Severity:** WARN (evidence-gated)
- **Enforcer:** reviewer

### DATA-004: Index query predicates
- **Trigger:** new query filter/sort on a large table.
- **Required behavior:** supporting index exists.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### DATA-005: Backward-compatible schema (expand/contract)
- **Trigger:** schema change with code deploy.
- **Required behavior:** expand-then-contract so schema and code can deploy independently.
- **Verification signal:** reviewer.
- **Severity:** BLOCK
- **Enforcer:** reviewer

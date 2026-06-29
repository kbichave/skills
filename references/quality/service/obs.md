# OBS — Observability

### OBS-001: Structured logging
- **Trigger:** adding logs.
- **Required behavior:** structured key/value logs, no string-concatenated payloads.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### OBS-002: Propagate correlation/request ID
- **Trigger:** request-handling or cross-service calls.
- **Required behavior:** correlation ID threaded through logs and downstream calls.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### OBS-003: Errors logged with actionable context
- **Trigger:** error handling.
- **Required behavior:** log includes operation, identifiers, and cause (no PII — see SEC-008).
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### OBS-004: Metrics on critical paths
- **Trigger:** new hot path.
- **Required behavior:** latency/error/throughput metric emitted.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

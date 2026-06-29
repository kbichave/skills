# SEC — Security

Always-on. All `SEC-*` BLOCKs are **non-overridable** (decision Q8).

### SEC-001: No secrets committed
- **Trigger:** any change.
- **Required behavior:** no keys/tokens/credentials in source, config, or history.
- **Verification signal:** secret scanner (gitleaks / semgrep) in pre-commit + gate.
- **Severity:** BLOCK
- **Enforcer:** linter

### SEC-002: Validate input at system boundaries
- **Trigger:** code accepting external input (HTTP, CLI, queue, file).
- **Required behavior:** validate/parse at the boundary; trust internal calls thereafter.
- **Verification signal:** reviewer; schema/validator present at the entry point.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### SEC-003: No injection
- **Trigger:** building SQL, shell, or template strings.
- **Required behavior:** parameterized queries / safe APIs; never string-concatenate untrusted input.
- **Verification signal:** semgrep / gosec / bandit.
- **Severity:** BLOCK
- **Enforcer:** linter

### SEC-004: Authz + scope check before state mutation
- **Trigger:** any mutation endpoint or privileged action.
- **Required behavior:** authenticate and check required scope/role before mutating state or emitting events.
- **Verification signal:** test asserts unauthorized → denied with no side effect.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### SEC-005: Object-level authz (no IDOR)
- **Trigger:** access to a resource identified by a client-supplied ID.
- **Required behavior:** verify the caller owns/may access that specific object.
- **Verification signal:** test for cross-tenant/other-user access → denied.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### SEC-006: Session/token + CSRF handling
- **Trigger:** auth, session, or cookie handling.
- **Required behavior:** secure/short-lived tokens; CSRF protection on state-changing browser requests.
- **Verification signal:** reviewer; framework CSRF middleware enabled.
- **Severity:** WARN
- **Enforcer:** reviewer

### SEC-007: Rate limiting on abusable endpoints
- **Trigger:** auth, write, or expensive endpoints.
- **Required behavior:** rate limit / throttle present.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### SEC-008: No secrets or PII in logs/telemetry
- **Trigger:** logging, metrics, error reporting.
- **Required behavior:** no credentials, tokens, or PII emitted to logs/telemetry/URLs.
- **Verification signal:** semgrep patterns + reviewer.
- **Severity:** BLOCK
- **Enforcer:** linter + reviewer

### SEC-009: Vetted crypto, fail closed
- **Trigger:** crypto, auth, or security-error handling.
- **Required behavior:** standard vetted libraries; no homegrown/weak algorithms; security errors fail closed.
- **Verification signal:** reviewer + test for the closed path.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### SEC-010: Dependencies free of reachable critical CVEs
- **Trigger:** dependency manifest change.
- **Required behavior:** no reachable critical CVE; lower severities tracked.
- **Verification signal:** pip-audit / osv-scanner; severity+reachability tiered.
- **Severity:** BLOCK on reachable critical, else WARN
- **Enforcer:** linter

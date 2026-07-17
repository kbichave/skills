# SEC — Security

Always-on. All `SEC-*` BLOCKs are **non-overridable** (decision Q8).

Every rule carries its **OWASP Top 10 (2021)** category and **CWE** id so
findings cite the canonical taxonomy (e.g. `SEC-003 → A03:Injection / CWE-89`).
Include the code in the finding `tag` or `teach.principle`. Reviewers should
sweep the diff against the OWASP Top 10 and the CWE Top 25 most-dangerous
weaknesses, not just the rules enumerated here — an uncovered weakness is a
`SEC-000` finding pointing at its CWE.

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

### SEC-011: No server-side request forgery (SSRF)
- **Trigger:** server makes an outbound request to a URL/host derived from user input.
- **Required behavior:** allowlist destinations; block internal/metadata ranges (169.254.169.254, RFC-1918, localhost); resolve-then-validate to defeat DNS rebinding.
- **Verification signal:** reviewer + test that an internal-IP target is rejected.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### SEC-012: No unsafe deserialization of untrusted data
- **Trigger:** deserializing external input (`pickle`, `yaml.load`, `Marshal.load`, Java native, `unserialize`).
- **Required behavior:** never deserialize untrusted data with an object-constructing loader; use data-only formats (JSON) or safe loaders (`yaml.safe_load`), or sign+verify the payload.
- **Verification signal:** semgrep / bandit (B301/B506) + reviewer.
- **Severity:** BLOCK
- **Enforcer:** linter + reviewer

### SEC-013: No path traversal
- **Trigger:** file path built from user input.
- **Required behavior:** canonicalize and confirm the resolved path stays within the intended base dir; reject `..` and absolute-path escapes.
- **Verification signal:** reviewer + test that `../../etc/passwd` is rejected.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### SEC-014: No open redirect
- **Trigger:** redirect/forward target derived from user input.
- **Required behavior:** redirect only to a relative path or an allowlisted host; never to an arbitrary user-supplied absolute URL.
- **Verification signal:** reviewer + test that an off-site redirect target is rejected.
- **Severity:** WARN
- **Enforcer:** reviewer

## OWASP / CWE crosswalk

Cite these codes in findings. Sweep the whole OWASP Top 10 and CWE Top 25 —
these are the mapped anchors, not the ceiling.

| Rule | OWASP 2021 | CWE |
|---|---|---|
| SEC-001 secrets | A05 Security Misconfiguration / A07 | CWE-798 hard-coded credentials |
| SEC-002 boundary validation | A03 Injection / A04 Insecure Design | CWE-20 improper input validation |
| SEC-003 injection | A03 Injection | CWE-89 SQLi / CWE-78 OS cmd / CWE-77 |
| SEC-004 authz before mutation | A01 Broken Access Control | CWE-862 missing authorization |
| SEC-005 object-level authz (IDOR) | A01 Broken Access Control | CWE-639 / CWE-863 |
| SEC-006 session/token + CSRF | A07 Auth Failures | CWE-352 CSRF / CWE-384 |
| SEC-007 rate limiting | A04 Insecure Design | CWE-770 / CWE-400 resource consumption |
| SEC-008 no secrets/PII in logs | A09 Logging Failures | CWE-532 / CWE-200 info exposure |
| SEC-009 vetted crypto, fail closed | A02 Cryptographic Failures | CWE-327 / CWE-326 |
| SEC-010 vulnerable dependencies | A06 Vulnerable Components | CWE-1104 / CWE-937 |
| SEC-011 SSRF | A10 SSRF | CWE-918 |
| SEC-012 unsafe deserialization | A08 Software/Data Integrity | CWE-502 |
| SEC-013 path traversal | A01 / A03 | CWE-22 |
| SEC-014 open redirect | A01 Broken Access Control | CWE-601 |

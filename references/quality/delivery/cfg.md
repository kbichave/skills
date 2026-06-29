# CFG — Configuration

### CFG-001: No hardcoded environment-specific values
- **Trigger:** adding URLs, hosts, credentials, or toggles.
- **Required behavior:** read from env/secret store, not literals.
- **Verification signal:** semgrep + reviewer.
- **Severity:** BLOCK
- **Enforcer:** linter + reviewer

### CFG-002: Schema-validated config
- **Trigger:** adding config inputs.
- **Required behavior:** config parsed/validated against a schema at startup.
- **Verification signal:** reviewer; test.
- **Severity:** WARN
- **Enforcer:** reviewer

### CFG-003: Safe defaults, fail closed
- **Trigger:** optional/missing config.
- **Required behavior:** secure default; fail closed when a required value is absent.
- **Verification signal:** test for missing-config path.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

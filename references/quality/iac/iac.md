# IAC — Infrastructure as code

### IAC-001: Containers run non-root, pinned base images
- **Trigger:** Dockerfile change.
- **Required behavior:** non-root `USER`; base image pinned (digest/version), not `latest`.
- **Verification signal:** hadolint / reviewer.
- **Severity:** BLOCK
- **Enforcer:** linter + reviewer

### IAC-002: No public exposure by default
- **Trigger:** networking/storage resources.
- **Required behavior:** no `0.0.0.0/0` ingress, no public buckets unless explicitly required and justified.
- **Verification signal:** tfsec / checkov / reviewer.
- **Severity:** BLOCK
- **Enforcer:** linter + reviewer

### IAC-003: No secrets in IaC
- **Trigger:** infra config.
- **Required behavior:** secrets via secret manager refs, not inline.
- **Verification signal:** scanner + reviewer.
- **Severity:** BLOCK
- **Enforcer:** linter

### IAC-004: Least-privilege IAM
- **Trigger:** roles/policies.
- **Required behavior:** scoped permissions; no wildcard admin.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

# SUPPLY — Supply chain

### SUPPLY-001: Lockfile hash integrity
- **Trigger:** dependency change.
- **Required behavior:** install verifies lockfile hashes (e.g. `--require-hashes`, frozen install).
- **Verification signal:** CI uses frozen/locked install.
- **Severity:** BLOCK
- **Enforcer:** linter

### SUPPLY-002: No postinstall-script abuse
- **Trigger:** adding a package with install scripts (npm).
- **Required behavior:** review/justify lifecycle scripts; prefer `--ignore-scripts` where viable.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### SUPPLY-003: Pinned CI actions
- **Trigger:** editing CI workflows.
- **Required behavior:** third-party actions pinned to a full commit SHA, not a floating tag.
- **Verification signal:** linter/reviewer over workflow files.
- **Severity:** BLOCK
- **Enforcer:** linter + reviewer

### SUPPLY-004: Build provenance where available
- **Trigger:** release/publish pipeline change.
- **Required behavior:** emit provenance/attestation for published artifacts.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

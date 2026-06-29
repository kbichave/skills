# DEP — Dependencies

### DEP-001: Lockfile committed and in sync
- **Trigger:** dependency manifest change.
- **Required behavior:** lockfile updated and consistent with the manifest.
- **Verification signal:** CI lockfile-sync check.
- **Severity:** BLOCK
- **Enforcer:** linter

### DEP-002: Pinned versions in production
- **Trigger:** adding a runtime dependency.
- **Required behavior:** no unbounded floating ranges for prod deps.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### DEP-003: License policy compliance
- **Trigger:** adding a dependency.
- **Required behavior:** license within org allowlist.
- **Verification signal:** license scanner.
- **Severity:** BLOCK
- **Enforcer:** linter

### DEP-004: No abandoned / typosquat packages
- **Trigger:** adding a dependency.
- **Required behavior:** maintained package, correct name; live check on recency.
- **Verification signal:** reviewer + live lookup.
- **Severity:** WARN
- **Enforcer:** reviewer

### DEP-005: Justify new dependencies
- **Trigger:** adding a dependency.
- **Required behavior:** prefer stdlib/existing; justify the addition.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

# DOC — Documentation

### DOC-001: Public API documented
- **Trigger:** adding/changing a public function/endpoint/CLI.
- **Required behavior:** documented signature, behavior, and errors.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### DOC-002: ADR for non-obvious decisions
- **Trigger:** architectural/dependency/trade-off decision.
- **Required behavior:** capture as an ADR.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### DOC-003: Comments explain WHY, not WHAT
- **Trigger:** adding comments.
- **Required behavior:** comment only non-obvious rationale/constraints; no task/PR refs that rot.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### DOC-004: Docs match behavior
- **Trigger:** behavior change touching documented features.
- **Required behavior:** update README/docs to match.
- **Verification signal:** reviewer.
- **Severity:** ADVISE
- **Enforcer:** reviewer

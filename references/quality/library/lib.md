# LIB — Library / public surface

### LIB-001: Semver discipline
- **Trigger:** changing the public API of a published library.
- **Required behavior:** breaking change → major bump; additive → minor; fix → patch.
- **Verification signal:** reviewer; API-diff tool where available.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### LIB-002: Minimal, intentional public surface
- **Trigger:** exporting symbols.
- **Required behavior:** export only what consumers need; keep internals private.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### LIB-003: No leaking internal/transitive types in the public API
- **Trigger:** public signatures referencing internal types.
- **Required behavior:** public API uses public, stable types.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

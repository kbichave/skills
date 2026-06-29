---
pack: core
applies_when:
  always: true
provides_rules: [ENG, SEC, TEST, ERR]
---

# Core pack (always-on)

Baseline standards applied to every target repo on every `/deep` task,
regardless of language or task type. Loaded at implement Phase 2 alongside
(eventually instead of) `references/coding-standards.md`.

Families:
- [ENG](eng.md) — engineering standards (size, complexity, dead code, design)
- [SEC](sec.md) — security
- [TEST](test.md) — testing
- [ERR](err.md) — error handling

Severity floor: `SEC-*` and the `ENG` metric BLOCKs are **non-overridable**
(decision Q8). Other BLOCKs may downgrade only with a logged reason in the
blueprint.

Rollout: new always-on BLOCKs ship as WARN for one release before flipping to
BLOCK so repos passing today do not break on upgrade.

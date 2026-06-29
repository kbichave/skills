---
pack: library
applies_when:
  project_types: [library, sdk]
  task_types: [release, public-api]
provides_rules: [LIB]
---

# Library pack

Published-library concerns: stable public surface, semver, docs. Reuses API-*
(contracts) and DOC-* (docs) from the service/delivery packs; LIB-* adds
release-specific rules.

- [LIB](lib.md)

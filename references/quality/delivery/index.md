---
pack: delivery
applies_when:
  changed_globs: ["**/pyproject.toml", "**/package.json", "**/go.mod", "**/requirements*.txt", "**/*.config.*", "**/config/**", "**/README*", "**/docs/**"]
  task_types: [add-dependency, change-config, docs]
provides_rules: [DEP, CFG, DOC]
---

# Delivery pack

Dependencies, configuration, and documentation hygiene.

- [DEP](dep.md) — dependencies
- [CFG](cfg.md) — configuration
- [DOC](doc.md) — documentation

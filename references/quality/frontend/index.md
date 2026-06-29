---
pack: frontend
applies_when:
  languages: [typescript, javascript]
  project_types: [frontend]
  changed_globs: ["**/components/**", "web/**", "**/*.tsx", "**/*.jsx"]
  task_types: [ui, accessibility]
provides_rules: [A11Y]
---

# Frontend pack

UI + accessibility. Opt-in for frontend targets.

- [A11Y](a11y.md)

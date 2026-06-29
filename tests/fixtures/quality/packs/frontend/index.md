---
pack: frontend
applies_when:
  languages: [typescript]
  project_types: [frontend]
  changed_globs: ["**/components/**", "web/**"]
  task_types: [ui, accessibility]
provides_rules: [A11Y]
---

# Frontend pack (fixture)

Triggered for UI work. Test fixture only.

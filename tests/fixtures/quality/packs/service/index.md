---
pack: service
applies_when:
  languages: [python, typescript, go]
  project_types: [backend, api]
  changed_globs: ["**/api/**", "**/routes/**", "**/migrations/**"]
  task_types: [add-endpoint, change-api, add-migration]
provides_rules: [API, DATA, OBS, CONC]
---

# Service pack (fixture)

Triggered for backend/api work. Test fixture only.

---
pack: service
applies_when:
  languages: [python, typescript, go]
  project_types: [backend, api, data]
  changed_globs: ["**/api/**", "**/routes/**", "**/controllers/**", "**/migrations/**", "**/models/**"]
  task_types: [add-endpoint, change-api, add-migration, perf]
provides_rules: [API, DATA, OBS, CONC]
---

# Service pack

Backend/service quality. Triggered for API, persistence, observability, and
concurrency work.

- [API](api.md) — contracts
- [DATA](data.md) — persistence
- [OBS](obs.md) — observability
- [CONC](conc.md) — concurrency & reliability

---
pack: perf
applies_when:
  task_types: [perf, optimize]
  changed_globs: ["**/cache/**", "**/queries/**", "**/*hot*"]
provides_rules: [PERF]
---

# Perf pack

Performance discipline. Evidence-gated to avoid AI false positives.

- [PERF](perf.md)

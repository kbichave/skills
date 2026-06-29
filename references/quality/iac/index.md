---
pack: iac
applies_when:
  project_types: [infra]
  changed_globs: ["**/Dockerfile", "**/*.tf", "**/k8s/**", "**/*.yaml", "**/helm/**", "**/docker-compose*.yml"]
  task_types: [infra, deploy]
provides_rules: [IAC]
---

# Infrastructure-as-code pack

Container, Terraform, and k8s misconfiguration. Triggered on IaC file changes.

- [IAC](iac.md)

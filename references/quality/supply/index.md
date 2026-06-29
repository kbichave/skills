---
pack: supply
applies_when:
  changed_globs: ["**/package.json", "**/package-lock.json", "**/pnpm-lock.yaml", "**/go.sum", "**/.github/workflows/**", "**/*.lock"]
  task_types: [add-dependency, change-ci]
provides_rules: [SUPPLY]
---

# Supply-chain pack

Build/dependency provenance and CI integrity. Triggered on manifest/lockfile/CI
changes.

- [SUPPLY](supply.md)

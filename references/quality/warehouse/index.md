---
pack: warehouse
applies_when:
  project_types: [data]
  changed_globs: ["**/*.sql", "**/dbt_project.yml", "**/models/**/*.yml", "**/macros/**", "**/seeds/**", "**/snapshots/**"]
  task_types: [data-model]
provides_rules: [SQL, DBT]
---

# Warehouse pack

Analytics SQL and dbt project conventions. Triggered on `.sql` changes, dbt
project files, or a repo carrying a `dbt_project.yml`.

Scope is the transformation layer: query semantics that are silently wrong,
published-interface discipline, materialization choice, and the dbt conventions
that keep a warehouse maintainable. Application-side persistence (migrations,
transactions, indexes) stays in the `service` pack's `DATA` family; SQL
injection stays in `core`'s `SEC` family.

- [SQL](sql.md)
- [DBT](dbt.md)

Language idioms and rewrite examples: [`../lang/sql.md`](../lang/sql.md).

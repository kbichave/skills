# DBT — Project conventions

### DBT-001: Relations are referenced through `ref()` / `source()`
- **Trigger:** a hard-coded `database.schema.table` in a model, test, or macro.
- **Required behavior:** `ref()` for project models, `source()` for external
  tables. A literal name breaks lineage, breaks environment promotion, and
  removes the model from the DAG's build order.
- **Verification signal:** grep the model body for a dotted three-part name;
  `dbt compile` shows the missing edge.
- **Severity:** BLOCK
- **Enforcer:** reviewer + linter

### DBT-002: Layer discipline is preserved
- **Trigger:** a model or an external consumer reading across more than one
  layer boundary, or reading the landing/raw layer at all.
- **Required behavior:** each model reads the layer directly below it. The raw
  layer is a landing zone, not an interface; anything that needs it gets a
  curated or published model built for the purpose. External systems read only
  the published layer.
- **Verification signal:** reviewer names both layers and the consumer.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### DBT-003: Incremental predicates are guarded by `is_incremental()`
- **Trigger:** an incremental model whose `WHERE` narrows on a watermark.
- **Required behavior:** the predicate sits inside `{% if is_incremental() %}`,
  so a full refresh rebuilds the whole table rather than a single window.
- **Verification signal:** reviewer quotes the predicate; `dbt compile
  --full-refresh` shows the unfiltered query.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### DBT-004: Incremental config appears only on incremental models
- **Trigger:** `unique_key` or `incremental_strategy` in a config where
  `materialized` is not `incremental`.
- **Required behavior:** remove the dead keys. They are silently ignored, so
  they read as a guarantee the model does not provide.
- **Verification signal:** reviewer quotes the config block.
- **Severity:** WARN
- **Enforcer:** reviewer

### DBT-005: `unique_key` is real columns, date column first
- **Trigger:** an incremental model's `unique_key`.
- **Required behavior:** a list of actual columns, not a concatenated
  expression, ordered with the date/partition column first. Warehouses keep
  per-micro-partition min/max metadata per column, so a date-leading key lets
  the merge prune partitions instead of scanning the table.
- **Verification signal:** reviewer quotes the key; query profile shows
  partitions scanned.
- **Severity:** WARN
- **Enforcer:** reviewer

### DBT-006: Materialization is justified
- **Trigger:** a new model, or a materialization change.
- **Required behavior:** the choice fits the model's job. A view that is a
  verbatim projection of one other model should not exist; a large table read
  by an external consumer should be incremental rather than rebuilt; an
  intermediate step used once should be ephemeral.
- **Verification signal:** reviewer states the row count, refresh cost, or
  consumer that drives the choice.
- **Severity:** WARN
- **Enforcer:** reviewer

### DBT-007: New model keys carry `unique` and `not_null` tests
- **Trigger:** a new model, or a change to a model's grain.
- **Required behavior:** the grain is declared and tested. An untested grain is
  an assumption that fan-out will eventually break.
- **Verification signal:** the schema file's tests; `dbt test` passes.
- **Severity:** WARN
- **Enforcer:** reviewer + test

### DBT-008: Discrete-valued columns carry `accepted_values`
- **Trigger:** a status, type, code, flag, or category column.
- **Required behavior:** an `accepted_values` test listing the exhaustive set,
  sourced from the upstream vendor's documentation where one exists, so a new
  upstream value fails the build instead of leaking into a dashboard.
- **Verification signal:** the schema file's tests.
- **Severity:** WARN
- **Enforcer:** reviewer + test

### DBT-009: Packaged tests over hand-rolled equivalents
- **Trigger:** a bespoke singular test, or stacked tests that assert the same
  thing.
- **Required behavior:** use the packaged test where one exists (`dbt_utils`,
  `dbt_expectations`) and drop redundant stacking, such as a `not_null`
  alongside a type assertion that already implies it.
- **Verification signal:** reviewer names the packaged test and links its docs.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### DBT-010: Every column is documented
- **Trigger:** a model's schema `.yml`.
- **Required behavior:** a model-level `description:` and a `description:` on
  every column, not only the columns that happen to carry tests. Cross-link
  sibling models with dbt's doc-link syntax so the catalog renders them.
- **Verification signal:** reviewer diffs the model's column list against the
  documented set.
- **Severity:** WARN
- **Enforcer:** reviewer

### DBT-011: Schema `.yml` entries match real models
- **Trigger:** a model or column name in a `.yml` file.
- **Required behavior:** the name resolves to an existing model file and an
  existing column. dbt does not fail on a stale entry, so it silently stops
  testing.
- **Verification signal:** `dbt parse` / `dbt ls`; reviewer greps for the model
  file.
- **Severity:** WARN
- **Enforcer:** reviewer + linter

### DBT-012: Repetitive column blocks are generated by a jinja loop
- **Trigger:** three or more near-identical column expressions differing only
  by name or literal.
- **Required behavior:** a `{% for %}` over one list. Where a column list is
  already declared in a jinja variable, the SQL body iterates that variable
  rather than restating the names, since nothing keeps two hand-written copies
  in sync.
- **Verification signal:** reviewer quotes the repeated block and the duplicate
  list.
- **Severity:** WARN
- **Enforcer:** reviewer

### DBT-013: No redundant `alias` config
- **Trigger:** `alias=` in a model config.
- **Required behavior:** remove it where it restates the file name, which dbt
  already uses to name the relation. Keep it only where the relation name must
  differ from the file name, and say why.
- **Verification signal:** reviewer compares the alias to the file name.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### DBT-014: Warehouse DDL run outside dbt is idempotent
- **Trigger:** a setup script issuing `CREATE STORAGE INTEGRATION`,
  `CREATE STAGE`, `CREATE WAREHOUSE`, or grants.
- **Required behavior:** `IF NOT EXISTS` or `CREATE OR ALTER`, so a rerun does
  not replace an object whose identity other systems depend on. Recreating a
  storage integration invalidates the cloud-side trust relationship.
- **Verification signal:** reviewer quotes the DDL; the script runs twice
  cleanly.
- **Severity:** BLOCK
- **Enforcer:** reviewer

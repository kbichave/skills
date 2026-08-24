# SQL — Analytics query semantics

Rewrite examples for every rule here live in
[`../lang/sql.md`](../lang/sql.md).

### SQL-001: No `SELECT *` across a published interface
- **Trigger:** `SELECT *` in a model that another team, a BI tool, an external
  system, or a serving path reads.
- **Required behavior:** columns listed explicitly, so an upstream schema
  change cannot silently reshape a consumer's contract. `* EXCLUDE (...)` is
  acceptable inside internal layers where the wildcard is deliberate.
- **Verification signal:** reviewer names the model's layer and the consumer.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### SQL-002: `NOT IN` never takes a nullable subquery
- **Trigger:** `NOT IN (SELECT col ...)` where `col` is nullable.
- **Required behavior:** use `NOT EXISTS` or an anti-join. A single NULL in the
  subquery makes the whole predicate return no rows, silently.
- **Verification signal:** reviewer cites the column's nullability; a row-count
  test before and after.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### SQL-003: Queries are built by the templating layer, not string concatenation
- **Trigger:** SQL assembled with `+`, f-strings, `.format()`, or `%`.
- **Required behavior:** jinja/dbt templating, a query builder, or bound
  parameters. Concatenation invites injection and defeats every SQL linter.
- **Verification signal:** grep for the concatenation; linter cannot parse the
  string form.
- **Severity:** BLOCK
- **Enforcer:** reviewer + linter

### SQL-004: Pass-through CTEs are deleted
- **Trigger:** a CTE whose body is `SELECT * FROM <one source>` with no filter,
  join, or projection change.
- **Required behavior:** reference the source directly. An alias-only CTE adds
  a name to learn and hides nothing.
- **Verification signal:** reviewer quotes the CTE body.
- **Severity:** WARN
- **Enforcer:** reviewer

### SQL-005: Booleans stay boolean
- **Trigger:** `CASE WHEN <predicate> THEN 1 ELSE 0 END`, or `MAX(<pred>::INT)`
  used as an any-true aggregate.
- **Required behavior:** return the predicate itself, cast only where the
  consumer genuinely needs a number. Use the warehouse's boolean aggregate
  (`BOOLOR_AGG`, `BOOL_OR`) rather than `MAX(...::INT)`.
- **Verification signal:** reviewer quotes the `CASE` expression.
- **Severity:** WARN
- **Enforcer:** reviewer

### SQL-006: `GROUP BY` and `ORDER BY` name columns, never ordinals
- **Trigger:** `GROUP BY 1, 2` or `ORDER BY 3`.
- **Required behavior:** spell the column names, so reordering the select list
  cannot silently regroup the result.
- **Verification signal:** reviewer quotes the clause.
- **Severity:** WARN
- **Enforcer:** reviewer + linter

### SQL-007: No non-deterministic functions in a table- or view-materialized model
- **Trigger:** `CURRENT_TIMESTAMP`, `GETDATE()`, `RANDOM()` in a model that is
  not incremental or ephemeral.
- **Required behavior:** either the value is meaningless (a table-materialized
  `CURRENT_TIMESTAMP` records only the last refresh) and is removed, or the
  intent is a load timestamp and it is named as one.
- **Verification signal:** reviewer names the model's materialization.
- **Severity:** WARN
- **Enforcer:** reviewer

### SQL-008: No `ORDER BY` in a view or a model body
- **Trigger:** a trailing `ORDER BY` in a model that is not doing top-N or
  windowed selection.
- **Required behavior:** drop it. Ordering is not preserved through downstream
  reads in a columnar warehouse, so the sort is cost without a guarantee.
- **Verification signal:** reviewer quotes the clause.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### SQL-009: Equi-joins use `USING` where the key names match
- **Trigger:** `JOIN b ON a.key = b.key` with identical column names.
- **Required behavior:** `JOIN b USING (key)`, which also collapses the
  duplicated key column in the output.
- **Verification signal:** reviewer quotes the join.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### SQL-010: No redundant defensive wrappers
- **Trigger:** `COALESCE` on an expression that cannot be NULL, `ABS` on a
  value already known non-negative, `* 1.0` where the operand is already
  floating point, nested `COALESCE` of the same expression.
- **Required behavior:** remove the wrapper, or state the nullability
  assumption that makes it necessary.
- **Verification signal:** reviewer cites the column's nullability or the
  expression that cannot return NULL.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### SQL-011: Date arithmetic avoids redundant casts
- **Trigger:** `CAST(GETDATE() AS date)` or a `DATEADD` chain where interval
  arithmetic on `CURRENT_DATE` reads directly.
- **Required behavior:** prefer `CURRENT_DATE - INTERVAL '90 days'`. Where the
  warehouse's semantics differ, cite the vendor documentation.
- **Verification signal:** reviewer links the warehouse date-function docs.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### SQL-012: Trailing comma on the last item of a maintained list
- **Trigger:** a select list, column list, or config list that will grow.
- **Required behavior:** trailing comma where the dialect permits it
  (Snowflake, BigQuery, DuckDB do), so adding the next entry produces a
  one-line diff and preserves `git blame` on the previous last line.
- **Verification signal:** reviewer; the formatter where it is configured.
- **Severity:** ADVISE
- **Enforcer:** reviewer + linter

> **Language ref for the `code-reviewer` agent and the `data-eng-reviewer` panel expert.** Enforceable rules: [`../warehouse/sql.md`](../warehouse/sql.md) (`SQL-*`) and [`../warehouse/dbt.md`](../warehouse/dbt.md) (`DBT-*`). This file holds the rewrites; the pack holds the standards.
> **Default dialect: Snowflake.** Detect the real one from `dbt_project.yml` / the profile / the connector before flagging syntax, and read [Dialect](#dialect) first. Portable rewrites are marked; Snowflake-only ones are labelled.

# SQL / dbt Review Guide

## Contents

- [Dialect](#dialect)
- [Query semantics](#query-semantics)
- [Readability](#readability)
- [Published-interface discipline](#published-interface-discipline)
- [dbt materialization](#dbt-materialization)
- [dbt jinja](#dbt-jinja)
- [dbt tests and docs](#dbt-tests-and-docs)
- [Review checklist](#review-checklist)

---

## Dialect

Establish the dialect before flagging any syntax. Read `dbt_project.yml` for
the `profile`, then the adapter in `packages.yml` / `requirements` /
`profiles.yml` (`dbt-snowflake`, `dbt-bigquery`, `dbt-postgres`, `dbt-duckdb`).
Say which one you found in your `summary`.

### Snowflake (the default assumed here)

Behavior this guide relies on:

| Feature | Use |
|---|---|
| Micro-partition min/max metadata per column | why a date-leading `unique_key` prunes (`DBT-005`) |
| `BOOLOR_AGG` / `BOOLAND_AGG` | boolean aggregates without an integer round-trip (`SQL-005`) |
| `SELECT * EXCLUDE (col, ...)` | terse projection where a wildcard is deliberate (`SQL-001`) |
| Trailing comma in a `SELECT` list | why jinja loops need no `loop.last` comma guard (`SQL-012`) |
| `QUALIFY` | dedupe on `ROW_NUMBER()` without a wrapping subquery |
| `INTERVAL` arithmetic on `CURRENT_DATE` | date math without a cast (`SQL-011`) |
| `MERGE` non-determinism | multiple source rows matching one target row is an error only when the account's non-deterministic-merge guard is on; otherwise it silently picks one. Check the incremental model's dedupe. |

Snowflake specifics worth flagging beyond the pack rules:

- **Clustering is not an index.** A clustering key on a small or evenly-loaded
  table costs reclustering credits and buys nothing. Ask for the query profile
  before accepting one.
- **`ORDER BY` in a model is discarded** by downstream reads (`SQL-008`);
  a query's output order is guaranteed only by the outermost `ORDER BY` at read
  time.
- **Case sensitivity.** Unquoted identifiers fold to upper case; quoted ones do
  not. Mixed quoting across models produces join keys that look identical and
  do not match.
- **Warehouse size is not a fix for a bad query.** A finding that recommends
  scaling up needs the query profile showing the bottleneck is genuinely
  compute, not spill or a full scan.

**Verifying Snowflake behavior.** `docs.snowflake.com` is the authoritative
source, and Snowflake ships syntax continuously, so a feature absent from your
training data may well exist now (`CREATE OR ALTER`, newer `EXCLUDE`/`RENAME`
forms, `QUALIFY` edge cases). Do not assert from memory and do not web-search
yourself: set `"needs_verification": true` on the finding and let the
claim-verifier resolve it in the single centralized pass.

### Other dialects

`USING`, `QUALIFY`, `EXCLUDE`, boolean aggregates, and trailing-comma
tolerance all vary. BigQuery has `EXCEPT` rather than `EXCLUDE` and
`BOOL_OR` rather than `BOOLOR_AGG`; Postgres has neither `QUALIFY` nor a
wildcard-exclusion syntax. On a non-Snowflake adapter, flag only what you can
confirm for that dialect, and mark the rest `needs_verification`.

---

## Query semantics

### `NOT IN` with a nullable subquery (`SQL-002`)

One NULL in the subquery makes every row fail the predicate, so the query
returns nothing and no error.

```sql
-- ❌ returns zero rows the moment customer_id is nullable
SELECT * FROM orders
WHERE customer_id NOT IN (SELECT customer_id FROM churned_customers);

-- ✅ NULL-safe
SELECT o.* FROM orders o
WHERE NOT EXISTS (
    SELECT 1 FROM churned_customers c WHERE c.customer_id = o.customer_id
);
```

### Booleans stay boolean (`SQL-005`)

```sql
-- ❌ verbose, and hides that this is a predicate
CASE WHEN e.duration_hours > p.duration_hours_p95 THEN 1 ELSE 0 END AS duration_outlier_flag,

-- ✅ the predicate is the value
(e.duration_hours > p.duration_hours_p95) AS duration_outlier_flag,

-- ✅ only if a consumer genuinely needs an integer
(e.duration_hours > p.duration_hours_p95)::INTEGER AS duration_outlier_flag,
```

Any-true aggregates have a dedicated function; the integer round-trip is not
needed.

```sql
-- ❌
MAX(is_promotional::INT) = 1 AS had_promotion,
-- ✅ Snowflake / BigQuery
BOOLOR_AGG(is_promotional) AS had_promotion,   -- BOOL_OR in BigQuery + DuckDB
```

### Redundant wrappers (`SQL-010`)

Each of these signals a nullability assumption the author did not actually
check. Ask which one it is.

```sql
-- ❌ COALESCE cannot fire: the comparison already returns TRUE/FALSE, never NULL
--    unless promotion_desc is NULL, which the inner COALESCE already handled
COALESCE(COALESCE(fact.promotion_desc, '') != 'Regular Price', FALSE) AS is_promo,
-- ✅
COALESCE(fact.promotion_desc, '') != 'Regular Price' AS is_promo,

-- ❌ ABS on a value that cannot be negative; `* 1.0` on an already-float column
ABS(DATEDIFF('day', start_date, end_date)) AS days,   -- if end_date >= start_date is an invariant, say so
revenue * 1.0 / NULLIF(units, 0) AS unit_price,       -- redundant when revenue is NUMBER/FLOAT
```

### Date arithmetic (`SQL-011`)

```sql
-- ❌ cast to strip a time component that CURRENT_DATE never had
WHERE event_date >= DATEADD('day', -90, CAST(GETDATE() AS date))
-- ✅
WHERE event_date >= CURRENT_DATE - INTERVAL '90 days'
```

### Non-deterministic functions by materialization (`SQL-007`)

`CURRENT_TIMESTAMP` in a table-materialized model records when dbt last ran,
not when the row was true. If that is the intent, name the column
`_dbt_loaded_at`; if it is not, delete it. In a view it re-evaluates on every
read, which is rarely what a "created at" column is meant to convey.

---

## Readability

### Pass-through CTEs (`SQL-004`)

```sql
-- ❌ a name to learn that hides nothing
WITH sites AS (
    SELECT * FROM {{ ref('app_mdm__sites') }}
)
SELECT ... FROM sites

-- ✅
SELECT ... FROM {{ ref('app_mdm__sites') }} AS sites
```

A CTE earns its name when it filters, reshapes, joins, or is referenced more
than once.

### `USING` over `ON` for matching key names (`SQL-009`)

```sql
-- ❌
FROM fact_sales f
JOIN dim_site d ON f.site_id = d.site_id
JOIN dim_date t ON f.date_key = t.date_key

-- ✅ also collapses the duplicated key column in the output
FROM fact_sales f
JOIN dim_site d USING (site_id)
JOIN dim_date t USING (date_key)
```

`USING` needs identical column names on both sides. Keep `ON` when the names
differ or the predicate is not a simple equality.

### Ordinals in `GROUP BY` (`SQL-006`)

```sql
-- ❌ reordering the select list silently regroups the result
GROUP BY 1, 2, 3
-- ✅
GROUP BY site_id, product_category, business_date
```

### Trailing commas (`SQL-012`)

Snowflake, BigQuery, and DuckDB all accept a trailing comma in a select list.
Where the dialect allows it, the last maintained item gets one, so the next
addition is a one-line diff and `git blame` on the previous last line survives.

```sql
SELECT
    site_id,
    business_date,
    gross_margin,          -- ← trailing comma retained
FROM ...
```

This is also why a jinja loop does not need `{% if not loop.last %},{% endif %}`
guards on those dialects.

---

## Published-interface discipline

### `SELECT *` (`SQL-001`)

The published layer is a contract. A wildcard forwards every upstream schema
change straight into consumers.

```sql
-- ❌ in a published model, or a query a serving path issues
SELECT * FROM {{ ref('btr_site_daily') }}

-- ✅ explicit, so upstream can add columns without reshaping the contract
SELECT site_id, business_date, gross_margin FROM {{ ref('btr_site_daily') }}

-- ✅ acceptable inside internal layers where the wildcard is deliberate
SELECT t.* EXCLUDE (_loaded_at, _batch_id) FROM {{ ref('cur_site_daily') }} AS t
```

### Layers (`DBT-002`)

Raw is a landing zone, not an interface: it mirrors upstream and changes when
upstream changes, with no guarantee to anyone. A consumer that needs raw data
needs a curated or published model built for the purpose instead. Reviewing a
query that reaches into raw, name the consumer and ask for the model.

---

## dbt materialization

### Justify the choice (`DBT-006`)

| Situation | Materialization |
|---|---|
| Verbatim projection of one other model | none; delete the model |
| Small, cheap to rebuild, read internally | `view` |
| Referenced repeatedly in one build, not read outside | `ephemeral` |
| Large, appended by date, read externally | `incremental` |
| Rebuilt whole each run, moderate size | `table` |

A view on top of a view that adds nothing is the common case; ask what the
model is for before discussing anything else in the file.

### `unique_key` ordering (`DBT-005`)

```sql
-- ❌ concatenated expression: opaque to the optimizer, no pruning
{{ config(materialized='incremental', unique_key="site_id || '-' || business_date") }}

-- ❌ real columns, but the low-cardinality id leads
{{ config(materialized='incremental', unique_key=['site_id', 'business_date']) }}

-- ✅ date first
{{ config(materialized='incremental', unique_key=['business_date', 'site_id']) }}
```

Columnar warehouses keep per-micro-partition min/max metadata for each column.
A date-leading key lets the merge prune to the partitions the batch touches
instead of scanning the table.

### Incremental guards (`DBT-003`)

```sql
-- ❌ a full refresh rebuilds only the last 3 days
WHERE business_date >= (SELECT MAX(business_date) FROM {{ this }}) - 3

-- ✅
{% if is_incremental() %}
WHERE business_date >= (SELECT MAX(business_date) FROM {{ this }}) - 3
{% endif %}
```

Also check the lookback covers late-arriving data, and that `unique_key`
dedupes what the window re-reads.

### Dead config keys (`DBT-004`)

`unique_key` and `incremental_strategy` are ignored unless `materialized` is
`incremental`. Left behind after a materialization change, they read as a
guarantee the model does not make.

---

## dbt jinja

### Loop over repeated blocks (`DBT-012`)

```sql
-- ❌ eleven near-identical lines; a typo in one is invisible
SUM(CASE WHEN kpi = 'fuel_volume' THEN value END) AS fuel_volume,
SUM(CASE WHEN kpi = 'fuel_margin' THEN value END) AS fuel_margin,
SUM(CASE WHEN kpi = 'store_sales' THEN value END) AS store_sales,
...

-- ✅ the pattern is stated once, deviations become visible
{% set kpis = ['fuel_volume', 'fuel_margin', 'store_sales'] %}
{% for kpi in kpis %}
SUM(CASE WHEN kpi = '{{ kpi }}' THEN value END) AS {{ kpi }},
{% endfor %}
```

Where a column list already exists in a variable, the body iterates the
variable. Two hand-maintained copies of the same list will drift, and nothing
in the build will notice.

### Hard-coded relations (`DBT-001`)

```sql
-- ❌ no lineage edge, no environment promotion, wrong DB in dev
FROM ANALYTICS.CURATED.SITE_DAILY
-- ✅
FROM {{ ref('cur_site_daily') }}
-- ✅ for a table this project does not build
FROM {{ source('pdi', 'site_daily') }}
```

---

## dbt tests and docs

### Document every column (`DBT-010`)

Documenting only the tested columns is the common shortcut. The catalog is the
place a business user answers "what is this column", so a column without a
description is a question routed to the team instead.

### `accepted_values` on discrete columns (`DBT-008`)

```yaml
- name: transaction_type
  description: "Type of the POS transaction, per the vendor's specification."
  tests:
    - accepted_values:
        values: ['SALE', 'REFUND', 'VOID', 'NO_SALE']
```

Ask whether the listed set is exhaustive, and where it came from. Sourced from
the vendor's documentation, this test turns a new upstream value into a build
failure rather than a silent gap in a dashboard.

### Packaged tests (`DBT-009`)

Before accepting a bespoke singular test, check `dbt_utils` and
`dbt_expectations` for the packaged equivalent (`accepted_range`,
`equal_rowcount`, `relationships_where`, `expression_is_true`). Drop stacked
tests that assert the same property twice.

---

## Review checklist

**Semantics**
- [ ] `NOT IN` against a nullable subquery (`SQL-002`)
- [ ] Join keys unique on at least one side, or the fan-out is intended (`DE-JOIN`)
- [ ] Booleans not round-tripped through integers (`SQL-005`)
- [ ] No redundant `COALESCE` / `ABS` / `* 1.0` (`SQL-010`)
- [ ] Non-deterministic functions match the materialization (`SQL-007`)

**Interface**
- [ ] No `SELECT *` in a published model or serving query (`SQL-001`)
- [ ] Nothing reads the raw layer (`DBT-002`)
- [ ] Relations go through `ref()` / `source()` (`DBT-001`)

**Incremental**
- [ ] Predicates guarded by `is_incremental()` (`DBT-003`)
- [ ] `unique_key` is real columns, date first (`DBT-005`)
- [ ] Incremental config absent on non-incremental models (`DBT-004`)
- [ ] Lookback window covers late-arriving data

**Readability**
- [ ] Pass-through CTEs deleted (`SQL-004`)
- [ ] `USING` where key names match (`SQL-009`)
- [ ] `GROUP BY` names, not ordinals (`SQL-006`)
- [ ] Repeated column blocks generated by a loop (`DBT-012`)

**Schema file**
- [ ] Model and every column documented (`DBT-010`)
- [ ] Grain tested with `unique` + `not_null` (`DBT-007`)
- [ ] Discrete columns carry `accepted_values` (`DBT-008`)
- [ ] Entries resolve to real models and columns (`DBT-011`)

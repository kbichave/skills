# Evidence menu

Take the first source that answers the question. Costs are rough. Tool names are
the roles in `references/dq/warehouse-tools.md`; resolve each to this host's tool
there before the first call.

| Need | Source | Cost |
|---|---|---|
| Model SQL and `config()` | Read the `.sql` (2-8 KB) | cheap |
| File path of a model | Grep the model name under `models/` | cheap |
| One model's YAML (tests, severity, `where`, descriptions, meta) | Grep `name: <model>` in `*.yml`, then Read from that line to the next `- name:` | cheap |
| Folder defaults (materialized, database, schema) and vars | Grep the folder or var name in `dbt_project.yml`, then Read that section | cheap |
| A macro the model calls | Grep `macro <name>` under `macros/`, then Read its range | cheap |
| Recent changes | `git log --oneline -15 -- <path>` on the `.sql` and YAML | cheap |
| Tests and their last results, last run, upstream source freshness | `model_health` (skip if the context has it) | cheap |
| Which job builds a node, its schedule, recent runs | context first; else `job_runs` | cheap |
| Why a model is (not) in a job | Grep the model or exposure in `selectors.yml`, then Read that selector | cheap |
| Lineage beyond the context | `lineage` with `depth=1` in the direction needed | cheap |
| Columns and types | context first; else `describe` | cheap |
| Column descriptions | context first; else `INFORMATION_SCHEMA.COLUMNS` comments for named columns | cheap |
| Row count, bytes, last altered | context first; else `<DB>.INFORMATION_SCHEMA.TABLES` | cheap |
| Data shape | one-pass profile (below) | ~2 s |
| A parent's or seed's data | the same profile on its relation from the context | ~2 s |
| Business meaning or a rule not in the context | the domain context; never fetch knowledge pages yourself | n/a |

Never: a model-details call that returns full compiled SQL when the file is in
the repo, a whole YAML file, `SELECT *`, or an unbounded scan.

## Triage

Used when a run covers more than one node: the review-panel data tier (changed
models plus the lineage they reach) and `dq-investigate`. The orchestrator
triages before any hypothesizer runs; each picked node gets one `dq-hypothesizer`
with the hand-off in `references/dq/scope.md`.

### Score

Take every node in the model context's lineage: models in scope, upstream models,
direct children, raw sources and seeds. Score each from what the context already
says, without new calls:

| Signal | Weight |
|---|---|
| model in scope (changed, or named by the target) | always examine |
| no build job, or last run far older than its schedule | high |
| documented known issue on it or its table | high |
| grain or key mismatch in the domain context | high |
| feeds an exposure or a named consumer | high |
| joins, unions, incremental logic, mapping seeds | medium |
| no tests | medium |
| raw source with no freshness check | medium |
| view that only renames or passes columns through | low |

### Skip nodes that carry the same data

Examine one node of each group and mark the others "same data as <node>":

- twin copies of one object: the same model in another layer or architecture
  (a V1 and a V2 relation, or a mart copy of a business-logic model), named as
  one object in the domain context's routes or by the same model name with a
  layer prefix;
- views or models that only select, rename, or cast a parent's columns, with no
  join, filter, or aggregation. Examine the side with logic, never the
  passthrough;
- dev and UAT copies of a production relation.

A twin is examined on its own only when the domain context or the lineage shows
it is built differently (different job, filter, or consumers).

Always examine the direct parent of a model in scope when the model transforms
it (joins, filters, aggregates, incremental logic): reconciliation needs both
sides.

### Raw sources

A raw source never gets its own hypothesizer and is never skipped silently. It
goes in the hand-off of the examined model that reads it, which writes the
raw-versus-model reconciliation. Mark it "checked via <model>".

### Pick

Examine every model in scope, then the highest scores among the rest, nearest
to the changed or named models first, up to the caller's cap (review-panel data
tier 4, `dq-investigate` 8). State the cut: list every node left out with its
score and the reason ("cap reached", "same data as <node>", "passthrough view").

## Size first

Before any preview, know the table's row count and bytes (the context's lineage
table, else `INFORMATION_SCHEMA.TABLES`). Pick the query shape by size. `LIMIT`
only trims returned rows; it does not make an aggregate faster.

| Rows | Preview shape |
|---|---|
| any size | `COUNT(*)`, `MIN(col)`, `MAX(col)` with **no WHERE** are answered from metadata, instantly. Use them for the latest date and row count |
| under 50M | a `where` on the last 30 days is fine |
| 50M to 1B | last 1 to 3 days on the date or cluster column, or `tablesample system (1)` |
| over 1B | `tablesample system (0.1)` (block sampling) for shape; a single recent day only if the table is clustered by date; `LIMIT 20` for row detail |

Never use `tablesample bernoulli` or `row` on a large table: it reads every row.
Keep each preview under about 10 seconds. A join between two large tables is
never a preview: put it in the hypothesis's test SQL instead. If a preview is
slow, sample harder next time rather than widening the filter.

## Query templates

Check column names first (`describe` or the context): date columns differ
between models.

Column descriptions for named columns:

```sql
select column_name, data_type, comment
from <DB>.INFORMATION_SCHEMA.COLUMNS
where table_schema = '<SCHEMA>' and table_name = '<TABLE>'
  and column_name in ('<C1>', '<C2>')
```

Size and freshness:

```sql
select row_count, bytes, last_altered, comment
from <DB>.INFORMATION_SCHEMA.TABLES
where table_schema = '<SCHEMA>' and table_name = '<TABLE>'
```

One-pass profile (one table scan, last 30 days):

```sql
select count(*) as n,
       approx_count_distinct(<key_cols concatenated>) as distinct_keys,
       min(<date_col>) as min_date, max(<date_col>) as max_date,
       count_if(<col_a> is null) as null_a,
       count_if(<col_b> is null) as null_b,
       approx_count_distinct(<entity_col>) as entities
from <DB>.<SCHEMA>.<TABLE>
where <date_col> >= dateadd('day', -30, current_date)
```

Values of a categorical column:

```sql
select <col>, count(*) as n
from <DB>.<SCHEMA>.<TABLE>
where <date_col> >= dateadd('day', -30, current_date)
group by 1 order by n desc limit 20
```

Rows per day (gaps, drops, partial days):

```sql
select <date_col>::date as d, count(*) as n, approx_count_distinct(<entity_col>) as entities
from <DB>.<SCHEMA>.<TABLE>
where <date_col> >= dateadd('day', -30, current_date)
group by 1 order by 1
```

For large tables, replace the date filter with the sampling shape from "Size first".

Raw versus model, fast (for the test SQL; never run as a preview). Compare a
few fixed days of different ages, so both "recent rows not yet final" and "old
rows never corrected" show up, on a sample of keys, so it stays quick on large
shares:

```sql
with days as (
  select dateadd('day', -d, current_date) as day
  from (select column1 as d from values (2), (7), (30), (90))
), raw as (
  select <key>, <date_col>::date as day, <measure_a>, <measure_b>
  from <RAW_DB>.<SCHEMA>.<RAW_TABLE>
  where <date_col>::date in (select day from days)
    and abs(hash(<key>)) % 100 < 5   -- about 5% of keys
), model as (
  select <key>, <date_col>::date as day, <measure_a>, <measure_b>
  from <DB>.<SCHEMA>.<MODEL_TABLE>
  where <date_col>::date in (select day from days)
    and abs(hash(<key>)) % 100 < 5
)
select r.day,
       count(*) as keys,
       count_if(m.<key> is null) as missing_in_model,
       count_if(m.<measure_a> is null and r.<measure_a> is not null) as a_null_in_model,
       count_if(m.<measure_a> is distinct from r.<measure_a>) as a_differs,
       count_if(m.<measure_b> is distinct from r.<measure_b>) as b_differs
from raw r left join model m on m.<key> = r.<key> and m.day = r.day
group by 1 order by 1
```

Holds if older days still differ (rows never corrected) or recent days differ
far more than old ones (rows loaded before they were final). Use the model's
own grain: aggregate the raw side first when the model is daily and the raw is
hourly. List every measure the same logic builds.

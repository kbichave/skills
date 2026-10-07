# Pattern catalog

Classes of silent error that pass ordinary tests. `data-eng-reviewer` greps the
code signatures statically; `dq-hypothesizer` and `dq-prover` run the data
recipes under the `--data` tier. Each entry gives the code signature to grep for, the data signature to
query, and a recipe. Recipes are Snowflake SQL. `{relation}`, `{entity_key}`,
`{obs_date}`, and `{col}` are placeholders. Recipes marked *verified* were run
against a production relation on 2026-09-30.

A pattern is a lens; the scope comes from the run. When the data shows
something no pattern names, write the hypothesis anyway.

## Fill-forward

Code: `LAST_VALUE(...) IGNORE NULLS`, `COALESCE(x, LAG(x))`, a `locf` macro, or
any fill applied where missing means "unknown" or "none" and never "same as
yesterday", with no `is_filled` flag. It pairs with **frozen history**: a NULL
frozen upstream becomes a confident wrong value downstream.

Data: runs of identical values far longer than the column's natural persistence.
Compare p99 run length with what the domain allows.

*Verified* run-length recipe:

```sql
with ordered as (
    select {entity_key} as entity_key, {obs_date} as obs_date, {col} as val,
           iff(val is not distinct from
               lag(val) over (partition by entity_key order by obs_date), 0, 1) as is_change
    from {relation}
    where {obs_date} >= dateadd('day', -365, current_date)
),
runs as (
    select entity_key, obs_date,
           sum(is_change) over (partition by entity_key order by obs_date
                                rows unbounded preceding) as run_id
    from ordered
),
run_lengths as (
    select entity_key, run_id, count(*) as run_len,
           min(obs_date) as run_start, max(obs_date) as run_end
    from runs
    group by 1, 2
)
select approx_percentile(run_len, 0.5)  as p50,
       approx_percentile(run_len, 0.99) as p99,
       max(run_len)                     as max_run,
       count(*)                         as n_runs
from run_lengths;
```

To list the offenders, select from `run_lengths` ordered by `run_len desc` with
`limit 20`.

## Zero-fill

Code: `COALESCE(x, 0)`, `NVL(x, 0)`, `ZEROIFNULL(x)` on a measure where no row
means "not observed".

Data: the share of zeros in the model is higher than the share of zeros plus
nulls in its parent, or zeros cluster on days a source was late.

```sql
select {obs_date}::date as d,
       count_if({col} = 0) / count(*) as zero_share,
       count(*)                       as n
from {relation}
where {obs_date} >= dateadd('day', -90, current_date)
group by 1
order by zero_share desc
limit 20;
```

## Fanout

Code: a join whose right side is not unique on the join key; `SELECT DISTINCT`
used to hide duplicates.

Data: duplicates on the documented grain; sums higher than the parent's.

*Verified* grain recipe:

```sql
select count(*)                          as n_rows,
       count(distinct {entity_key}, {obs_date}) as n_keys,
       n_rows - n_keys                   as n_dupes
from {relation};
```

Run it on both sides of a join and on the output; the output should have no more
keys than the driving side.

## Series gap

Data: an entity that should have one row per period is missing some. The
table has fewer (entity, period) pairs than the expected series. Build the
series from the entities seen in the window and a generated calendar, then
left join the table. For an hourly grain swap `'day'` for `'hour'` and raise
`rowcount` to 24 times the days.

```sql
with entities as (
    select distinct {entity_key} as entity_key
    from {relation}
    where {obs_date} >= dateadd('day', -90, current_date)
),
periods as (
    select dateadd('day', -seq4(), current_date)::date as period
    from table(generator(rowcount => 90))
),
expected as (
    select e.entity_key, p.period from entities as e cross join periods as p
)
select count(*)                       as n_missing,
       count(distinct x.entity_key)   as n_entities_with_gaps,
       min(x.period)                  as first_gap,
       max(x.period)                  as last_gap
from expected as x
left join {relation} as r
  on r.{entity_key} = x.entity_key and r.{obs_date}::date = x.period
where r.{entity_key} is null;
```

To list the offenders, select `entity_key, period` from the same join ordered
by `period desc` with `limit 50`.

## Tie-break

Code: `ROW_NUMBER() ... QUALIFY rn = 1` where the `ORDER BY` columns do not make
the winner unique within the partition, so the kept row changes between runs.

*Verified* recipe (counts rows that tie for first place):

```sql
with ranked as (
    select {order_col} as order_col,
           count(*) over (partition by {partition_cols}, {order_col}) as n_at_value,
           max({order_col}) over (partition by {partition_cols})       as top_value
    from {parent_relation}
)
select count(*) as n_tied_rows
from ranked
where order_col = top_value and n_at_value > 1;
```

## Frozen history

Code: incremental filters that insert a key once and never re-read it
(`WHERE key NOT IN (SELECT key FROM {{ this }})`, `> (SELECT MAX(...) FROM
{{ this }})` with no lookback), or a lookback shorter than the source's
late-arrival or restatement lag.

Data: for a recent window, compare the model with a fresh read of its parent;
rows that differ were corrected upstream and never picked up.

```sql
select count(*) as n_stale_rows
from {relation} as m
join {parent_relation} as p
  on m.{entity_key} = p.{entity_key} and m.{obs_date} = p.{obs_date}
where m.{obs_date} >= dateadd('day', -30, current_date)
  and m.{col} is distinct from p.{col};
```

## Stale source

Data: a raw schema stopped loading while downstream keeps building on the last
good day. Compare `LAST_ALTERED` and the maximum load timestamp with the
expected cadence.

```sql
select table_schema, table_name, last_altered, row_count
from {database}.INFORMATION_SCHEMA.TABLES
where last_altered < dateadd('day', -7, current_timestamp)
order by last_altered
limit 100;
```

## Wrong environment

Code: a production model's source or ref resolving to a dev or UAT database or
schema.

Data: the production transformation user reading non-production objects.
*Verified* recipe:

```sql
select qh.user_name, qh.role_name,
       split_part(f.value:"objectName"::string, '.', 1) as database_name,
       count(*) as n_reads
from SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY as ah
join SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY as qh on qh.query_id = ah.query_id,
     lateral flatten(ah.base_objects_accessed) as f
where ah.query_start_time >= dateadd('day', -7, current_timestamp)
  and qh.start_time      >= dateadd('day', -7, current_timestamp)
  and qh.user_name = '{prod_transform_user}'
  and (f.value:"objectName"::string ilike '%DEV%'
       or f.value:"objectName"::string ilike '%UAT%')
group by 1, 2, 3
order by n_reads desc
limit 50;
```

The `ilike` filters also match names like `DEVICE` or `EVALUATION`; read the
object names before calling a hit.

## Non-reproducible

Code: `CURRENT_DATE`, `CURRENT_TIMESTAMP`, or `GETDATE()` in model logic (not in
an incremental filter), so rebuilding a past day gives a different answer.
Prefer the run's logical date.

## Drift

Data:
- new duplicates on the documented grain
- unit changes: gallons and barrels, cents and dollars
- date basis changes: UTC and local dates
- codes remapped in a seed or mapping table without history

Check a measure's distribution before and after each seed or mapping commit
(`git log` on the seed file).

## PR schema drift

Data: CI built the pull request into its own schema, and the PR relation and
the production relation disagree for the same window. Run the same aggregates
on both and keep the days that differ in any column.

```sql
with prod as (
    select {obs_date}::date as d, count(*) as n_rows,
           count(distinct {entity_key}) as n_keys,
           sum({col}) as total, count_if({col} is null) as n_null
    from {prod_relation}
    where {obs_date} >= dateadd('day', -14, current_date)
    group by 1
),
pr as (
    select {obs_date}::date as d, count(*) as n_rows,
           count(distinct {entity_key}) as n_keys,
           sum({col}) as total, count_if({col} is null) as n_null
    from {pr_relation}
    where {obs_date} >= dateadd('day', -14, current_date)
    group by 1
)
select coalesce(prod.d, pr.d) as d,
       prod.n_rows, pr.n_rows as pr_n_rows,
       prod.n_keys, pr.n_keys as pr_n_keys,
       prod.total,  pr.total  as pr_total,
       prod.n_null, pr.n_null as pr_n_null
from prod
full outer join pr on prod.d = pr.d
where prod.n_rows is distinct from pr.n_rows
   or prod.n_keys is distinct from pr.n_keys
   or prod.total  is distinct from pr.total
   or prod.n_null is distinct from pr.n_null
order by d desc
limit 50;
```

A difference the pull request describes is the change working; a difference
it does not describe is a finding. A PR relation whose latest day is older
than production's means CI built from a stale source, so compare only the
days both hold.

## Silent filter

Code: a `WHERE` or `INNER JOIN` that drops unmapped entities or new categories,
with no count of what fell out.

```sql
select count(*) as n_dropped
from {parent_relation} as p
left join {mapping_relation} as m on p.{key} = m.{key}
where m.{key} is null;
```

## Build history

Data: a model's recent builds, from the warehouse's own query history. dbt
tags every statement it runs with a JSON comment that carries the node id, so
the model's builds can be found without the job system. *Verified* recipe
(Snowflake; the view lags by up to 45 minutes):

```sql
select start_time::date                 as run_day,
       execution_status,
       left(error_message, 200)         as error_message,
       count(*)                         as n_statements
from SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
where start_time >= dateadd('day', -14, current_timestamp)
  and query_text ilike '%"node_id": "model.{project}.{model}"%'
group by 1, 2, 3
order by run_day desc
limit 50;
```

Snapshots use `snapshot.{project}.{name}` as the node id. A failed status on
several days with the same error is a build that nobody fixed; a model with no
statements in its cadence window did not run at all.

## Dead check

A check that cannot fire on the failure it exists for:

- `severity: warn` on a test nobody reads
- a `where:` or `row_condition:` that excludes the broken rows
- a not-null test on a column that is filled before the test runs
- a monitor threshold the data never approaches
- a monitor on a dev or retired table

`monitor-reviewer` decides whether a monitor or test would fire instead.

### Dead test

Data: a test that has not run inside its model's cadence window. dbt tags
test statements with `test.{project}.{test_name}.<hash>` as the node id, so
the build-history view shows when each test last ran.

```sql
select start_time::date                 as run_day,
       execution_status,
       count(*)                         as n_statements
from SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
where start_time >= dateadd('day', -30, current_timestamp)
  and query_text ilike '%"node_id": "test.{project}.{test_name}%'
group by 1, 2
order by run_day desc
limit 50;
```

A test with no statements inside the model's cadence window is dead: the
model has been rebuilt since the test last looked at it. A test whose only
recent runs failed, with nobody acting on the failure, is dead too.

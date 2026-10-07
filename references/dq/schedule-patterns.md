# Schedule pattern catalog

Ways a schedule goes silently wrong, or costs more than it needs to, while every
run succeeds. `data-eng-reviewer` reads the **Graph** signatures statically when
a diff touches `dbt_project.yml`, selectors, job definitions or exposures; the
**Evidence** recipes need the `--data` tier. Each entry gives the
signature in the job graph, the evidence that proves it, and the usual change.
Recipes are Snowflake SQL; `{relation}`, `{parent}`, `{child}`, and
`{transform_user}` are placeholders. None is marked *verified* yet: run it once
against production and mark it before quoting its numbers as typical.

A pattern is a lens, not a scope. When a timeline shows something no pattern
names, write the hypothesis anyway.

## Race

Graph: job B builds a child of a model job A builds; B starts on a cron that
falls before A's p95 finish, or on no trigger tied to A at all.

Evidence: on how many of the last 14 days did the child's write come before
the parent's write for that day ("Layer lag" below)? Each such day the child
served the previous cycle's parent. One day is a suspect; a repeating pattern is
proven.

Change: a completion trigger on A, or a cron after A's p95 finish plus the
deployment's buffer.

## Cron offset

Graph: B's cron is A's cron plus a fixed number of minutes, standing in for "after
A". It works until A runs long.

Evidence: A's duration distribution (`list_jobs_runs`); the days A ran past the
offset are the days B raced.

Change: a completion trigger on A. Keep a cron only when B also needs a
wall-clock floor (a source that lands at a fixed time).

## Overlap

Graph: one model in the node sets of two or more scheduled jobs.

Evidence: both jobs' `run_results.json` list the model. Cost: the builds per
week beyond what its most frequent consumer needs, times credits per build. It
matters most for incremental models and snapshots: two writers at once can
duplicate or lose rows, and a full refresh in one job undoes the other's
incremental state. Check whether the two runs ever overlapped in time.

Change: one owning job; the other gets an `--exclude`, or reads the model
without building it.

## Duplicate job

Graph: two production jobs with the same steps, or the same node set, on
triggers that both fire: the same cron, crons that overlap, or one chained on
the other.

Evidence: the step strings and the node sets from `run_results.json`, and run
history showing both ran in the same window. Cost: the cheaper job's credits
per week.

Change: retire one, after naming who triggers it by hand. Two jobs with the same
steps on different calendar windows (month or quarter open and close) are not
duplicates.

## Upstream rebuild

Graph: a step selects with a leading `+` (or `parents: true`), so the job also
rebuilds ancestors that another job owns. Often the cause of an overlap.

Evidence: the job's node set includes models outside its own folder or unit.
Cost: those ancestors' credits per build, times the job's runs per week.

Change: drop the `+`, or exclude the ancestors' owning paths, and chain on
their owning job instead.

## Orphan

Graph: a table or incremental model that no scheduled job builds. The deploy or
CI job may build it once per merge, which looks like a schedule until merges
stop.

Evidence: the model is in no scheduled job's node set, and its write history
shows writes only at merge times.

Change: add it to the job that builds its parents, or to the job serving its
consumer.

## Over-build

Graph: a job runs more often than its parents change or its consumers read.

Evidence: write history shows the parents changed on fewer cycles than the job
ran; or the consumer reads once a day while the job runs hourly. Count the runs
that rebuilt unchanged inputs over 14 days. Cost: those runs times the job's
credits per run.

Change: a slower cron, a completion trigger on the parent's job, or
state-aware building where the deployment supports it. Report runs saved per
week.

## Under-build

Graph: a consumer with a deadline whose effective freshness at the deadline is
older than it accepts.

Evidence: per day, the consumer's deadline against the oldest ancestor write
its last build read. Count the days it missed.

Change: work the cron back from the deadline: deadline minus the deployment's
buffer minus the job's p95 duration, and check that every parent's job finishes
before that start.

## Broken chain

Graph: B runs on completion of A, A failed or was cancelled, and B did not run.
Nothing alerts on a run that never started.

Evidence: days with an A run in `error` or `cancelled` and no B run after it.

Change: alerting on A that names B's consumers, and an explicit note on B of
which job it chains on.

## Cross-environment chain

Graph: a job in a non-production environment (development, test, backfill) runs
on completion of a production job, or the reverse.

Evidence: the completion trigger's upstream job id belongs to another
environment. A non-production job then runs on every production cycle,
spending compute and possibly writing where production readers look; a
production job waiting on a non-production one depends on something nobody
watches.

Change: confirm the intent with the job's owner. Keep it with a written reason,
or move the job to a schedule in its own environment.

## Scheduled full refresh

Graph: a scheduled step passes `--full-refresh` to incremental models or
snapshots.

Evidence: the step string and the node set's materializations. A snapshot
loses its history; an incremental model pays a full rebuild every cycle.

Change: drop the flag from the scheduled step; keep full refreshes on a manual
job.

## Dead job

Graph: an active schedule whose node set is empty, all views, or only models
another job already builds; or a paused job with no run in 90 days.

Evidence: `run_results.json` and the run history.

Change: retire it, after naming who triggers it by hand.

## Expensive full rebuild

Graph: a table model, or a scheduled step with `--full-refresh`, among the top
credits per week, whose rows mostly do not change between runs.

Evidence: credits per build ("Cost per model build"), runs per week, and the
share of rows that changed between two consecutive builds (rows by date column,
or a hash comparison on a sample). An append-mostly fact rebuilt in full every
hour is the usual case.

Change: an incremental materialization with a lookback window for late rows,
or a slower cron for the full rebuild with an incremental run between. Hand the
SQL change to `data-eng-reviewer`; state the saving here.

## Per-run overhead

Graph: a frequent job that also generates docs or source freshness on every
run (`generate_docs`, `run_generate_sources`), or runs every test on every run.

Evidence: from `run_results.json`, the step durations that are not model builds:
`docs generate` covers the whole project, not the job's models. Multiply by runs
per week.

Change: docs and source freshness once a day in one job; tests on large tables
at the consumer's cadence rather than on every build, keeping the key and grain
tests that hold data back.

## Unchanged-input runs

Graph: a job whose sources land less often than it runs, or on a calendar
(weekdays only, once a day).

Evidence: source `max_loaded_at` or raw-table write history against the job's
runs over 14 days; count runs where no source in the node set's lineage changed.

Change: a selection that builds only what has fresher sources
(`source_status:fresher+`, with source freshness on the sources), state-aware
building where the deployment supports it, or a cron matched to the landing
times. State the runs and credits saved.

## Unread runs

Graph: runs on days or hours when no consumer reads the output: weekend runs for
a weekday report, overnight hourly runs for a morning dashboard.

Evidence: access history readers of the job's leaf models by weekday and hour
over 30 days, against the job's runs.

Change: limit the cron's days or hours to when readers read, keeping one run
before the first read.

## Long pole

Graph: one model's build takes most of a job's duration, or the job's critical
path is one chain while its threads sit idle.

Evidence: per-node `execution_time` and timing from `run_results.json`; the job
duration against the longest chain of dependent nodes.

Change: give the long model its own job or an incremental build; raise threads
when the critical path is short and the queue is wide. State the minutes of
freshness gained.

## Start-minute crowding

Graph: many jobs start in the same minute (round hours, a shared offset such as
minute 4), so they queue for the same warehouse.

Evidence: run `created_at` against `started_at` (queue time) and warehouse load
in that minute; jobs whose runs wait.

Change: stagger crons that do not depend on each other; chain the ones that do.

## Cost per model build

Credits per build for each model, from the warehouse's query attribution. dbt's
default query comment puts the node id at the start of each query it runs; read
it from the query text. Filter to the production transform user.

```sql
with builds as (
    select regexp_substr(qh.query_text, '"node_id": "([^"]+)"', 1, 1, 'e') as node_id,
           qh.start_time,
           qa.credits_attributed_compute as credits
    from SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY as qa
    join SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY as qh on qh.query_id = qa.query_id
    where qa.start_time >= dateadd('day', -14, current_timestamp)
      and qh.start_time >= dateadd('day', -14, current_timestamp)
      and qh.user_name = '{transform_user}'
)
select node_id,
       sum(credits) as credits_14d,
       count(*)     as n_queries
from builds
where node_id is not null
group by node_id
order by credits_14d desc
limit 200;
```

Credits per build is `credits_14d` divided by the model's builds in the same
14 days, counted from run history (the runs of every job whose node set holds
the model), never from this query: two jobs building a model in the same hour
are two builds.

Query attribution leaves out very short queries and lags real time by several
hours. When a deployment sets its own query comment or query tag, read the node
id from that instead. With no attribution available, estimate from each node's
`execution_time` in `run_results.json` and the warehouse size, and say it is an
estimate.

## Layer lag

Write history for a parent and its child, one row per write, from the
warehouse's access history. Pair each child write with the latest parent write
before it.

```sql
with writes as (
    select f.value:"objectName"::string as relation,
           ah.query_start_time         as written_at
    from SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY as ah,
         lateral flatten(ah.objects_modified) as f
    where ah.query_start_time >= dateadd('day', -14, current_timestamp)
      and f.value:"objectName"::string in ('{parent}', '{child}')
),
child as (select written_at from writes where relation = '{child}'),
parent as (select written_at from writes where relation = '{parent}')
select c.written_at                                  as child_written_at,
       max(p.written_at)                             as parent_read_at,
       datediff('minute', max(p.written_at), c.written_at) as lag_minutes
from child as c
left join parent as p on p.written_at <= c.written_at
group by c.written_at
order by c.written_at;
```

A `lag_minutes` near a whole cycle, or a parent write landing minutes after
the child's, is a race. Access history lags real time by up to three hours, so
leave today out. Names in `objects_modified` are fully qualified and upper case.

To narrow writes to scheduled runs, join `QUERY_HISTORY` on `query_id` and
filter `user_name = '{transform_user}'`.

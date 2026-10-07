---
name: dq-investigate
description: Investigate one warehouse table, dbt model, domain, source, or symptom for silent data errors, on demand. Maps the target and its lineage, gathers domain knowledge, forms falsifiable hypotheses per node, proves them with read-only warehouse queries, tries to refute every proven finding, and writes a dated report outside the repo. Use when the user says "investigate <table>", "what is wrong with <table or model>", "audit this model's data", "check data quality of <source>", or describes a data symptom ("prices repeat the prior day", "volume dropped since Monday"). Do NOT use for reviewing a PR, branch, or diff (use review-panel, which runs the same agents on changed models with --data), for writing or applying fixes, or for data that does not live in a SQL warehouse (spreadsheets, CSV files, API payloads).
---

# dq-investigate

Find what is silently wrong in the data behind one target. Every finding is
backed by a query result; code reading alone yields a suspect, never a finding.
Read-only from start to finish: this skill changes no table, model, monitor,
ticket, or repo file.

**Input:** one target in a sentence (a table, model, domain, source, or symptom)
and an optional note from the user. A symptom and the note are the first lead
for every agent.

**Done when** every hypothesis is proven, disproven, or parked with the query
that would settle it, and every proven finding has a severity, a cause (or "not
yet known"), an impact line, and a fix.

## Guardrails (hold for the whole run)

- Queries: `SELECT`, `WITH`, `DESCRIBE`, `SHOW` only, one statement per call.
  Named columns, never `SELECT *`. Aggregates by default; a row-level read
  carries `LIMIT` (default 100). The data-tier guard hook enforces this while
  the session marker is active; the rules hold even when it is not.
- Size first: follow "Size first" in `references/dq/evidence.md`. Over 50M rows
  means a bounded date window; over 1B rows means metadata or `SAMPLE` only.
- Personal data: columns matching the profile's `pii_column_patterns` (and any
  loyalty, email, phone, name, or address column) are counted or aggregated,
  never shown at row level, in agent returns or in the report.
- Every number in the report carries the `queried_at` of the query behind it.
- Real company identifiers never go into a tracked file. The report lives
  outside every repo.
- Spawn agents with the Agent tool, in parallel (one message, several calls).
  Use the Workflow tool only when the user asked for a workflow.

## 1. Setup

1. Resolve the deployment profile:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/checks/deep-profile.py --json`.
   `{"profile": null}` means no profile: assume production naming from the dbt
   project, Snowflake dialect, repo docs as the only knowledge source, dbt tests
   as the only check system, and say so in the report's scope line.
2. Confirm a warehouse tool is reachable (see `references/dq/warehouse-tools.md`).
   None reachable: stop, and tell the user which tool the profile or that file
   expects. Do not fall back to code reading and call it an investigation.
3. Start the guard:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/checks/data-tier.py start --session "$DEEP_SESSION_ID"`.
   Stop it in step 9, and also on any early exit or error:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/checks/data-tier.py stop --session "$DEEP_SESSION_ID"`.

## 2. Map

Spawn in parallel:

- `deep:model-context` with the target: resolve it to dbt models, or to
  relations with no dbt node. It returns grain, keys, health and tests, lineage
  back to raw sources and out to exposures, relations, config, incremental
  filter, and the job behind every node.
- `deep:domain-context-reader` with the target and the profile's
  `knowledge_sources`: meaning, semantic grain against the dbt key, rules a
  query can test, documented known issues, consumers, traps. It falls back to
  repo docs when no source is reachable.

The map is done when the grain is one stated line and every parent is named.
Keep scope to about 20 relations, nearest the target first; state any cut.
Then run `git log --since=90.days --oneline -- <path>` on each model's file for
recent commits; they go to every hand-off for that node.

## 3. Triage

Follow the triage in `references/dq/evidence.md`. Every node the target names
is examined; add the parents and children with the highest scores, at most 8
nodes in total, nearest first. State the cut. Write your own hypotheses only
for what the symptom claims directly ("price repeats the prior day's value on
more than 20% of site-days"), each with the query that would falsify it.

## 4. Hypothesize

One `deep:dq-hypothesizer` per triaged node, all in one message. Each hand-off
carries: node, relation, environment, grain, key columns, date column, cadence,
parents, the model-context card, the domain-context excerpt with its source and
as-of date, the recent commits, and the symptom as the first lead. Budget:
full for nodes the target names, light for the rest.

Merge in this session: drop duplicates (same relation and same claim), and
drop any hypothesis a standard check in step 5 already covers.

## 5. Prove

Units of work for `deep:dq-prover`, in batches of 10, at most 6 batches:

- standard checks from `references/dq/standard-hypotheses.md` on every relation
  in scope (H1 to H4, H8, H10, H11; H6 on incremental models and snapshots;
  H5 on models with recent commits);
- H9 reconciliation on every lineage edge between nodes in scope;
- the symptom hypotheses from step 3;
- the merged hypotheses from step 4, dependent ones after their parents hold.

Each batch runs in its own agent; send all independent batches in one message.
Batches over the cap are listed under "Not reached" with their hypotheses.

**Derived round:** one round only. Collect each batch's `new_leads` that name a
readable relation, dedupe against everything already run (key: relation plus
claim), and run at most 3 more batches. Remaining leads go to "Not reached".

## 6. Verify

For each proven finding, spawn a fresh `deep:dq-prover` that did not produce it,
with the claim, relation, evidence query and result, and this instruction: try
to refute it. It re-runs the query or an independent one (another date window,
another aggregate, the parent in place of the model), then checks the benign
explanations:

- the two sides use different date windows, time zones, or date bases;
- the behaviour is an intended rule (YAML description, SQL comment, the domain
  context, a documented known issue);
- a guard elsewhere handles it (a downstream test, filter, or dedupe);
- the data is still loading today (last altered against cadence);
- the rows fall outside the model's documented scope.

Verdicts: `confirmed`, `refuted`, `unverifiable` (no query of its own). A
documented known issue the data still shows stays confirmed, marked
`known: <source>`. The verifier narrows the claim when the numbers support less.

Severity is set by readers:

- **High**: wrong numbers reached a decision-facing report, forecast, or price
  in the last 30 days, or a known consumer makes decisions from the table.
- **Medium**: wrong numbers sit in a table or feature with active readers.
- **Low**: nothing reads the wrong rows today, or only a dead check does.

## 7. Cause and impact (optional, per confirmed finding)

Run these when the finding is High or Medium, or the user asked "since when" or
"who is affected".

- **Cause:** run the finding's check by day to get the first bad day. Run the
  same check on each parent with the same columns; a parent that shows it moves
  the search up one level. The first relation that shows it with no parent that
  does is the origin. `git log` and `git blame` on the origin model's file for
  commits between the last good and first bad day; name the one that fits as a
  hypothesis when the data cannot tell commits apart.
- **Impact:** downstream models and exposures from the model context; affected
  rows, entities, and days (aggregates only); readers over the last 30 days
  from `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` joined to
  `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` on `query_id`. Report roles and teams,
  never individual users. Name the business unit from the profile's
  `business_units` when the consumer maps to one.

## 8. Checks and monitors

One `deep:monitor-reviewer` per confirmed finding, in parallel. It returns
`covered`, `misconfigured`, `missing`, or `not-monitorable`, with the monitor
YAML (Metaplane only when the profile's `check_systems` lists it or the repo has
`meta.metaplane` blocks) or the dbt test or source-freshness block that would
catch it next time. Recommendations only; it applies nothing.

## 9. Report

Stop the guard first (step 1.3). Then write the report to
`~/.claude/code-reviews/dq/<YYYY-MM-DD>-<target-slug>.md` (`mkdir -p` the
directory; it is outside every repo). Use the template in
`references/report-template.md`. Group findings that share a root cause into
one issue; an issue's severity is the highest severity among its findings.

In chat, give the verdict line, the top issues in one line each, the counts
("hypotheses: n run, p proven, v confirmed, r refuted"), and the report path.

No tickets are filed. If the user asks for one, hand the issue text to the
`jira` skill when it is installed; otherwise give the text to paste.

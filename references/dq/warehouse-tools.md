# Warehouse tools

The data tier (`dq-hypothesizer`, `dq-prover`, `monitor-reviewer`) and the
context stage (`model-context`) name tools by **role**. Resolve each role to the
first tool this session actually has, in the order below, before the first call.
The profile's `[warehouse].tool` (and `describe_tool`) wins over the order when
set. A role with no tool is a gap: say so in `couldnt_check`, never guess a
result.

| Role | dq_agent name | This host, in order |
|---|---|---|
| `query` (one statement) | `sf_query` | `[warehouse].tool`; `mcp__dq__sf_query`; `mcp__claude_ai_dbt__execute_sql`; `mcp__dbt__execute_sql`; a Snowflake MCP query tool |
| `batch` (up to 10 statements) | `sf_batch` | `mcp__dq__sf_batch`; else `query` once per statement, all calls in one message |
| `describe` | `sf_describe` | `[warehouse].describe_tool`; `mcp__dq__sf_describe`; else `query` on `<DB>.INFORMATION_SCHEMA.COLUMNS` |
| `list_tables` | `sf_list_tables` | `query` on `<DB>.INFORMATION_SCHEMA.TABLES` (or `SNOWFLAKE.ACCOUNT_USAGE.TABLES` with `deleted is null`) |
| `model_health` | `get_model_health` | `mcp__claude_ai_dbt__get_model_health`; `mcp__dbt__get_model_health` |
| `lineage` | `get_lineage` | `mcp__claude_ai_dbt__get_lineage`; `mcp__dbt__get_lineage` |
| `model_details` | `get_model_details` | `mcp__claude_ai_dbt__get_model_details`; `mcp__dbt__get_model_details` (only when the file is not in the repo) |
| `exposures` | `get_exposures` | `mcp__claude_ai_dbt__get_exposures`; `mcp__dbt__get_exposures`; else Grep `exposures:` in the repo |
| `job_runs` | `get_model_performance`, `get_job_run_details` | the same names under `mcp__claude_ai_dbt__` or `mcp__dbt__` |
| `repo_read`, `repo_grep`, `git_log` | `repo_*`, `git_log` | Read, Grep, `git log` through Bash |

Dropped from dq_agent, with no replacement: `facts_read`, `fact_record`,
`fact_relate`, `scratch_*`. Nothing in this plugin keeps a fact store; a result
lives in the agent's JSON and the review report.

**Agent `tools:` frontmatter** lists the known prefixes above
(`mcp__claude_ai_dbt__`, `mcp__dbt__`, `mcp__dq__`). An MCP server registered
under another name is invisible to these agents until you add its tool names in
a local agent override (`~/.claude/agents/<name>.md` with the same `name:`).

## Environment

Production by default. The profile's `[environments]` says which database
prefix is production. When the profile sets `ci_schema_pattern` and CI built the
pull request, query the PR relation and the production relation both. Every
`result_excerpt` opens with `queried <DATABASE.SCHEMA.TABLE> (production)` or
`queried <DATABASE.SCHEMA.TABLE> (PR CI schema <NAME>)`.

## Read-only rules

The `warehouse-sql-guard` hook enforces these while a data-tier run is active;
agents follow them regardless.

- One statement per call. `SELECT`, `WITH ... SELECT`, `DESCRIBE`, `SHOW` only.
  No DML, DDL, `CALL`, `PUT`, `COPY`, `GRANT`, or session changes (`USE`,
  `ALTER SESSION`).
- No `SELECT *`; name columns.
- Aggregate. A row-level read (offender lists) carries `LIMIT` of at most 50,
  and returns key columns, dates and the measure in question only.
- Bounded: a date filter, metadata-only `COUNT`/`MIN`/`MAX`, or `tablesample
  system`. Size the shape from the table's row count first (`Size first` in
  `references/dq/evidence.md`).
- **Personal data.** Columns matching the profile's `pii_column_patterns`
  (loyalty member ids, emails, phone numbers, card tokens and the like) appear
  only inside `count`, `count(distinct ...)` or `approx_count_distinct`. Never
  select, group by, or quote them. Without a profile, treat names containing
  `email`, `phone`, `member`, `customer_name`, `card`, `ssn`, `dob`, `address`
  as personal.
- Never echo credentials, connection strings or account identifiers in output.

## Dialect

Snowflake is assumed (`count_if`, `approx_count_distinct`, `qualify`,
`tablesample system`, `table(generator(...))`, `is distinct from`). Confirm it
from the profile's `[warehouse].dialect` or the dbt adapter. On another engine,
rewrite each recipe for it, and mark any recipe you cannot translate
"inconclusive: dialect".

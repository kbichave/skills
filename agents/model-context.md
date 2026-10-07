---
name: model-context
description: Metadata stage for the review-panel data path and dq-investigate. Given changed dbt models or a target, returns what each model is, its config and incremental filter, tests and their last status, lineage back to the raw sources and out to the exposures, production relations, and the job behind each node, as JSON. Metadata only, read-only. Not for querying table data (that is dq-prover) or for business meaning (that is domain-context-reader).
tools: Read, Grep, Glob, Bash, mcp__claude_ai_dbt__get_model_health, mcp__claude_ai_dbt__get_lineage, mcp__claude_ai_dbt__get_model_details, mcp__claude_ai_dbt__get_model_parents, mcp__claude_ai_dbt__get_model_children, mcp__claude_ai_dbt__get_exposures, mcp__claude_ai_dbt__get_exposure_details, mcp__claude_ai_dbt__get_all_sources, mcp__claude_ai_dbt__get_source_details, mcp__claude_ai_dbt__get_model_performance, mcp__claude_ai_dbt__get_job_details, mcp__claude_ai_dbt__get_job_run_details, mcp__claude_ai_dbt__execute_sql, mcp__dbt__get_model_health, mcp__dbt__get_lineage, mcp__dbt__get_model_details, mcp__dbt__get_model_parents, mcp__dbt__get_model_children, mcp__dbt__get_exposures, mcp__dbt__get_exposure_details, mcp__dbt__get_all_sources, mcp__dbt__get_source_details, mcp__dbt__get_model_performance, mcp__dbt__get_job_details, mcp__dbt__get_job_run_details, mcp__dbt__execute_sql, mcp__dq__sf_query, mcp__dq__sf_describe
---

# Model context (context stage: `model-context`)

Describe a scope of one or more dbt models as one picture: shared sources and
exposures once, then one entry per model. The hypothesizer, the prover, the
domain-context reader, and the review-verifier all read your output, so they
never fetch this metadata again.

## Input

Your prompt contains:
- `models`: the changed models (names or paths), or a `target` (a model,
  table, source, or domain) for dq-investigate.
- `repo`: the dbt project root.
- `profile`: the resolved deployment profile JSON, or `null`. It names the
  production environment, the layer naming, the CI schema pattern, and the
  warehouse tool.

## Hard limits

- **No table data.** The only warehouse queries allowed are metadata:
  `INFORMATION_SCHEMA.TABLES`, `INFORMATION_SCHEMA.COLUMNS`,
  `SNOWFLAKE.ACCOUNT_USAGE.TABLES` (with `deleted is null`), and `describe`.
  Never `select` from a model or source relation.
- Never call `get_model_details` or `get_node_details` on a model or test to
  read its SQL; read the `.sql` file instead, and only its `config()`, header
  comment, and `is_incremental()` block. Use node details for sources and
  exposures only.
- Never read a schema `.yml` whole: grep for `- name: <model>` and read that
  range.
- Scope cap: about 60 relations. Past that, cut by distance from the changed
  set and state the cut in `cut`.

## Steps

1. **Probe tools.** Note which of the dbt MCP (either prefix) and a warehouse
   query tool are present. Each missing tool goes in `unavailable`; continue
   with what remains.
2. **Health.** `get_model_health` per model: `unique_id`, last run status and
   time, every test with its last status, upstream source freshness.
3. **Lineage.** For each `unique_id`:
   - `get_lineage` upstream, `depth=0`, no `types` filter (a type filter breaks
     the walk): every ancestor back to the raw sources and seeds. Direct
     parents are the ones with an edge to the model.
   - `get_lineage` downstream, `depth=0`, `types=["Model","Exposure"]`,
     `limit=500`: the downstream count, the exposures reached, and any other
     in-scope model it feeds.
4. **Relations.** One metadata query for the names of the in-scope models,
   upstream models, and direct children: database, schema, row count, last
   altered. Pick the production copy using `profile.environments`; with no
   profile, take the copy with no environment prefix, else the `prod_` one,
   and say which rule you used. Then describe each production relation for its
   columns and types. Write every relation as `DATABASE.SCHEMA.TABLE`.
5. **Config.** Read each model's `.sql` for materialization, incremental
   strategy, `unique_key`, the incremental filter (one line), and the header
   comment's purpose and grain.
6. **Jobs.** `get_model_performance` (last 5 runs for in-scope models, the
   last run for lineage nodes), then `get_job_run_details` once per distinct
   run id and `get_job_details` once per distinct job: name, environment,
   trigger, schedule (cron and in words), and which step selects the model and
   how (path, tag, selector, `+` operator). A node with no run has no job;
   record it, never guess one.
7. **Sources and exposures.** `get_source_details` for each raw source
   (relation, loader, freshness config) and `get_exposure_details` for each
   exposure (owner, type, url), once each.

## Fallback without the dbt MCP

Work from the repo. If `target/manifest.json` exists, read lineage, tests,
sources, and exposures from it (`parent_map`, `child_map`, `nodes`,
`sources`, `exposures`). Otherwise run `dbt ls --select +<model>+
--resource-type model source exposure --output json` via Bash when `dbt` is on
the path and a profile resolves; failing that, grep `ref(` and `source(` to
rebuild one hop up and down. Mark every field you could not fill as `null` and
name the missing tool in `unavailable`. No health, run, or job data exists in
this mode; say so.

## Output: JSON only, no preamble, no fences

```json
{
  "expert": "model-context",
  "built_at": "<UTC timestamp>",
  "scope": ["<model names in scope>"],
  "production_rule": "<how the production copy was chosen>",
  "models": [
    {
      "name": "<model>",
      "unique_id": "model.<project>.<model>",
      "relation": "DATABASE.SCHEMA.TABLE",
      "rows": 0,
      "last_altered": "<timestamp>",
      "materialization": "incremental",
      "incremental_strategy": "merge",
      "unique_key": ["<col>"],
      "incremental_filter": "<one line, or null>",
      "grain": "<from header comment or YAML, or null>",
      "columns_used": ["<name type>"],
      "tests": [{"name": "unique_<model>_<col>", "status": "pass"}],
      "last_run": {"status": "success", "at": "<timestamp>"},
      "parents": ["<unique_id>"],
      "children": ["<unique_id>"],
      "exposures": ["<exposure name>"],
      "raw_sources": ["<source.relation>"],
      "job": {"id": "<id>", "name": "<name>", "schedule": "<cron, in words>", "selected_by": "<tag/path/selector>"},
      "gaps": ["<missing tests, docs, freshness, owner>"]
    }
  ],
  "lineage_nodes": [
    {"unique_id": "<id>", "role": "raw source|upstream|child", "relation": "DATABASE.SCHEMA.TABLE", "job": "<id or null>", "feeds": ["<model>"]}
  ],
  "shared_sources": [
    {"name": "<source.table>", "relation": "DATABASE.SCHEMA.TABLE", "loader": "<loader>", "freshness": "<config>", "used_by": ["<model>"]}
  ],
  "exposures": [
    {"name": "<exposure>", "owner": "<team or role>", "type": "dashboard", "reached_from": ["<model>"]}
  ],
  "nodes_without_job": ["<unique_id>"],
  "cut": "<what was dropped past the cap, or none>",
  "unavailable": ["<tool names that were missing>"]
}
```

- `gaps` lists what is missing; do not analyse logic or guess at data
  problems. That is the hypothesizer's job.
- Owners are teams or roles, never individuals.
- `built_at` matters: every downstream stage quotes it as the as-of time of
  this metadata.

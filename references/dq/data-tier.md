# Warehouse context and data tier (review-panel)

Loaded by `skills/review-panel/SKILL.md` step 2b (context) and step 5 (data
stage). `skills/dq-investigate/SKILL.md` runs the same agents from a target
instead of a diff.

## Profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/checks/deep-profile.py --repo <repo>
```

`{"profile": null}` is the generic mode: production is whatever the dbt
project's prod target names, no knowledge space, dbt tests as the check
system. Exit 2 means a profile exists but is invalid: tell the user the error
line and continue in generic mode. Pass the profile JSON to every agent below;
never paste its values into a PR comment.

## Context stage (2b)

Runs when `deep:data-eng-reviewer` is selected and the diff touches dbt
models, YAML, macros, seeds or snapshots. Spawn in one message:

| Agent | When | Input |
|---|---|---|
| `deep:model-context` | always in this stage | changed models, repo path, profile |
| `deep:domain-context-reader` | profile lists `knowledge_sources`, or `--context`; never with `--no-context` | changed models plus model-context lineage when available, profile |

They are independent; the reader works from model names when lineage is not
yet in. Neither reads table data. A missing MCP is reported in their
`unavailable` / `sources_unavailable` lists, never an error. Hand both outputs
to `deep:data-eng-reviewer` (as `model_context`, `domain_context`) and to the
review-verifier.

## Data stage (step 5, `--data` only)

Skip with one line ("data tier off" or "data tier: no warehouse tool
reachable") unless `--data` was passed and a warehouse tool from
`references/dq/warehouse-tools.md` answers a `select 1`.

1. **Arm the guard.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/checks/data-tier.py
   start --session "$DEEP_SESSION_ID"`. While armed, the PreToolUse hook denies
   any warehouse SQL that is not one read-only, star-free, bounded statement.
2. **Hypothesize.** One `deep:dq-hypothesizer` per changed model, nearest the
   change first, cap 4 (state the cut). Each gets its diff hunk, the
   data-eng findings on it (with `disproof_sql`), both context outputs and the
   profile. Light budget.
3. **Prove.** Build the item list in this session and dedupe by relation plus
   claim:
   - standard checks H1 to H4 per changed relation, H6 for incremental ones
     (`references/dq/standard-hypotheses.md`);
   - H9 per changed lineage edge, one fan-out check per join data-eng named;
   - every finding's `disproof_sql`;
   - the hypothesizers' hypotheses, high priority first.
   Batches of 10, one `deep:dq-prover` (run mode) per batch, cap 4 batches,
   all in one message. Environment: the PR CI schema when the profile's
   `ci_schema_pattern` resolves to an existing schema, else production; say
   which in the report.
4. **Verify.** One `deep:dq-prover` in verify mode per proven item, a fresh
   agent that did not prove it, cap 6.
5. **Disarm.** `data-tier.py stop --session "$DEEP_SESSION_ID"`, also when a
   step failed. The marker expires after 4 hours regardless.
6. Hand prover and verify results to the review-verifier (check 10). A null
   or failed agent return is a suspect with `missing_table` set, never a
   finding.

After the review-verifier: one `deep:monitor-reviewer` per approved `high` or
`medium` warehouse finding with data evidence, cap 6. Its `check_as_code` goes
under the finding's fix.

Use parallel Agent calls. Use the Workflow tool only when the user asked for
a workflow.

## Report additions

- `## Production data` (data stage only): one line per relation queried with
  environment, freshness, rows per day, duplicates, null keys, each number
  with its `queried_at`.
- Findings with `data_evidence` show `How verified:` with the relation and
  environment, the query excerpt and `queried_at`.
- `## Checked and found fine`: the verifier's `checked_fine` list.
- `## Checks to add`: monitor-reviewer verdicts `missing` or `misconfigured`
  with their YAML.
- PR comments carry aggregates only. Never a value from a column matching the
  profile's `pii_column_patterns`.
- Pre-existing problems (scope `fixed-by-pr`, or proven but older than the
  change): offer `dq-investigate` on that relation.

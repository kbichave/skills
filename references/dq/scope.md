# Scope hand-off

Scoring and picking nodes is the Triage section of `references/dq/evidence.md`.
This file is the hand-off the orchestrator gives each picked node's
`dq-hypothesizer`.

## Hand-off

One per examined node, every field filled ("none" or "unknown" rather than left
out). Never paste the whole context.

```
Node: <name> | Role: <in scope, upstream, child, raw source> | Budget: <full|light>
Relation: <DATABASE.SCHEMA.TABLE> | Environment: <production | PR CI schema NAME>
Rows: <n> | Last altered: <time> | Job: <name or none>
SQL path: <path if known> | Diff hunk: <the changed lines, or none>
Parents: <name (relation)>, ... | Children: <name (relation)>, ...
Raw sources read: <relation, key columns, date column> | none
Consumers: <exposures or business units it reaches> | none
Leads:
- <3 to 6 lines: data-eng findings with their disproof_sql, no job, known
  issue, grain mismatch, missing tests, join or incremental logic>
Rules:
- <up to 5 domain rules or traps that name this node or its semantic object>
PII columns: <names matching the profile's pii_column_patterns> | none
```


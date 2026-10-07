# dq-investigate report template

Plain words for a data team and its business readers. No hypothesis language
("holds if", "H3") in issue text; say what is wrong as a fact. Every number
comes from an agent return and carries its `queried_at`. No row-level personal
data anywhere.

```markdown
---
target: <target as given>
date: <YYYY-MM-DD>
profile: <profile name | none>
warehouse_tool: <tool used>
environment: <production | named schema>
---

# Data quality investigation: <target>

Findings: <n> High, <n> Medium, <n> Low.

## Scope
- Target: <as given>; note: <note | none>
- Relations mapped: <n>, nodes examined: <n> (cut: <what was left out and why> | none)
- Knowledge sources read: <source, as-of date> | repo docs only
- Hypotheses: <n> run, <p> proven, <v> confirmed, <r> refuted, <u> unverifiable

## Issues

### 1. <Issue title in plain words> | <High | Medium | Low>
- **What is wrong:** <one or two sentences>
- **Evidence:** <relation (environment): deciding numbers, date range, example keys>; queried_at <ts>
- **Extent:** <rows, entities, days affected; since when>
- **Cause:** <origin relation, first bad day, commit that fits> | not yet known
- **Impact:** <downstream models, exposures, reader roles or teams, business unit>
- **Fix:** <the change and where>
- **Check to add:**
  ```yaml
  <dbt test, source freshness, or monitor YAML from monitor-reviewer>
  ```
- **Verify the fix:** `<query that returns zero rows once fixed>`
- **Known issue:** <source and section> | no

### 2. ...

## Checks to add or change
<one line per recommendation not already shown under an issue: relation, check, reason>

## Suspects
<one line each: claim, relation, the query or table that would settle it, why it was not run>

## Not reached
<hypotheses and leads dropped by a cap or the derived-round limit> | none

## Checked and found fine
<one line per disproven hypothesis or refuted finding, with its deciding number and queried_at>
```

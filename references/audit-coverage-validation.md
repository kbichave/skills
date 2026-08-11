# Audit Coverage Validation

Checks which research topics from `research-topics.yaml` have findings files, then spawns targeted gap agents for uncovered topics. Done after Deep Research, before Auto Gap ID.

## Purpose

Research agents cover their assigned topics but the assignment may have been imperfect, or agents may have produced empty/thin findings for some topics.

## Step 1: Run Coverage Check

```bash
uv run ${DEEP_PLUGIN_ROOT}/scripts/checks/validate-coverage.py \
  --topics-file "${planning_dir}/research-topics.yaml" \
  --findings-dir "${planning_dir}/findings/"
```

Parse JSON output:
```json
{
  "coverage_pct": 73.3,
  "total": 15,
  "covered": 11,
  "missing": ["rt-04", "rt-09", "rt-12", "rt-15"]
}
```

## Step 2: Assess Missing Topics

For each missing topic ID, read its entry from `research-topics.yaml`:
- Review its `category`, `priority`, and `questions`
- Determine if it can be researched:
  - **Yes** (most cases): spawn a gap agent
  - **Unresearchable** (e.g. "Operational runbooks" for a project with no ops docs): mark as `skipped` with a note

## Step 3: Spawn Gap Agents

For each researchable missing topic, spawn **one** `general-purpose` agent with WebSearch enabled. Each agent gets this prompt:

```
Topic: {topic name}
Category: {category}
Priority: {priority}

You are researching this topic for a codebase audit. Answer these questions:
{questions[0]}
{questions[1]}
...

Codebase context: read {planning_dir}/scan-summary.md first.
Then read any relevant source files from {initial_file} directory.
Use WebSearch to find ecosystem context, package alternatives, and best practices.

Write your findings to: {planning_dir}/findings/{topic_id}-{topic_slug}.md

Use this format:
## {Topic Name}
<!-- source: gap-agent, topic: {category}, wave: gap -->

{findings — answer each question explicitly}

### Open Questions Raised
- {anything that needs deeper investigation}
```

After the agent writes its findings file, update `research-topics.yaml`:
```yaml
- id: rt-04
  status: covered
  findings_file: "findings/rt-04-database-schema.md"
```

## Step 4: Loop Until Threshold Met

After all gap agents complete:
1. Re-run `validate-coverage.py`
2. If `coverage_pct >= 80`: proceed to Auto Gap ID
3. If `coverage_pct < 80` and there are still researchable missing topics: repeat from Step 3
4. If `coverage_pct < 80` but all remaining missing topics are unresearchable: proceed anyway, note the gap in the coverage report

**Hard limit:** Maximum 2 gap-filling rounds.

## Step 5: Write Coverage Report

Write `{planning_dir}/coverage-report.md`:

```markdown
# Research Coverage Report

Coverage: {covered}/{total} topics ({pct}%)

## Covered Topics
| ID | Topic | Category | Findings File |
|---|---|---|---|
| rt-01 | Authentication & Authorization | security | findings/rt-01-auth.md |
...

## Skipped Topics
| ID | Topic | Reason |
|---|---|---|
| rt-12 | Operational Runbooks | No ops documentation exists in codebase |
...

## Notes
{Any observations about coverage quality, thin findings, or areas needing human judgment}
```

Also generate `{planning_dir}/findings.md` as an **index** of all findings files:

```markdown
# Research Findings Index

This file indexes per-topic findings. See individual files in findings/ for details.

## Topics Covered ({N})
- [rt-01 — Authentication & Authorization](findings/rt-01-auth.md) — security · high
- [rt-02 — Database Schema & Migrations](findings/rt-02-db-schema.md) — data-model · high
...
```

## Rules

1. **Do not spawn more than 7 gap agents in parallel** (Claude Code subagent limit).
2. **Gap agents must write to `findings/<topic-id>-<slug>.md`** — not append to findings.md.
3. **80% coverage is the threshold**, not 100% — some topics (ops, deployment) may legitimately be unresearchable without production access.
4. **A findings file must be non-empty to count as covered** — a file with only a heading does not qualify.
5. **Mark unresearchable topics as `skipped`** in the YAML — never leave them as `pending`.

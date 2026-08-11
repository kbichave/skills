# Audit Document Writing Protocol

Defines how deep-discovery step 8 generates audit documents. Files are dynamic, focused, and quality-gated.

## Output Compression

Audit docs are intermediate artifacts — compress aggressively.

- No section-intro sentences. Start every section with content, not description.
- Bullets > paragraphs. Tables > bullets for comparisons.
- Max 15 words per prose sentence. No hedging ("might", "could potentially").
- No filler transitions ("Additionally", "Furthermore", "It is worth noting").
- `current-state/` files: lead with a `| Metric | Value |` table (line counts, file counts, dep counts).
- `gaps/` files: use `| Gap | Severity | Effort | Affected |` table per gap.

---

## Core Rules

1. **One topic per file.** If a file would exceed ~300 lines, split it.
2. **File names are descriptive.** `request-flow.md` not `finding-01.md`.
3. **File list is dynamic.** Determined by what research found, not a template.
4. **Every file is independently readable.** Cross-reference other files by relative path.
5. **No project-specific assumptions.**

---

## File Determination Logic

Read findings.md, interview.md, and auto-gap files. For each significant topic discovered, create a file.

### Decision Tree

```
For each finding in findings.md:
  Is it about the current system state?
    → current-state/{descriptive-name}.md
  
  Is it a gap (something missing)?
    Is it a structural blocker?     → gaps/tier1-blockers.md
    Is it an industry standard?     → gaps/tier2-table-stakes.md
    Would it differentiate?         → gaps/tier3-differentiators.md
    Is it future/optional?          → gaps/tier4-nice-to-have.md
    Is it infrastructure?           → gaps/infrastructure-gaps.md
  
  Is it about the target state?
    → architecture/{descriptive-name}.md
  
  Does it require a specification?
    → specs/{descriptive-name}.md
  
  Is it operational?
    → operations/{descriptive-name}.md
  
  Is it strategic?
    → strategy/{descriptive-name}.md
```

### What Each Category Contains

**current-state/** — "What exists today"
- Only for existing systems (skip for greenfield)
- One file per major aspect: request flow, code structure, data model, infra, testing
- Includes quantitative data: line counts, file counts, dependency counts
- Identifies problems inline (but detailed gap analysis goes in gaps/)

**gaps/** — "What's missing"
- Tiered by severity/urgency
- Cross-referenced against competitor research (from strategy/)
- Each gap includes: what's missing, why it matters, who it affects, effort estimate
- tier1 = blocks new work; tier2 = industry expects it; tier3 = competitive edge; tier4 = future

**architecture/** — "What the target looks like"
- One file per architectural concern relevant to THIS project
- NOT a generic list — a web API won't have "mobile-app-design.md"
- Includes: system diagram (text), component responsibilities, data flow, integration points

**specs/** — "Implementation details"
- Only produce specs the project actually needs
- Config schemas, data models, API contracts, error handling, security model
- Each spec is self-contained — an engineer should be able to implement from the spec

**operations/** — "How to run it"
- Adapted to detected infrastructure (Docker vs K8s vs serverless vs bare metal)
- Deployment, testing strategy, monitoring, infra audit
- Only produce what's relevant — a serverless app doesn't need "docker-compose-evolution.md"

**strategy/** — "Why and what order"
- Always includes competitor/alternative research
- Build-vs-buy summary (details in build-vs-buy/ directory)
- Enablement plan (if non-technical users are involved)
- Domain-specific strategy (if applicable)

**phases/** — "Implementation order" (see audit-phasing.md)

**build-vs-buy/** — "What to use" (see audit-build-vs-buy.md)

---

## Subagent Generation

### How Many Subagents

Count the total files to generate. Launch in batches of up to 7 (Claude Code parallel limit).

### Subagent Brief

Each audit-doc-writer subagent receives a prompt file containing:

```markdown
## Task
Generate: {file_title}
Output to: {category}/{filename}.md

## Context (Read These Files)
- {audit_dir}/findings.md (sections tagged with topic: {relevant_topic})
- {audit_dir}/interview.md
- {audit_dir}/gaps/{relevant_gap_file}.md (if exists)

## Focus
{2-3 sentence brief specific to this file}

## Constraints
- Maximum ~300 lines. If longer, this should have been split into multiple files.
- Reference other audit files by relative path: `See ../gaps/tier1-blockers.md`
- Include quantitative data where available (line counts, file counts, percentages)
- Be specific: file paths, function names, version numbers — not vague summaries
- For build-vs-buy references: cite the build-vs-buy/{capability}.md file

## Output
Raw markdown only. SubagentStop hook writes the file.
```

### Prompt File Location

Prompt files are written to: `{audit_dir}/.prompts/{category}-{filename}.prompt.md`

The SubagentStop hook derives the output path from the prompt path:
- Input: `{audit_dir}/.prompts/current-state-request-flow.prompt.md`
- Output: `{audit_dir}/current-state/request-flow.md`

Convention: prompt filename = `{category}-{filename}.prompt.md` → output = `{category}/{filename}.md`

---

## Eval-on-Write Quality Gate

After each subagent writes a file (via SubagentStop hook), evaluate:

```
Read the generated file.
Score 1-10 on:
  Completeness: Does it cover the topic thoroughly?
  Specificity: Does it name files, functions, versions — not vague?
  Actionability: Can someone act on this without asking questions?

If average score < 7:
  Regenerate with feedback:
  "File {name} scored {score}/10. Issues: {issues}. Rewrite with:
   - More specific file paths and function names
   - Quantitative data (how many files affected, line counts)
   - Concrete recommendations, not vague suggestions"

If average score >= 7:
  Accept. Move to next file.
```

### Regeneration Limit

Maximum 2 regeneration attempts per file. If still below threshold after 2 retries, accept the best version and note the quality concern in README.md.

---

## Reflection Nudge (After Each Batch)

After every batch of 3-4 files is written:

1. Read all generated files so far
2. Check for:
   - Contradictions between files
   - Missing cross-references (file A mentions topic covered in file B but doesn't link)
   - Gaps between files (topic mentioned but no file covers it)
   - Redundancy (two files cover the same thing)
3. Fix: update files, add cross-references, merge redundant files, create missing files

This prevents "island effect" where each subagent writes in isolation.

### Build-vs-Buy Quality Gate (additional checks for `build-vs-buy/` files)

For each file in `build-vs-buy/`:
1. **Checklist completeness**: Every recommended package has a filled verification checklist. Unchecked items without `UNVERIFIED` label = fail.
2. **Minimum alternatives**: At least 2 alternatives evaluated per capability (not counting build-custom).
3. **Build-custom present**: The "Build Custom" section must exist with a maintenance burden estimate.
4. **Reasoning specificity**: Recommendation text >50 words and references at least one concrete factor.

For files with >1 `UNVERIFIED` package, request regeneration with instructions to verify or replace flagged packages.

Append quality summary to the audit `README.md`:

```markdown
## Build-vs-Buy Quality
| Capability | Packages Evaluated | Verified | Unverified | Gate |
|---|---|---|---|---|
| {name} | {count} | {count} | {count} | PASS/WARN |
```

---

## Eval-on-Write Calibration Examples

### Example 1: Score 9/10 (Excellent)

> **Topic:** Current State: Request Flow
>
> The request lifecycle spans 4 files across 2 packages. Ingress enters through `src/api/router.py:handle_request()` (line 23), which dispatches to handler functions in `src/api/handlers/`. The auth middleware at `src/middleware/auth.py:verify_token()` adds ~15ms latency per request (measured via `time.perf_counter` in debug mode). Database queries in `src/db/queries.py` average 3 queries per request with no connection pooling — the `get_connection()` call on line 42 creates a new connection each time. Total p95 latency: ~180ms, of which ~120ms is database. See `../gaps/tier1-blockers.md` for the connection pooling gap analysis.

**Why this scores 9/10:** Specific (file paths, function names, measured latencies), complete (covers full request lifecycle from ingress to response), and actionable (each bottleneck has a concrete location). Loses one point because database query analysis uses estimated counts rather than EXPLAIN output.

### Example 2: Score 7/10 (Passes threshold)

> **Topic:** Gaps: Authentication Weaknesses
>
> The auth module (`src/auth/`) uses JWT with a hardcoded secret in `config.py`. Token expiry is set to 24 hours, which is longer than recommended for this type of application. The refresh token flow exists but lacks rotation — the same refresh token can be reused indefinitely. Estimated impact: affects all 14 API endpoints that require authentication.

**Why this scores 7/10:** Identifies the right problems, names the affected module, and quantifies impact. Loses points for not specifying exact config file lines, not naming the OWASP guideline being violated, and using "longer than recommended" without stating what the recommendation is.

### Example 3: Score 4/10 (Fails, triggers regeneration)

> **Topic:** Architecture: API Design
>
> The API follows REST conventions. Input validation could be improved in several areas. The testing strategy for API endpoints should be enhanced. Consider adding rate limiting and improving error handling consistency.

**Why this scores 4/10:** Generic advice that applies to any API. No file paths, no function names, no version numbers. "Could be improved" and "should be enhanced" are not findings — they are opinions without evidence. A passing document must name actual endpoints, reference actual data models, and identify actual validation gaps found during research.

---

## README.md Generation (Step 13)

After all files are written, generate `{audit_dir}/README.md`:

```markdown
# System Audit: {project_name}

**Date:** {date}
**Mode:** {Existing System | Greenfield | Hybrid}
**Files:** {total_count}

## Current State
{list each file in current-state/ with one-line description}

## Gaps
{list each file in gaps/}

## Architecture
{list each file in architecture/}

## Specifications
{list each file in specs/}

## Operations
{list each file in operations/}

## Strategy
{list each file in strategy/}

## Phases
{list each file in phases/}

## Build vs Buy
{list each file in build-vs-buy/}

## How to Use This Audit

1. Start with `phases/phasing-overview.md` for the roadmap
2. For any phase, read the referenced audit files for context
3. When ready to implement a phase:
   `/deep-plan @{audit_dir}/phases/{phase-file}.md`
4. Then: `/deep-implement` to build it

## Quality Notes
{any files that scored below threshold, if applicable}
```

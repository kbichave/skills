# Audit Phasing Protocol

Defines how deep-discovery step 10 generates implementation phases. Phases are 100% dynamic — names, count, ordering, and grouping all derived from the audit findings.

## Phase Discovery Algorithm

### Step 1: Collect All Actionable Gaps

Read every file in `gaps/`, `architecture/`, and `build-vs-buy/`. Extract every actionable item:

```
From gaps/tier1-blockers.md:
  - "Decouple auth from API layer" (blocker — must do first)
  - "Fix shared state in request handler" (blocker)

From gaps/tier2-table-stakes.md:
  - "Add retry logic" (table stakes)
  - "Add health check endpoint" (table stakes)

From architecture/target-overview.md:
  - "Introduce worker process" (architectural change)
  - "Add message queue" (new component)

From build-vs-buy/caching.md:
  - "Integrate Redis (pip install redis)" (buy decision)
```

### Step 2: Group Into Natural Work Units

Items that change together become a phase. Grouping criteria:

- **Same files touched:** If two changes modify the same 5 files, they're one phase
- **Same capability:** "Add retry" + "add circuit breaker" = one resilience phase
- **Hard dependency:** "Add database" must precede "add migrations" — same phase or adjacent
- **Risk profile:** High-risk changes shouldn't be bundled with low-risk ones

### Step 3: Determine Dependencies

For each phase, identify:
- What must be done BEFORE this phase (prerequisite phases)
- What this phase ENABLES (dependent phases)
- What can run IN PARALLEL (no shared dependencies)

Build a dependency graph. Phases without dependencies can run in parallel.

### Step 4: Order by Priority

```
Priority order:
1. Tier-1 blockers (must fix first — they block everything)
2. Infrastructure prerequisites (database, queues, workers — other phases need them)
3. Tier-2 table stakes (industry expectations)
4. Core capabilities (what the interview prioritized)
5. Tier-3 differentiators (competitive edge)
6. Tier-4 nice-to-have (future)
```

Within each priority level, order by dependency graph (prerequisites first).

### Step 5: Assign Phase Numbers and Names

```
Pattern: P{NN}-{verb}-{noun}.md

Where:
  NN = sequential number (00, 01, 02, ...)
  verb = what the phase DOES (not what it IS)
  noun = what it affects

Examples by project type:

Refactor project:
  P00-fix-shared-state.md
  P01-decouple-auth-layer.md
  P02-extract-worker-process.md
  P03-add-retry-logic.md

Greenfield project:
  P00-setup-project-skeleton.md
  P01-build-data-layer.md
  P02-build-api-endpoints.md
  P03-integrate-auth-provider.md

Migration project:
  P00-setup-new-database.md
  P01-dual-write-adapter.md
  P02-migrate-read-path.md
  P03-cutover-write-path.md
  P04-decommission-old-system.md
```

Names are NEVER generic ("P01-phase-one.md") or hardcoded. They describe the SPECIFIC work.

---

## Phase Spec Format

Each `phases/P{NN}-{name}.md` contains:

```markdown
# P{NN}: {Phase Title}

**Objective:** {One sentence — what this phase achieves}

**Scope:** {Which modules/files/components are affected}

**Depends on:** {List of prerequisite phases by number}

**Enables:** {What phases can start after this completes}

**Effort estimate:** {T-shirt size or time range}

---

## What Changes

{Detailed description of what to build/change/migrate}

## Key Decisions

{Architecture/technology decisions this phase makes}
{Reference build-vs-buy files: "See ../build-vs-buy/{capability}.md"}

## Files to Create/Modify

{List of files with what changes in each — derived from audit findings}

## Tests

| Test | What It Verifies |
|------|-----------------|
| {test name} | {what it checks} |

## Acceptance Criteria

1. {Verifiable criterion}
2. {Verifiable criterion}
...

## Risk

| Risk | Severity | Mitigation |
|------|----------|-----------|
| {what can go wrong} | {high/medium/low} | {how to handle it} |

## References

- See `../gaps/{relevant-gap}.md` for the problem this solves
- See `../architecture/{relevant-arch}.md` for the target design
- See `../build-vs-buy/{relevant}.md` for technology decision
- See `../current-state/{relevant}.md` for the current state
```

---

## Milestone Grouping

Group phases into milestones — natural shipping points where something useful is deliverable.

```markdown
# phases/phasing-overview.md

## Milestones

### M1: {Milestone Name} (derived from what it enables)
**Phases:** P00, P01, P02, P03
**What ships:** {What users/developers can do after this milestone}
**Effort:** {total across phases}

### M2: {Milestone Name}
**Phases:** P04, P05, P06
**What ships:** {What's new}
**Effort:** {total}

...

## Dependency Graph

```
P00 ──→ P01 ──→ P03
  └──→ P02 ──→ P04
                  └──→ P05 ──→ P06
```

## Timeline

| Milestone | Phases | Sequential | With 2 devs |
|-----------|--------|-----------|-------------|
| M1 | P00-P03 | {weeks} | {weeks} |
| M2 | P04-P06 | {weeks} | {weeks} |

## Parallelism Opportunities

{Which phases can run in parallel and why}
```

Milestone names describe OUTCOMES, not phase numbers:
- "Core Stability" not "Milestone 1"
- "User-Facing Launch" not "Milestone 3"
- "Self-Service Platform" not "Milestone 4"

---

## Iteration

After generating phases:

1. Read all phase specs
2. Cross-check against build-vs-buy: "Does each phase correctly reference pip-install vs build-custom decisions?"
3. Cross-check dependencies: "Can P03 really start before P02 finishes?"
4. Check for gaps: "Is there a gap in the audit that no phase addresses?"
5. If issues found: revise phases (reorder, merge, split, add)

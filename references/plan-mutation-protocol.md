# Plan Mutation Protocol

During implementation, reality diverges from the plan. Sections turn out to be too large, dependencies shift, or assumptions prove wrong. This protocol defines formal operations for changing the plan mid-execution with an audit trail.

## When to Mutate

Mutate the plan when:
- A section is too large to implement in one pass (estimated > 500 lines of changes)
- A section's assumptions are invalidated by an earlier section's implementation
- A dependency is discovered that wasn't in the original manifest
- A section is no longer needed (e.g., the problem was solved by an earlier section)
- The confidence gate scores a section below 5 (fundamentally unclear)

Do NOT mutate for:
- Minor scope adjustments within a section (handle inline)
- Test additions not in the original spec (just add them)
- Implementation approach changes that don't affect the section boundary

## Mutation Operations

### 1. SPLIT — Break a section into smaller parts

**When:** Section is too large or has independent sub-tasks that could parallelize.

**Procedure:**
1. Log: `MUTATION: SPLIT section-NN-name → section-NN-name-a, section-NN-name-b`
2. Create new section files using the section-writer agent (same eval/test/impl structure)
3. Update `sections/index.md` SECTION_MANIFEST:
   - Remove the original section line
   - Add the new section lines with correct `depends_on:`
   - Preserve ordering (use sub-numbering: `section-03a-...`, `section-03b-...`)
4. Update tracker: close original issue as "Split into X, Y", create new issues
5. Transfer any completed work from the original section to the appropriate new section

### 2. SKIP — Abandon a section entirely

**When:** Section is no longer needed (solved by prior work, requirement dropped, or out of scope).

**Procedure:**
1. Log: `MUTATION: SKIP section-NN-name — reason: {specific reason}`
2. Close the section's tracker issue with reason: "Skipped: {reason}"
3. Check downstream dependencies — any section with `depends_on:section-NN-name` must have that dependency removed
4. Update `sections/index.md` SECTION_MANIFEST: comment out the line with `# SKIPPED: {reason}`
5. Do NOT delete the section file — mark it with a header: `<!-- SKIPPED: {reason} -->`

### 3. REORDER — Change execution sequence

**When:** A dependency was wrong or a later section should go first.

**Procedure:**
1. Log: `MUTATION: REORDER section-NN before section-MM — reason: {reason}`
2. Update `sections/index.md` SECTION_MANIFEST `depends_on:` edges
3. Validate no circular dependencies exist after the change
4. Re-run `generate-sections.py` to regenerate tracker issues with new dependency graph

### 4. INSERT — Add a new section not in the original plan

**When:** Implementation reveals a missing piece (e.g., a shared utility, a migration step, a new integration point).

**Procedure:**
1. Log: `MUTATION: INSERT section-NN-new-name after section-MM — reason: {reason}`
2. Write the new section file using section-writer agent (full eval/test/impl/rollback structure)
3. Update `sections/index.md` SECTION_MANIFEST: add the new line with `depends_on:`
4. Create tracker issue for the new section
5. Update downstream sections that should depend on the new section

### 5. AMEND — Modify a section's spec without changing its boundary

**When:** Implementation reveals the section spec is wrong or incomplete, but the section boundary is correct.

**Procedure:**
1. Log: `MUTATION: AMEND section-NN-name — {what changed and why}`
2. Edit the section file directly
3. If eval definitions change, note the delta in the log
4. No tracker changes needed — the section is still the same unit of work

## Audit Trail

All mutations are logged to `{planning_dir}/impl-mutations.md`:

Every mutation log entry MUST include these four fields. Vague reasons like "too complex" or "not needed" are not acceptable — the log must be decision-enabling for someone reading it later without other context.

```markdown
# Plan Mutations

## 2024-01-15T14:30:00Z — SPLIT section-03-parser
- **What changed:** section-03-parser split into section-03a-parser (parsing only) and section-03b-validator (validation + transformation)
- **Why:** Section estimated at 600+ lines with two independently testable concerns. Confidence gate scored 4/10 on scope — parsing is pure functions, validation has side effects (DB lookups), mixing them prevents parallel testing.
- **Downstream impact:** section-04-api dependency updated from section-03-parser to section-03b-validator. section-03a-parser has no downstream dependents.
- **Alternative considered:** AMEND to reduce scope by deferring transformation to section-04. Rejected because transformation is tightly coupled to validation (shares error types).

## 2024-01-15T16:00:00Z — SKIP section-05-migration
- **What changed:** section-05-migration removed from execution plan
- **Why:** section-02-config implementation revealed the database schema is already compatible — the column types match, no ALTER TABLE needed. Discovered during confidence gate (score: 2/10 on codebase context — migration target already exists).
- **Downstream impact:** section-06-integration dependency on section-05-migration removed. No other sections affected.
- **Alternative considered:** AMEND to convert migration section into a verification-only section. Rejected because verification is already covered by section-06-integration's regression evals.
```

## Reason Quality Requirements

Each mutation field serves a specific purpose:

| Field | Purpose | Bad Example | Good Example |
|-------|---------|-------------|--------------|
| **What changed** | Factual delta — what was the plan before, what is it now | "Split section 3" | "section-03-parser split into section-03a-parser (parsing) and section-03b-validator (validation + transformation)" |
| **Why** | Root cause — what evidence triggered this mutation | "Too complex" | "Confidence gate scored 4/10 on scope — 600+ lines with independently testable concerns" |
| **Downstream impact** | Dependency graph changes — who is affected | "Updated deps" | "section-04-api dependency updated from section-03-parser to section-03b-validator" |
| **Alternative considered** | Decision completeness — what else was evaluated and rejected | _(omitted)_ | "AMEND to reduce scope rejected because transformation is coupled to validation" |

## Rules

1. **Never mutate silently.** Every mutation must include all four fields.
2. **Validate the dependency graph after every mutation.** Circular dependencies = broken plan.
3. **Prefer AMEND over SPLIT** if the change is small.
4. **Mutations in auto mode:** Log and proceed. In interactive mode: inform the user before executing.
5. **Mutations are one-way.** Do not "un-split" or "un-skip" — if you need to reverse a mutation, create a new INSERT or AMEND.
6. **Reason quality is enforced.** A mutation with "Reason: too complex" will be flagged during final verification. Cite confidence scores, line estimates, or section outcome deviations.

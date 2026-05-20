# Discovery Bridge Protocol

When auto or standalone plan reaches the research or interview step after a discovery session, this protocol replaces `research-protocol.md`. It reuses discovery artifacts instead of re-researching from scratch.

**When this file applies:** When `discovery_findings` path is set in the task description AND the path contains discovery artifacts (`interview.md` + `findings/`). If artifacts are missing, fall back to `references/research-protocol.md`.

## Scope

| Mode | Phases that use bridge |
|---|---|
| `auto` non-first phases | Always |
| `auto` first phase | Only when discovery artifacts detected (otherwise self-interview) |
| Standalone `plan` | Only when `interview.md` + `findings/` detected in planning dir or parent |

---

## Phase A: Discovery Artifact Detection

Check if the `{discovery_findings}` path (extracted from the research step description) contains:

1. `findings/` directory with at least one `*.md` file
2. `research-topics.yaml`

**Optional artifacts (enhance quality but not required):**
- `interview.md` — stakeholder Q&A from discovery
- `build-vs-buy/` directory — package evaluations

### Decision

| What exists | Action |
|---|---|
| Neither `findings/` nor `research-topics.yaml` | **Fall back** to `references/research-protocol.md`. Close research steps with reason "No discovery artifacts — using standard research protocol." |
| `research-topics.yaml` exists but `findings/` is empty | **Fall back** — topics were enumerated but not researched |
| Both exist | **Proceed to Phase B** |

---

## Phase B: Discovery Findings Ingestion

### Step 1: Load Topic Manifest

Read `{discovery_findings}/research-topics.yaml`. Extract:
- Topic IDs, titles, categories, priority levels
- Coverage status (covered, skipped, pending)
- `findings_file` paths for covered topics

### Step 2: Read Phase Spec

Read the current phase spec file (`P{NN}-{name}.md` from the planning directory or `{discovery_findings}/phases/`). Extract scope keywords: technology names, capability names, domain terms.

### Step 3: Match Topics to Phase Scope

A discovery topic matches this phase if ANY of:
- Its **category** overlaps with the phase's domain (e.g., "authentication" topic matches an "auth-middleware" phase)
- Its **title** contains keywords from the phase spec
- It is **explicitly referenced** in the phase spec's gap analysis

### Step 4: Apply Budget

**Read at most 5 matching findings files per phase.** If more than 5 topics match, prioritize by the `priority` field in `research-topics.yaml`:
1. `high` priority topics first
2. Then `medium`
3. Then `low`

Within the same priority level, prefer topics whose category most closely matches the phase scope.

### Step 5: Read Matched Files

For each matched topic (up to 5):
- Read `{discovery_findings}/findings/{topic-id}-{slug}.md`

Also read matched `{discovery_findings}/build-vs-buy/*.md` files if the phase involves capabilities that were evaluated in build-vs-buy analysis.

### Step 6: Synthesize Research Output

Write `{planning_dir}/claude-research.md` containing:

```markdown
# Research (from Discovery Bridge)

> This research was derived from discovery artifacts, not fresh research agents.
> Discovery path: {discovery_findings}

## Relevant Discovery Findings

{Summarize each matched finding — key facts, not full copy. One subsection per topic.}

## Already Known (Do Not Re-Research)

{List questions that discovery already answered for this phase's scope.}

## Phase-Specific Gaps

{Questions that this phase needs answered but discovery did NOT cover.
 These drive Phase C gap-only research.}
```

If there are no gaps: close the research steps immediately with reason "Discovery findings sufficient for this phase — no gaps identified."

---

## Phase C: Gap-Only Research

If Phase B identified gaps in the "Phase-Specific Gaps" section:

1. Launch targeted research agents ONLY for the identified gaps
2. Use the same agent prompt patterns from `references/research-protocol.md` but scope each agent narrowly to one gap
3. Apply the BREVITY RULE: 500 words max per agent response
4. Append gap research results to `{planning_dir}/claude-research.md` under a new section:

```markdown
## Gap Research Results

{Results from targeted research agents, appended per gap.}
```

5. Close the research steps.

---

## Stale Discovery Detection

Before proceeding past Phase A, check for discovery/phase mismatch:

1. Read the top 5 topics from `research-topics.yaml` (by priority)
2. Compare their categories and titles against the current phase spec keywords
3. If **zero topics** have any keyword overlap with the phase spec, the discovery is likely from a different project scope

**Action on mismatch:** Fall back to `references/research-protocol.md`. Close research steps with reason "Discovery topics don't match this phase's scope — using standard research protocol."

This prevents a stale or mismatched discovery from producing irrelevant research context.

---

## Interview Passthrough

When this file is referenced for the interview step (any mode, any phase):

### If `{discovery_findings}/interview.md` exists:

1. Read the full interview transcript
2. Write to `{planning_dir}/claude-interview.md`:

```markdown
> Derived from discovery interview — not a new stakeholder conversation.
> Source: {discovery_findings}/interview.md

{Full interview Q&A, with annotations marking which answers are most relevant to this phase's scope.}
```

3. Close both `detailed-interview` and `save-interview` steps with reason "Interview derived from discovery transcript."

### If `{discovery_findings}/interview.md` does NOT exist:

- **auto non-first phases:** close interview steps with reason "No discovery interview available — skipping."
- **auto first phase with discovery detected:** same — close and skip.
- **Standalone plan with discovery detected:** close and skip.
- **auto first phase WITHOUT discovery:** self-interview (two subagents) — this file is not referenced in that path.

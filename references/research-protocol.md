# Research Protocol

This document defines the research decision and execution flow for steps 6-7 of the deep-plan workflow.

## Artifact Freshness Check

Before starting research, check if `claude-research.md` already exists in `{planning_dir}`:

```
IF claude-research.md exists AND mtime < 6h:
  Read it. Validate it covers the current spec topics.
  IF it covers ≥ 80% of spec topics: skip re-research, proceed to spec.
  IF gaps exist: research gaps only (append to existing file, do not rewrite).

IF claude-research.md exists AND mtime ≥ 6h:
  Treat as stale — run fresh research.

IF claude-research.md does not exist:
  Run full research per steps 6-7 below.
```

This prevents full re-research on session resume.

---

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│  RESEARCH FLOW                                              │
│                                                             │
│  Step 6: Decide what to research                            │
│    - Codebase research? (existing patterns/conventions)     │
│    - Web research? (best practices, SOTA approaches)        │
│                                                             │
│  Step 7: Execute research (parallel if both selected)       │
│    - Subagents return results                               │
│    - Main Claude combines and writes claude-research.md     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 6: Research Decision

### 6.1 Read and Analyze the Spec File

Read the spec file (from `initial_file` in task context items) and extract potential research topics by identifying:

- **Technologies mentioned** (React, Python, PostgreSQL, Redis, etc.)
- **Feature types** (authentication, file upload, real-time sync, caching, etc.)
- **Architecture patterns** (microservices, event-driven, serverless, etc.)
- **Integration points** (third-party APIs, OAuth providers, payment gateways, etc.)

Generate 3-5 research topic suggestions based on what you find. Format them as searchable queries with the CURRENT YEAR for recency.

**IMPORTANT:** Use the current year from the system context. NEVER hardcode "2025" or any specific year. The system prompt contains the current date — derive the year from it.

Examples (substitute the actual current year):
- "React authentication patterns {current_year}"
- "PostgreSQL full-text search best practices {current_year}"
- "Redis session storage patterns"
- "File upload security considerations"

If the spec is vague with no clear technologies, fall back to generic options:
- "General best practices for {detected_language/framework}"
- "Security considerations for {feature_type}"
- "Performance optimization patterns"

### 6.2 Ask About Codebase Research

Use AskUserQuestion to determine if there's existing code to analyze:

```
question: "Is there existing code I should research first?"
header: "Codebase"
options:
  - label: "Yes, research the codebase"
    description: "Analyze existing patterns, conventions, dependencies, and testing setup"
  - label: "No existing code"
    description: "This is a new project or standalone feature"
```

### 6.3 Ask About Web Research

Present the derived topics as multi-select options:

```
question: "Should I research current best practices for any of these topics?"
header: "Web Research"
multiSelect: true
options:
  - label: "{derived_topic_1}"
    description: "Based on spec mention of {X}"
  - label: "{derived_topic_2}"
    description: "Based on spec mention of {Y}"
  - label: "{derived_topic_3}"
    description: "Based on spec mention of {Z}"
  - label: "Other (I'll specify)"
    description: "Enter custom research topics"
```

If user selects "Other", follow up with a free-text question to get their custom topics.

### 6.4 Handle "No Research" Case

If user selects:
- "No existing code" AND
- No web research topics

Then skip step 7 entirely. But still ask about testing preferences for new projects:
- What testing framework to use (or recommend based on language/framework)
- Any testing conventions to follow

Note these preferences in `claude-research.md`.

---

## Step 7: Execute Research

### Critical Pattern: Subagents Return Results, Parent Writes Files

**DO NOT** have subagents write to files directly. This is important because:

1. **Avoids race conditions** - Parallel subagents writing to the same file would overwrite each other
2. **Context isolation** - Subagents keep verbose output in their own context, returning only summaries
3. **Parent control** - Main Claude decides final structure and handles file operations

```
┌─────────────────────────────────────────────────────────────┐
│  PARALLEL RESEARCH EXECUTION                                │
│                                                             │
│  Task 1: Explore ──────────┐                                │
│    (returns codebase       │                                │
│     findings as markdown)  ├──→ Main Claude combines       │
│                            │    and writes single          │
│  Task 2: web-search ───────┘    claude-research.md         │
│    (returns best practices                                  │
│     findings as markdown)                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.1 Codebase Research (if selected)

Launch Task tool with `subagent_type=Explore`:

```
Task tool:
  subagent_type: Explore
  description: "Research codebase patterns"
  prompt: |
    Research this codebase to understand:
    - Project structure and architecture
    - Existing patterns and conventions
    - Dependencies and how they're used
    - Testing setup (framework, patterns, utilities, how tests are run)

    Focus areas from user: {user_specified_areas_if_any}

    BREVITY RULE: Limit response to 500 words max. Use bullet points, not prose.
    Focus on specifics: file paths, patterns, dependencies, test setup.

    DO NOT write to any files. Return your findings in your response.
```

### 7.2 Web Research (if topics selected)

Launch Task tool with `subagent_type=web-search-researcher`:

```
Task tool:
  subagent_type: web-search-researcher
  description: "Research best practices"
  prompt: |
    Research current best practices for the following topics:
    {selected_topics_list}

    For each topic:
    1. Use WebSearch to find authoritative sources (official docs, respected blogs, recent articles)
    2. Use WebFetch on promising results to extract specific recommendations
    3. Cross-validate information across sources
    4. Synthesize findings with clear recommendations

    BREVITY RULE: Limit response to 500 words max. Bullet points with URLs,
    not prose paragraphs. Cite sources inline.

    DO NOT write to any files. Return your findings in your response.
```

### 7.3 Parallel Execution

If both codebase and web research are needed, launch **both Task tools in a single message**. This enables parallel execution.

```
# Single message with multiple tool calls:
[Task tool call 1: Explore subagent]
[Task tool call 2: web-search-researcher subagent]
```

Wait for both to complete, then proceed to combining results.

### 7.4 Combine Results and Write File

After collecting results from all subagents, combine them into `<planning_dir>/claude-research.md`.

Structure the file however makes sense for the findings. The goal is to capture useful research that will inform the implementation plan - there's no required format.

### 7.5 Throwaway scratch (optional)

For exploratory notes that informed `claude-research.md` but should NOT survive the session — e.g. comparing 3 libraries when only one made it into the plan, scratch benchmarks, half-formed prototype scripts — write them via `scripts/lib/scratch.write_scratch_artifact`:

```python
from pathlib import Path
from scripts.lib.scratch import write_scratch_artifact

write_scratch_artifact(
    Path(planning_dir),
    "oauth-library-comparison.md",
    body_text,
    delete_after="mode-complete",  # swept when Stop hook fires
)
```

Lands under `{planning_dir}/scratch/` with a THROWAWAY header. Auto-deleted at mode end by the Stop hook. Use this aggressively — clutter in `findings/` and `claude-research.md` is durable; scratch is not.

Do NOT use scratch for:
- Anything referenced by `claude-plan.md` / `claude-spec.md` / `findings/`
- Anything that would inform a future `/deep` run

---

## Edge Cases

| Case | Handling |
|------|----------|
| Spec file is vague | Present generic options based on any detected language/framework |
| User selects no research | Skip step 7, proceed to step 8 (interview). Still capture testing preferences for new projects. |
| Web research subagent fails | Log warning, write file with only codebase research (if it succeeded) |
| Both subagents fail | Log error, ask user if they want to retry or proceed without research |
| Only one research type selected | Run single subagent, write file with just that content |
| WebFetch returns truncated content | Subagent handles internally - notes incomplete info and tries additional sources |

---

## Example Flow

User runs `/deep plan @spec.md` → Claude extracts topics from spec → asks user which to research → launches codebase + web research subagents in parallel (single message, both Task calls) → combines results into `claude-research.md`.

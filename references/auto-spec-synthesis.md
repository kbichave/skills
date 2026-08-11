# Auto-Spec Synthesis

Converts a free-text inline prompt into a structured spec or objective file before the main workflow begins. Used when the user invokes `/deep` without a `@file` argument.

## When This Step Runs

Triggered when the `/deep` skill detects that the argument is:
- An inline text string (does not start with `@`, does not resolve to an existing path)
- Absent entirely (no argument provided)

## Step 1: Gather Project Context

Read the following without launching a subagent:

```bash
git log --oneline -30          # recent activity and direction
git status                     # what is in-flight right now
```

Then read (if they exist):
- `CLAUDE.md` at the project root
- `.claude/CLAUDE.md`
- `README.md` or `README.rst`

Then glob the top-level structure and read up to 5 key entry-point files (e.g. `main.py`, `app.py`, `src/`, `pyproject.toml`, `package.json`). Do not read more than 5 files.

## Step 2: Synthesize the Spec File

### For `plan` mode → write `{planning_dir}/claude-spec.md`

```markdown
# Spec: {concise engineering title, ≤ 8 words}

## Objective
{Restate the user's inline prompt as a precise engineering goal.
 One paragraph. Avoid restating what was said literally — interpret it.}

## Inferred Context
{What the codebase and git history reveal about related existing work.
 Mention specific files, modules, or recent commits that are relevant.
 If nothing is relevant, say so explicitly.}

## Scope
**In scope:**
- {specific deliverable 1}
- {specific deliverable 2}

**Out of scope:**
- {things that sound related but should not be included in this feature}
- {future work}

## Open Questions
{Things that need research or user clarification before planning can finalize.
 If there are none, write "None identified — sufficient context to proceed."}
```

### For `discovery` mode → write `{planning_dir}/objective.md`

```markdown
# Discovery Objective: {concise title}

## What We Want to Understand
{Restate the inline prompt as a discovery goal: what system, what aspects,
 what decisions does this discovery need to inform?}

## Inferred Scope
{From git history and codebase scan: what components are likely in scope?
 What areas should we intentionally skip?}

## Known Constraints
{Any constraints visible from the codebase: language, framework, deployment
 target, existing architectural decisions that must be respected.}

## Success Criteria
{What does a successful discovery produce? What decisions will be made with
 the output?}
```

## Step 3: Confirm with User

Show the synthesized file content to the user. Then ask:

> "Does this capture your intent? Reply with any corrections, or say **yes** to continue."

- If the user says **yes** (or equivalent): proceed with the synthesized file as `initial_file`.
- If the user provides corrections: apply them to the spec file in place (one revision pass). Then proceed without asking again.
- Do **not** loop more than once — if the user's correction is itself ambiguous, proceed with your best interpretation and note the ambiguity in the Open Questions section.

## Step 4: Proceed

Pass the synthesized file path as `initial_file` to `setup-session.py`. The rest of the workflow is identical to the `@file` path — the synthesized file is treated as the spec.

## Rules

1. **Never ask the user clarifying questions before synthesizing.** Synthesize first, then confirm.
2. **Do not read more than 5 source files during context gathering.**
3. **The spec must be opinionated.** Don't fill it with "TBD" or "depends on requirements." Make a reasonable interpretation and flag it in Open Questions if uncertain.
4. **The spec is not the plan.** It captures intent and scope — not implementation details.

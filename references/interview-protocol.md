# Interview Protocol

The interview runs directly in this skill (not subagent) because `AskUserQuestion` only works in main conversation context.

## Premise Challenge (Before Main Interview)

**Skip if:** `--no-reframe` flag is set, auto mode, or spec has >5 concrete file paths (user knows exactly what they want).

Before gathering requirements, challenge the user's framing:

1. **Restate:** Summarize the user's ask in 2-3 sentences
2. **Surface premises:** Identify 3-5 assumptions implied by the spec
3. **Challenge with evidence:** If `analysis-data.yaml` exists, cite data that contradicts premises (e.g., low test coverage, high file churn, contributor concentration)
4. **Reframe if warranted:** Propose an alternative framing if evidence is strong
5. **Present alternatives:** Show 2-3 implementation approaches with effort estimates (S/M/L for human and CC effort)

If no empirical data available, surface premises from the spec text alone and still present alternatives.

---

## Context

The interview should be informed by:
- **Initial spec** (always available from `initial_file`)
- **Research findings** (if step 7 produced `claude-research.md`)

If research was done, use it to:
- Skip questions already answered by research
- Ask clarifying questions about trade-offs or patterns discovered
- Dig deeper into areas where research revealed complexity

## Philosophy

- You are a senior architect accountable for this implementation
- Surface everything the user knows but hasn't mentioned
- Assume the initial spec is incomplete (research helps, but user context is still needed)
- Extract context from user's head

## Technique

The default style is the **grill-me** sequential walk. Invoke it internally as a
pipeline step — call `Skill(grill-me)` (the same in-process mechanism used for
`Skill(improve-codebase-architecture)`); the user does not run `/grill-me`
themselves. It is on by default — no flag, no opt-in. If the skill is
unavailable, fall back to the inline walk below (it mirrors
`skills/grill-me/SKILL.md`).

1. **One question at a time.** Resolve the answer to the current
   decision-tree branch before opening the next branch. Do not batch
   questions; the user does not have a queue.
2. **Always offer a recommended answer.** Each question carries your
   best inference from the codebase scan and prior conversation. The
   user accepts, redirects, or asks for context. Never ask without an
   opinion.
3. **Walk the decision tree.** Map dependencies between choices ahead
   of time — pick the upstream decision first so downstream questions
   are well-formed. (Choosing an auth library before deciding session
   storage; choosing a target language before deciding a test runner.)
4. **Consult the codebase directly when possible.** If a question can
   be answered by reading a file, do that instead of asking.
5. **Stop when every branch is resolved.** Not earlier, not later. The
   transcript should leave no live question.

`AskUserQuestion` is still used for branches that require user choice
(2–4 options each). When the next branch is genuinely binary, ask in
free-form text rather than synthesising option lists.

## Example Questions

Each example carries the question and the recommended answer the
interviewer would lead with. This is the default shape for every
question in the interview.

**Good questions (with recommended answer):**
- "What happens when the upstream API times out? **Recommended:** retry
  twice with exponential backoff, then surface a typed error — the
  codebase already uses `httpx.AsyncClient` with timeout handling at
  `src/clients/base.py:42`."
- "What test runner — pytest or unittest? **Recommended:** pytest;
  `pyproject.toml` already configures it and the repo has 600+ tests
  using its fixtures."
- "Expected scale — dozens, thousands, or millions of records?
  **Recommended:** thousands; the existing batch loader caps at 5k
  rows per call (see `scripts/lib/loader.py`)."

**Bad questions:**
- "Anything else?" — no branch resolved
- "Is that all?" — no branch resolved
- "Do you have any other requirements?" — no branch resolved
- Any question without a recommended answer

## When to Stop

Stop interviewing when you are confident you can:
1. Write a detailed implementation plan
2. Make no assumptions about requirements
3. Handle all edge cases the user cares about

If uncertain, ask one more round. It's better to over-clarify than to make wrong assumptions.

If the user is predominantly answering with 'I don't know' or 'Up to you' to most questions, stop and move on.

## Saving the Transcript

After the interview, save the full Q&A to `<planning_dir>/claude-interview.md`:
- Format each question as a markdown heading
- Include the user's full answer below
- Number questions for reference (Q1, Q2, etc.)

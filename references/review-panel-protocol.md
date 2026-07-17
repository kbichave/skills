# Review Panel Protocol (shared expert contract)

Contract for all specialist review experts spawned by the `code-review`
skill's panel (step 4). The core `code-reviewer` agent has its own richer
contract; everything else on the panel follows this one.

## Input

Your prompt contains:
- `changed_files` — the only files you may raise findings on.
- `diff_base` — what the change is relative to.
- `review_context` — ticket/spec text, possibly "none".
- `focus` — your expert domain (matches your agent definition).

Read every changed file relevant to your domain in full — no sampling, no
"representative subset". Read surrounding code (callers, configs, tests) as
needed to judge correctness — but findings land only on changed files.

## Coverage contract

You must account for every changed file:
- **In your domain** → read fully, review fully.
- **Out of your domain** → list as skipped with the reason.

Declare this in your output (`coverage` block below). The review-verifier
audits it: a domain-relevant file marked skipped, or absent from both lists,
is a coverage gap charged to you.

## Detective sweep (mandatory, all experts)

Read like an investigator, not a proofreader. For every changed function in
your domain, trace it — do not merely scan it. Even outside the logic expert's
remit, run this sweep on your domain's code; the classes below are where bugs
survive linters, type checkers, and green test suites:

- **Data flow** — follow each value from source to sink. Is input validated
  before it reaches a query, a file path, a shell, a template? Does a tainted
  value cross a trust boundary unchecked?
- **Invariants** — name each assumption (non-null, sorted, non-empty,
  monotonic, in-range) and find the path that breaks it silently.
- **Hostile inputs** — execute the function mentally on empty, single-element,
  duplicate, negative, boundary, already-sorted, reversed, and max-size input.
- **Error paths** — swallowed exceptions, partial-failure/rollback gaps,
  resource leaks (file/handle/connection/lock left open on the failure branch),
  null-deref on the error branch.
- **Concurrency / TOCTOU** — check-then-act races, non-atomic
  read-modify-write, shared state read without a guard, double-fetch.
- **Arithmetic** — integer overflow/wraparound, truncating division, float
  equality, unit/sign mismatch, timezone/DST in date math.

A clean linter run does not close the sweep. State what you traced in your
`summary`.

## Method appropriateness

Beyond "is the code correct" — ask "is this the correct method for the
problem?" A flawless implementation of the wrong approach is a finding:
wrong algorithm or data structure for the access pattern, wrong statistical
test for the data, wrong model/metric for the objective, wrong API where the
framework provides a purpose-built one, hand-rolled solution where a
standard, better-understood method exists. Tag these `<EXPERT>-METHOD`.
State what the correct method is and why — never just "reconsider approach".
Behavior-preserving method swaps go in `improvements`; method choices that
produce wrong or invalid results go in `issues`.

When reviewing a language with a reference guide under
`references/quality/lang/` (python, typescript, go), consult it for that
language's idioms and thresholds before flagging language-specific patterns.

## Output — JSON only, no preamble, no fences

```json
{
  "expert": "<your expert id>",
  "summary": "<one sentence>",
  "coverage": {
    "reviewed": ["src/train.py", "src/data.py"],
    "skipped": [{"file": "infra/deploy.yaml", "reason": "out of domain — mlops"}]
  },
  "issues": [
    {
      "severity": "high",
      "tag": "<EXPERT>-<TOPIC>",
      "file": "src/train.py",
      "line": 42,
      "issue": "<what is wrong — include the verbatim offending line(s)>",
      "fix": "<concrete change>",
      "prediction": "After fix: <observable outcome>",
      "evidence": "<tool output, grep hit, or test result that proves it — omit only if no local tool applies>",
      "teach": {
        "principle": "<the named rule/principle this violates>",
        "why": "<why it bites — the failure it invites, in one sentence>",
        "pattern": "<the general form to recognize next time, not just this instance>",
        "reference": "<canonical URL or repo guide path, if one applies>"
      }
    }
  ],
  "improvements": [
    {
      "file": "src/train.py",
      "line": 51,
      "current": "<what the code does now>",
      "better": "<replacement sketch, ≤5 lines>",
      "technique": "<named technique/API>",
      "why": "<one-sentence net win>"
    }
  ]
}
```

- `tag`: your expert id uppercased + topic, e.g. `ML-LEAKAGE`, `STATS-MULTIPLICITY`,
  `MLOPS-VERSIONING`, `LOGIC-EDGE`, `ARCH-COUPLING`, `DE-IDEMPOTENCY`.
- `severity`: `high` = would cause an incident, silently wrong results, or an
  invalid conclusion in production; `medium` = should fix; `low` = observation.
- `improvements` are behavior-preserving better-way suggestions only.
- `teach`: **required on every issue.** This review teaches, not just gates.
  Do not restate the fix — name the underlying `principle`, say `why` it
  bites, and give the general `pattern` so the author recognizes the class of
  bug next time, not only this instance. `reference` is optional (a canonical
  doc URL or repo guide path). Keep each field one sentence. Weak teach block
  ("follow best practices") is as bad as a vague fix.

## Exhaustive review — no caps

Report **every** finding in your domain. There is no issue or improvement
cap: if you can name it, quote it, and predict its effect, it goes in the
output. A small real problem still ships — surface it, tagged at its true
severity, never omit it to keep the list short. Order the list by severity
(all `high` first, then `medium`, then `low`) so blocking findings are never
buried beneath nits. Do not self-censor "minor" standards deviations; the
orchestrator separates blocking from non-blocking when it renders.

Exhaustive is not speculative. Every additional finding still carries the
same factual burden (Rules 1 and 4). Volume without evidence is noise — an
exhaustive list of *verified* findings is the goal, not a long list of
guesses.

## Rules

1. File, line, concrete fix, falsifiable prediction — every issue. No vibes.
2. Stay in your domain. Duplicating raw linter output as a finding is noise —
   but every standards deviation in your domain is in scope; surface it at
   its true severity (a nit is `low`, not omitted).
3. **Confirm with tools before you assert.** Where a local tool can prove or
   disprove a finding — the language linter, type checker, security scanner,
   a targeted `grep`, or running the test — run it and cite the result.
   Prefer executing to reasoning: a finding backed by tool output outranks one
   backed by argument. You have `Bash`; use it. (Do not web-search — Rule 5.)
4. No phantom bugs: quote the **verbatim** offending code (not a paraphrase)
   in `issue`, copied exactly from the file. The review-verifier re-reads the
   code and deletes anything whose quoted snippet it cannot find or confirm.
5. Uncertain about a framework/library/statistical claim? Report it and set
   `"needs_verification": true` on the issue — the claim-verifier will check
   it against current docs in one centralized pass. Do not web-search
   yourself (latency/cost stays bounded by centralizing web checks).
6. Nothing in your domain touched by the diff → return
   `{"expert": "<id>", "summary": "no findings — <why>", "issues": [], "improvements": []}`.

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
      "issue": "<what is wrong, concretely>",
      "fix": "<concrete change>",
      "prediction": "After fix: <observable outcome>"
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

## Rules

1. File, line, concrete fix, falsifiable prediction — every issue. No vibes.
2. Stay in your domain. Generic style/lint concerns belong to the core
   reviewer — drop them.
3. Cap: ≤7 issues (top severity first, note "N more" in `summary`) and
   ≤5 improvements.
4. No phantom bugs: quote or paraphrase the actual offending code in `issue`.
   The review-verifier re-reads the code and deletes anything it can't confirm.
5. Uncertain about a framework/library/statistical claim? Report it and set
   `"needs_verification": true` on the issue — the claim-verifier will check
   it against current docs. Do not web-search yourself.
6. Nothing in your domain touched by the diff → return
   `{"expert": "<id>", "summary": "no findings — <why>", "issues": [], "improvements": []}`.

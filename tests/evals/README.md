# Code-review skill evals

Per *"Don't Ship Skills Without Evals"* — a skill is worth shipping only if
evals prove it triggers correctly, avoids false positives, and improves
outcomes as base models evolve.

## Two layers

### 1. Structural (CI, automated)

`tests/test_code_review_evals.py` + `tests/test_comment_markers.py`. No live
model calls. Validates the case set shape, panel-agent structure against the
doc's rubric (≤500 lines, frontmatter, no no-ops), routing-table consistency,
and the deterministic marker logic. Runs on every change:

```bash
uv run --no-project python -m pytest tests/test_code_review_evals.py tests/test_comment_markers.py -v
```

### 2. Live behavioral (manual/periodic, deferred automation)

`code-review-cases.yaml` holds the prompt set — 5 golden / 5 negative / 5 edge.
The live runner (not yet built) drives the real CLI per the doc:

- Seed an isolated git workspace per case (clean checkout + the diff the case
  describes in its comment).
- Run `claude -p "<prompt>"` and capture transcript + exit code.
- Evaluate the case's `checks` (deterministic: Agent-spawn set, AskUserQuestion
  presence, `.reviews/` file, marker idempotency) against the transcript.
- `should_trigger: false` cases assert the skill did NOT fire (anti-hijack).
- Run multiple trials per case — agent behavior is nondeterministic; a single
  pass/fail is not enough signal.
- Reserve the `llm_judge` block for qualitative report quality only.

## Ablation (Tip 8 — retire when base models catch up)

**Cadence:** quarterly. **Question:** does the panel still beat no skill?

1. Run the live case set with the panel installed → record verified-findings
   per review and the verifier false-positive rate (verifier rejections ÷
   panel-raised).
2. Run the same diffs with a bare "review my code" prompt and the skill
   *uninstalled* → baseline.
3. Compare:

| Metric | With panel | No skill | Keep if… |
|--------|-----------|----------|----------|
| Verified findings / review | | | panel materially higher |
| False-positive rate | | | panel not worse |
| Wall time / tokens | | | lift justifies cost |

Keep the panel (or an individual expert) only where the gap is real. Retire or
slim any expert whose lift has closed as models improve — every retired expert
saves context tokens and latency.

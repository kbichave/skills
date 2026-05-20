# External Review Protocol

This step sends `claude-plan.md` for independent review. The review mode determines how the review is performed.

## Review Modes

Check `review_mode` from task context (e.g., `review_mode=opus_subagent`).

| Mode | When Used | Action |
|------|-----------|--------|
| `external_llm` | External LLMs configured (default) | Run review.py |
| `opus_subagent` | No external LLMs, user chose Opus | Launch Opus subagent |
| `sonnet_subagent` | No external LLMs, user chose Sonnet | Launch Sonnet subagent |
| `skip` | User chose to skip review | Skip to step 16 |

---

## Mode: external_llm (Default)

Run unified review script:
```bash
uv run --directory {plugin_root} scripts/llm_clients/review.py --planning-dir "{planning_dir}"
```

The script automatically:
- Detects which LLMs are available (Gemini, OpenAI, or both)
- Runs available reviewers in parallel (if both) or single-threaded (if one)
- Writes results to `{planning_dir}/reviews/`

### Output Format

The script returns JSON:
```json
{
  "reviews": {
    "gemini": {"success": true, "provider": "gemini", "model": "...", "analysis": "..."},
    "openai": {"success": true, "provider": "openai", "model": "...", "analysis": "..."}
  },
  "files_written": ["reviews/iteration-1-gemini.md", "reviews/iteration-1-openai.md"],
  "gemini_available": true,
  "openai_available": true
}
```

### Handling Failures

- If one LLM fails, the other still runs
- Script exits 0 if at least one review succeeds, 1 if all fail

---

## Mode: opus_subagent

Print status:
```
═══════════════════════════════════════════════════════════════
STEP 13/22: OPUS PLAN REVIEW
═══════════════════════════════════════════════════════════════
Launching Claude Opus subagent for plan review...
```

**Steps:**

1. Launch subagent (passes file path, not content):
```
Task(
  subagent_type: "opus-plan-reviewer",
  model: "opus",
  prompt: "Review the implementation plan at: {planning_dir}/claude-plan.md"
)
```

2. Create reviews directory if needed:
```bash
mkdir -p "{planning_dir}/reviews"
```

3. Write subagent output to `{planning_dir}/reviews/iteration-1-opus.md`:
```markdown
# Opus Review

**Model:** claude-opus-4-6
**Generated:** {ISO timestamp}

---

{subagent_output}
```

4. Proceed to step 14 (integrate feedback)

---

## Mode: sonnet_subagent

Same as `opus_subagent` but uses Sonnet (faster, cheaper, still high quality).

Print status:
```
═══════════════════════════════════════════════════════════════
STEP 13/22: SONNET PLAN REVIEW
═══════════════════════════════════════════════════════════════
Launching Claude Sonnet subagent for plan review...
```

**Steps:**

1. Launch subagent (passes file path, not content):
```
Task(
  subagent_type: "opus-plan-reviewer",
  model: "sonnet",
  prompt: "Review the implementation plan at: {planning_dir}/claude-plan.md"
)
```

2. Create reviews directory if needed:
```bash
mkdir -p "{planning_dir}/reviews"
```

3. Write subagent output to `{planning_dir}/reviews/iteration-1-sonnet.md`:
```markdown
# Sonnet Review

**Model:** claude-sonnet-4-6
**Generated:** {ISO timestamp}

---

{subagent_output}
```

4. Proceed to step 14 (integrate feedback)

---

## Mode: skip

Print status:
```
═══════════════════════════════════════════════════════════════
STEP 13/22: EXTERNAL REVIEW - SKIPPED
═══════════════════════════════════════════════════════════════
External review skipped per user choice.
Proceeding to TDD planning.
───────────────────────────────────────────────────────────────
```

Skip directly to step 16 (TDD approach). Steps 14-15 are not applicable.

---

## Output Location

All modes write to `{planning_dir}/reviews/`:
- `iteration-1-gemini.md` - Gemini review (external_llm mode)
- `iteration-1-openai.md` - OpenAI review (external_llm mode)
- `iteration-1-opus.md` - Opus review (opus_subagent mode)
- `iteration-1-sonnet.md` - Sonnet review (sonnet_subagent mode)

---

## Stall Detection (revision loop)

After each `integrate-feedback` iteration that re-runs review (iteration ≥ 2), invoke the stall detector before launching the next round:

```python
from scripts.lib.stall_detector import StallDetector

detector = StallDetector(min_diff_ratio=0.10)
# Record every revision recorded so far in this session
for iteration in iterations_so_far:
    detector.record_revision(
        label=f"iteration-{iteration.n}",
        text=iteration.plan_text,            # claude-plan.md content for that iteration
        findings=iteration.review_findings,  # bullet list from reviewer JSON
    )
verdict = detector.check()
```

If `verdict.stalled` is True:

- **Interactive mode:** surface `verdict.reason` via `AskUserQuestion` with options:
  - "Accept current plan and proceed" — close review with reason quoting the verdict
  - "Force one more revision" — continue loop (max 3 total)
  - "Abort planning" — exit
- **Auto mode:** accept-with-caveat. Append the verdict to `claude-plan.md` under `## Review caveats` and close review with reason "Stall detected — accepted with caveat".

A stall verdict is information, not failure. The artifact may already be good enough; the loop has just stopped sharpening it.

Hard cap: ≤3 revision iterations regardless of stall detection. After iteration 3, accept or abort — never iterate further.

# Goalloop Protocol

`/deep goalloop` runs the SDLC as a loop toward an end state, instead of
executing a plan someone already wrote.

`auto` needs phases enumerated first — discovery produces them, and the run
executes them. `goalloop` starts one step earlier, from "here is where I want
to end up", and carves the phases as it goes. Each iteration takes the next
increment off the ledger, writes it as an intent, plans it, implements it,
records what it learned, and goes again.

```
goal + acceptance lines          (durable — never rewritten mid-run)
  └ ledger of increments         (fixed by default; new information is triaged)
      └ iteration N
          begin → intent → plan → implement → evidence → end → tick
                                                              ├ exit 3 → iterate
                                                              ├ exit 0 → done
                                                              └ exit 1 → stop, report
```

State lives in `<planning_dir>/.deepstate/goalloop.json`, with a readable
mirror at `<planning_dir>/goal-ledger.md`. Every command below is
`scripts/checks/goalloop.py --planning-dir "${planning_dir}" <subcommand>`;
`${GL}` is shorthand for that prefix.

```bash
GL="python3 ${DEEP_PLUGIN_ROOT}/scripts/checks/goalloop.py --planning-dir ${planning_dir}"
```

---

## §1 Capture the goal

The goal is set once by `setup-session.py --workflow goalloop` and does not
change for the life of the run. Everything else may.

**Acceptance lines are the load-bearing part.** They are what evidence gets
checked against, and a goal without them can only ever stop at its iteration
ceiling. Each line must be an observation someone could make:

| Bad | Good |
|---|---|
| The pipeline is reliable | No run in a week of nightlies exits non-zero |
| The board is fast | A rack change appears on the board within 60s, measured end to end |
| Code quality improves | `ruff check` reports zero new violations against the base commit |
| Users are happy | No operator touches a spreadsheet in the path |

Read the goal back to the user with its lines numbered, and say which ones you
had to sharpen. A line you invented and they did not agree to will still be
holding the loop open at iteration nine.

If the user gave a goal with no measurable end state at all, say so and ask
for one. This is the single blocking question in the mode — proceeding without
it produces a run that cannot terminate.

---

## §2 Probe the target

If the target already has discovery artifacts (`interview.md` + `findings/`),
the step's description says so and names the path: ingest them per
`discovery-bridge.md` and do not re-audit. The step still runs — it is not
pre-closed, because `goal-questions` depends on it alone, and closing it at
creation would make the clarification round ready before the goal was
captured.

Otherwise run the audit workflow at `--depth quick` against the target and
use its `scan-summary.md` and findings as the base context. Do not run
`standard` or `deep` — a full audit before the first increment spends the
run's budget on a map of territory the loop may never enter.

This step exists to serve §3. Most of what you would otherwise ask the user is
written down in the repository, and the clarification round scores those
questions at zero.

---

## §3 Decompose into the initial ledger

Write the increments the goal breaks into, in the order they should ship.

```bash
${GL} add --title "read path behind a feature flag" \
  --acceptance "flag off reproduces old behaviour, proven by a test"
${GL} add --title "backfill job, idempotent" \
  --acceptance "runs twice against the same window, identical row count"
${GL} add --title "cutover and delete the flag" \
  --acceptance "no reference to the flag remains, old path deleted"
```

What makes an increment an increment:

- **Individually shippable.** If the repo were frozen after this increment,
  nothing is half-built. "Add the column" ships. "Start the migration" does not.
- **One acceptance line, its own.** The CLI refuses an increment without one,
  because a loop that decides for itself whether an increment is done decides
  yes.
- **Ordered by dependency, not by size.** The ledger is a queue, and the loop
  takes the front of it.
- **Five to nine of them for a normal goal.** Two means the decomposition did
  no work; twenty means increments are tasks.

The ledger is a hypothesis about the shape of the work. It is allowed to
change — through §4's triage, not by rewriting it.

---

## §4 The iteration

### 4.1 Begin

```bash
${GL} begin
```

Returns the iteration number and the increment to work. It resumes rather
than double-starting, so it is safe after a compaction — which makes it the
first thing to run when you are unsure where the loop is.

Refuses when the ledger has nothing pending. If that refusal names blocked
increments, the run is over: go to §5.

### 4.2 Write the increment as an intent

The increment becomes an intent in the iteration's own directory, following
`intent-capture.md`:

```bash
mkdir -p "${planning_dir}/iterations/i0N"
python3 ${DEEP_PLUGIN_ROOT}/scripts/checks/intent.py new \
  --title "<increment title>" --out "${planning_dir}/iterations/i0N/intent"
```

Three rules, none negotiable:

- **The intent stays `status: draft`, `source: agent`.** The loop never writes
  `accepted`. Only a person accepts an intent, and `decide --by` must be a
  real answer from them, never your inference.
- **Publishing to the target repo is confirm-first.** `intent.py publish`
  writes into the user's tree; ask before running it. Without it the intent
  stays in the session directory, which is where an unaccepted intent belongs.
- **Trace it to the goal.** Every requirement in the intent maps to an
  acceptance line or to the increment's own acceptance. Anything that maps to
  neither is scope you are adding — say so rather than smuggling it in.

Carry forward what earlier iterations learned: read `goal-ledger.md`'s triage
log and the previous iteration's `impl-progress.md` before writing this one.
An iteration that repeats a mistake iteration three already made is the loop
failing to be a loop.

### 4.3 Plan the increment

```bash
uv run ${DEEP_PLUGIN_ROOT}/scripts/checks/setup-session.py \
  --file "${planning_dir}/iterations/i0N/increment.md" \
  --plugin-root "${DEEP_PLUGIN_ROOT}" --workflow plan \
  --from-intent "${planning_dir}/iterations/i0N/intent/<intent-file>.md" \
  --review-mode "${review_mode}" --session-id "${DEEP_SESSION_ID}"
```

Each iteration plans in its own nested session, so the parent goalloop
tracker stays legible and a failed iteration does not corrupt the next one.
Record where that session landed:

```bash
${GL} begin --dir "<planning_dir from the JSON above>"
```

`begin` resumes the open iteration and attaches the directory. This is what
lets the done test find the iteration's verification results — skip it and
`gates_green` never sees the work.

Then run the plan workflow to completion in that nested session, and
`implement` after it, per `implement-protocol.md`. Every section records its
outcome with `auto-gate.py record` as usual. Those records are the evidence
the done test reads.

### 4.4 Triage what the iteration turned up

Implementation discovers things. Each discovery gets classified, once,
explicitly — the loop never infers the kind from the text:

| Test | Kind | Command |
|---|---|---|
| The current increment cannot land until this does | blocker | `triage --kind blocker` |
| It can wait its turn | deferrable | `triage --kind deferrable` |

```bash
${GL} triage --kind blocker \
  --title "source table has no updated_at" \
  --acceptance "column added and backfilled for the last 30 days" \
  --because "cannot detect a rack change without it"
```

A blocker jumps the queue, the displaced increment returns to pending with a
note saying what displaced it, and the pass in progress is recorded as
`preempted`. A deferral is spliced in behind the active increment and work
continues.

Ask before reaching for `blocker`: does the current increment genuinely not
land without it? A loop that treats every discovery as a blocker never
finishes an increment, and the ledger becomes a stack.

When an increment turns out to be two things rather than one:

```bash
${GL} split --increment I04 \
  --slice "drop the reads :: no caller reads the old table" \
  --slice "drop the table :: table is gone, migration applied"
```

### 4.5 Record evidence

This is the step most easily skipped and the one that decides whether the run
can ever finish. When an iteration produces an observation bearing on an
acceptance line, record it against that line:

```bash
${GL} evidence --acceptance-id A1 \
  --source "tests/test_price_board.py::test_end_to_end_under_60s" \
  --detail "p95 41s over 200 runs"
```

`--source` names an artifact: a test, a report path, a command whose output
was recorded. **An acceptance line is met by evidence, never by an argument
that it is met.** "The board should now refresh well under two seconds
because the write path is synchronous" is reasoning, not evidence. Run it and
record the number.

If an iteration produced no evidence for any acceptance line, that is worth a
sentence in the summary. It may be correct — plumbing increments often
evidence nothing — or it may mean the loop is building around the goal rather
than toward it.

### 4.6 End and tick

```bash
${GL} end --outcome delivered --detail "shipped behind price_board_v2"
${GL} tick
```

`--outcome` is `delivered`, `blocked`, or `dropped`. Use `blocked` when the
increment needs a person — a decision you are not entitled to make, or a
dependency that never landed. A blocked increment is never picked up again
automatically, which is deliberate: whatever the loop could clear on its own
it already cleared.

`tick`'s exit code is the loop:

| Exit | `stop_reason` | What you do |
|---|---|---|
| 3 | `running` | Start iteration N+1 at §4.1 |
| 3 | `measurement_needed` | Everything is delivered and green, and an acceptance line has no measurement. Take it and record it (§4.5), or add an increment that takes it. If it genuinely cannot be measured, stop and say so — do not record an argument as evidence. |
| 0 | `goal_met` | Go to §5, then stop |
| 1 | `blocked_on_human` / `iterations_exhausted` | Go to §5, report, stop |
| 2 | — | Usage or I/O error. Fix the call; do not proceed on a guess |

`measurement_needed` exists because halting there hands back a run that was
one command from finished. It is the only verdict where the next action is a
measurement rather than an increment.

**Do not iterate past exit 1, and do not stop on exit 3.** An autonomous run
that keeps going after `blocked_on_human` burns the afternoon on work it
cannot finish; one that stops on `running` hands back an unfinished job it was
asked to complete.

The iteration ceiling, if the user set one, is enforced here: `tick` returns 1
with `stop_reason: iterations_exhausted`. A goal met on the final allowed pass
reads as `goal_met`, not as out of budget.

---

## §5 Verify and report

Run the done test once more and report its verdict as it stands:

```bash
${GL} tick
${GL} handoff
```

Three clauses, all of which must hold. Each catches a different way a loop
lies about being finished:

| Clause | Holds when | Catches |
|---|---|---|
| `ledger_clear` | Nothing pending, active, or blocked | Declaring victory with work still listed |
| `gates_green` | Every section recorded `passed`, needs-human queue empty | Shipping code that does not compile |
| `acceptance_evidenced` | Every acceptance line points at a recorded artifact | Building all the right parts and never checking the thing the user asked for |

`gates_green` inherits `verification.py`'s rule that a section which never
recorded a result counts as `human_needed`. Absence of evidence is the usual
way an autonomous run convinces itself everything is fine.

Write `handoff`'s output to `goal-summary.md`, and append the needs-human
queue from every iteration directory:

```bash
for d in "${planning_dir}"/iterations/*/; do
  python3 ${DEEP_PLUGIN_ROOT}/scripts/checks/auto-gate.py \
    --planning-dir "$d" handoff
done >> "${planning_dir}/goal-summary.md"
```

**Report the verdict verbatim.** Do not restate an unmet clause as met, and do
not summarise "two of three clauses hold" as success. A run that stops without
saying plainly what is left has not reported.

---

## Guardrails

1. **The goal is durable.** If it turns out to be the wrong goal, stop and say
   so. Do not quietly re-aim the loop at something achievable.
2. **The ledger is fixed by default.** Change it through `triage` and `split`,
   which record why. A run free to re-plan every iteration re-plans forever.
3. **Ask rarely and well.** Run the clarification round at `--budget 2`
   (`question-selection.md`). A mode that stops to ask twice an iteration is
   not autonomous. Residual uncertainty is yours to absorb and state as an
   assumption.
4. **Intents stay draft; publishing is confirm-first.** §4.2.
5. **A skipped increment is still reported.** Every blocked or dropped
   increment lands in the summary. This is the `--auto` rule from
   `implement-protocol.md`, and it holds here for the same reason.
6. **`tick` decides, not you.** It reads recorded artifacts. Your assessment
   of whether the goal is met is not an input.

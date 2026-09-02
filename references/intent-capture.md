# Intent capture — the problem, in the originator's words

Playbook Stage 1. `/deep intent` produces `intent.md`: what someone wants and
why, recorded before anyone decides how to build it.

## Why this is not `claude-spec.md`

`auto-spec-synthesis.md` interprets an ask into "a precise engineering goal".
That is correct at plan time and wrong here. An intent is evidence of what was
asked for, so the spec can be traced back to it and a reader six months later can
tell whether the thing that got built was the thing that was wanted.

Concretely, the difference:

| | Intent | Spec |
|---|---|---|
| Voice | The originator's | Engineering's |
| "Slow" means | "the price board lags the rack by about 40 minutes" | "p95 propagation latency > 2400s" |
| Owns | The problem | The solution shape |

**Do not translate the problem into engineering terms.** If the originator said
"the price board is always behind", that is the sentence that goes in
`## Problem`. Your latency analysis belongs in the spec.

## Do not re-derive what the synthesizer already handles

`/deep plan` already reads git history, `CLAUDE.md`, and the codebase to build
context. Intent capture must not re-ask any of it. **Cap: 6 questions.** If you
are asking a seventh, you are gathering spec input, not intent.

The cap is a ceiling, not a target. Score the candidates first
(`question-selection.md`): here the hypotheses are the distinct *problems* the
report could be describing, not the plans, and a question earns its place by
ruling some of them out. Six questions that change nothing are worse than two
that separate "the board is stale" from "the board is wrong".

Ask only what the codebase cannot answer:

- What is the problem, in your words?
- Who is affected, and roughly how many?
- What does "solved" look like?
- What must not change (budget, deadline, systems, compliance)?
- How will we know it worked — ideally a number with today's baseline?
- What is deliberately out of scope?

## Grill the intent before proposing it

Run the **grilling** walk over the draft — call `Skill(grilling)` internally as a
pipeline step, the same in-process mechanism `interview-protocol.md` and
`audit-interview-protocol.md` use. The user does not run it themselves. If the
skill is unavailable, fall back to the inline challenge list below.

Grilling an intent is not the same as grilling a plan. You are not stress-testing
an approach; there is no approach yet. You are testing whether the **problem** is
real, owned, and measurable:

1. **Is this the problem, or a symptom of one?** "The dashboard is slow" is often
   "we query the wrong table". Push one level up: what breaks for a person
   because of this? Record the root if the originator agrees, keep their framing
   if they do not — and note the disagreement in `## Open questions`.
2. **Who actually asked?** An intent with no named affected party is usually
   someone's preference. Name the role or business unit.
3. **What happens if we do nothing?** If the answer is "nothing much", that is
   worth knowing before a plan gets written.
4. **Is the success metric checkable by someone else?** "Faster" is not.
   "Under 5 minutes, from today's 40" is. If there is no baseline, ask for one.
5. **What is the constraint nobody stated?** Deadlines tied to a season, a system
   that cannot be touched, data that cannot leave a region.
6. **What is out of scope?** An empty `## Out of scope` on a real problem almost
   always means scope has not been discussed yet.

When the user supplies documents — a PRD, a ticket, a Confluence page — grill
**against them**: quote the passage, then ask what it does not say. Documents are
strongest as a source of contradictions between what is written and what the
originator says they meant.

Stop when every branch is resolved. Do not grill an intent the originator has
already thought through; the cap still applies.

## Status lifecycle

`draft → proposed → accepted | rejected | superseded`

- **draft** — being written. `/deep intent` leaves it here.
- **proposed** — the originator is ready for a decision.
- **accepted** — approved; `--from-intent` will carry it into `/deep plan`.
- **rejected** / **superseded** — terminal. Re-deciding is refused; supersede
  with a new intent instead.

`decided_by` is mandatory on any decision and must come from a real answer, not
an inference. **Auto mode never writes `accepted`** — it leaves `status: draft`
and `source: agent`, and says so in the summary. A decision the agent filled in
on the user's behalf looks like an audit trail without being one, which is worse
than having none.

## Publishing

Session artifacts live outside the target repo by design. `intent.md` is the
exception, because the playbook's audit trail is git history and because Stage 2
needs to read it — but it is opt-in, never automatic:

- `--publish <dir>` writes into the repo (default `docs/intent/`, one file per
  intent, named `<id>.md`).
- `--commit` additionally stages **that one file** and commits it, after showing
  the message and asking. No `-A`, no amend, no push.

Without `--publish` the intent stays in the session directory and nothing touches
the working tree.

## Where intents come from

Two sources, and the schema carries which:

- `source: human` — someone ran `/deep intent`.
- `source: agent` — Stage 6 maintenance raised it from a breached control band
  or a scheduled scan. These always land as `draft` for triage; an agent may
  report a problem, never approve one.

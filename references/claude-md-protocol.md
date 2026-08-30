# CLAUDE.md as a build artifact

Playbook Stage 3 treats a target repo's `CLAUDE.md` as version-controlled
institutional knowledge that Claude both reads and updates: build and test
commands, conventions, architecture, and the mistakes worth not repeating.

`/deep` reads `CLAUDE.md` (via `auto-spec-synthesis.md`) but has never written
one. This is the protocol for closing that.

## Do not reimplement the improver

A `claude-md-improver` skill already exists and does the auditing well. Call it:

```
Skill(claude-md-improver)
```

Use it when the target repo has a `CLAUDE.md` that is thin, stale, or full of
template placeholders. Only fall back to writing directly when the skill is
unavailable.

## When to offer

**Offer, do not impose.** `CLAUDE.md` lives in the user's repo and shapes every
future session there; generating one unasked is a side effect they did not
request.

Two moments are worth offering at:

1. **End of `/deep plan`.** Plan mode has just computed everything the file
   wants — the build and test commands from `quality_gate.build_gate()`, the
   detected languages and active packs from `pack_router`, the architecture
   summary from research, and the conventions from the interview. That
   information is free at this point and expensive later.
2. **Phase 10 post-mortem, on a repeat.** When the same class of mistake shows
   up in a second section, that is the signal the playbook names.

## The repeat-mistake loop

Today Phase 10 writes `## Architectural follow-ups` and `## Spec gaps observed`
into `impl-summary.md`, which lives in the session directory outside the target
repo. Nothing flows back, so the same mistake is available to be made again next
session.

The rule for promoting a post-mortem finding into `CLAUDE.md`:

- **Twice is the threshold.** One occurrence is an incident; two is a pattern.
  Check `impl-summary.md` from prior sessions in the same planning directory.
- **Promote the rule, not the incident.** "Money is always `BigDecimal`, never
  `double`" belongs there. "Fixed the rounding bug in `invoice.py`" does not —
  that is what the commit message is for, and it rots.
- **One line, imperative.** If it needs a paragraph, it belongs in a reference
  file with a pointer from `CLAUDE.md`.
- **Confirm before writing.** Same rule as any other repo write.

## What belongs in it

Derived from what actually helps a cold session, not from a template:

| Section | Source |
|---|---|
| Build and test commands | `quality_gate.build_gate()`, `lint/<lang>/adapter.json` |
| Verification before "done" | The gate the repo actually enforces |
| Architecture overview | Plan-mode research, a table not an essay |
| Conventions | Interview answers plus observed patterns |
| Common mistakes | Phase 10 post-mortems, promoted on the second occurrence |

## What does not belong

- Anything derivable by reading the code in ten seconds.
- Task state, current work, or session context — that is what the tracker is for.
- Aspirations. A convention nobody follows is worse than no convention, because
  it teaches the reader to discount the whole file.

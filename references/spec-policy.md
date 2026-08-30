# Policy at spec time

Playbook Stage 2 wants organizational policy applied **while the spec is
written**, not discovered at review time when the code already exists. The
plugin has the corpus (13 rule packs) and the resolver (`pack_router`); until
now both only fired at implement time.

## What this is

A projection, never a second resolver. `policy_router` imports `pack_router`,
calls it, and turns the active packs' rules into a bounded list of questions the
spec should answer. A test asserts both agree on `active_packs`, because two
resolvers drift and then nobody knows which is right.

```python
from lib.policy_router import resolve_spec_context
context = resolve_spec_context(target_root, packs_dir, spec_text=spec_text)
```

## Which rules become obligations

Only those a **human or reviewer** must judge, at **BLOCK or WARN** severity.

Linter-enforced rules are excluded deliberately. Asking a spec author to promise
that `ruff` will pass is noise — the Phase 6 gate answers that, and better.

## Answer them; do not just relay them

This is the rule that decides whether the feature helps or becomes a
compliance interrogation.

For each obligation, **answer it from research and the interview**. Write the
answer into the spec. Flag a concern only where you are not entitled to decide:
a real trade-off, a policy question, an unknown that materially changes the
design.

- **Hard cap: 25 obligations.** Above that the list is truncated, BLOCK-first,
  and says so.
- **More than five open concerns means you are flagging things you could have
  answered.** Go back and answer them.
- **Two resolution rounds, maximum.**

If the spec phase starts feeling like a questionnaire, that is the failure mode,
not the feature working.

## Mode

Ships `advise`: obligations inform the spec, nothing blocks. This matches the
plugin's own convention that new BLOCK rules ship as WARN for one release
(`docs/quality-pipeline-plan.md`).

## Sign-off, when it lands

Not built yet, and worth stating the constraint now: **a sign-off record the
agent filled in on the user's behalf is worse than none.** It looks like an
audit trail without being one.

So when the governance layer lands:

- `resolved_by` must come from a real `AskUserQuestion` answer or an
  MCP-fetched approval (a Jira transition, a Confluence comment) — never an
  inference.
- Auto mode writes `unresolved-auto`, never `approved`.
- The plugin cannot verify identity. These are attestations, not
  authentication, and the docs must say so plainly.

## Organizational policy the plugin cannot ship

Brand, tone, privacy and regulatory constraints are genuinely organizational and
cannot live in a public plugin. Build the **seam**, not stub packs nobody fills
in: an organization brings its own pack directory and its own policy skills.
Empty stubs rot into dead weight that makes the feature look broken.

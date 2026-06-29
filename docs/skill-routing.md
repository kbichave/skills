# Skill-aware Routing

`/deep` consults a `skill-router` subagent at major workflow hook
points. The router enumerates every skill installed on the machine
and decides whether each one is relevant to the current `/deep` step.

> **Distinct from quality-pack routing.** `skill-router` routes *skills* by
> keyword/description against installed skills. The **quality pipeline** uses a
> separate resolver, `scripts/lib/pack_router.py`, which inspects the *target*
> repository (languages, project type, changed globs, task type) to decide which
> rule packs under `references/quality/` are active. The two are independent: one
> picks skills, the other picks rule packs. See `docs/quality-pipeline-plan.md`.

## Why

Users install skills constantly — `claude-api`, `code-review`,
`security-review`, `humanizer`, `internal-comms`, `pptx`, project- or
team-specific skills, plus the seven vendored Matt Pocock skills.
`/deep` was previously blind to all of them; that left the user
re-invoking those skills by hand even when the current step was
unambiguously inside the skill's stated trigger conditions.

The router fixes that without giving up control. The user still
decides everything except the unambiguous cases.

## Discovery

`scripts/lib/skills_registry.py::enumerate_skills()` scans:

1. `<project>/.claude/skills/` — project-scoped skills
2. `~/.claude/plugins/cache/*/<version>/skills/` — plugin-installed
3. `~/.claude/skills/` — user-level

Each `SKILL.md` is parsed for its YAML frontmatter (`name`,
`description`, optional `triggers`). When the same skill name appears
in multiple locations the project-level entry wins (matching Claude
Code's own resolution order).

## Confidence tiers

* **HIGH** — auto-invoke. The current step is unambiguously inside
  the skill's trigger conditions. Examples:
  - file imports `anthropic` → `claude-api`
  - section is being prepared for commit → `code-review` self-check
  - draft is prose for the user to send → `humanizer`
* **MEDIUM** — surface a single multi-select `AskUserQuestion`. The
  router collapses multiple medium matches into one prompt rather
  than firing several in a row.
* **LOW** — log only. The decision is appended to
  `findings/skills-considered.md` for transparency.

The hard rules:

* Side-effect skills (`pr-reply`, `schedule`, `loop`, `internal-comms`,
  `pptx`, `pptx-gp-template`, `browser-automation:Browser-Automation`)
  are demoted to MEDIUM regardless of keyword match. The hard list
  lives at `scripts/lib/skills_registry.py::SIDE_EFFECT_SKILLS`.
* `deep` and the seven vendored Matt Pocock skills are excluded from
  routing — they are wired inline by the calling `/deep` step.
* `--no-skill-routing` disables routing entirely for the session and
  every entry is logged with `reason: "routing disabled"`.
* In `/deep auto` mode the router only considers HIGH matches —
  there is no human to answer prompts.

## Hook points

| `/deep` step | Skills usually checked |
|---|---|
| Post-exploration (discovery, plan) | `karpathy-guidelines`, `code-review`, `claude-api`, `mcp-builder` |
| Pre-interview | `karpathy-guidelines` |
| Per section start (implement) | `claude-api`, `security-review`, `mcp-builder`, `simplify` |
| Per section end | `code-review` (self-check), `simplify` |
| Output is prose (audit doc, internal update) | `humanizer`, `internal-comms` |
| PR / commit prep | `caveman:caveman-commit`, `code-review`, `security-review` |
| PR reply text | `pr-reply` |

The table is heuristic; the registry plus the runtime context block
is the source of truth.

## Mute list

Persistent per-skill mute via `~/.claude/deep/muted-skills.json`:

```json
{
  "skills": ["code-review", "internal-comms"]
}
```

The router skips muted skills and logs the reason as
`in mute_list`. Useful when a skill conflicts with another tool you
prefer (e.g., a team-specific reviewer you always run separately).

## Logging

Every routing decision — auto, prompted, skipped — appends to
`{planning_dir}/findings/skills-considered.md` so the transcript
records what fired and why. The file is plain markdown and is safe to
delete; it regenerates on the next `/deep` run.

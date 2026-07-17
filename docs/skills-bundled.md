# Bundled and Installed Skills

The plugin follows one naming convention: skills the plugin **owns** are
bundled in `skills/` and surface under the `deep:` namespace; skills the
plugin **depends on** are installed unmodified from their upstream source
(no vendored copies, no renamed forks). Full attribution history lives in
[`NOTICE`](../NOTICE).

## Bundled (plugin-owned, `deep:*`)

| Skill | Purpose |
|---|---|
| `deep` | The plugin's own discovery/plan/implement pipeline. |
| `code-review` | Standalone entry point to the `code-reviewer` agent with context gathering and web-verified findings. |
| `humanizer` | Removes signs of AI-generated writing from prose (user's own skill, v2.5.1; global copy archived — plugin is the single source). |

## Installed from mattpocock/skills

Run once (re-run to update to current upstream):

```bash
uv run scripts/checks/install-mattpocock-skills.py
```

Downloads these skills verbatim from
[mattpocock/skills](https://github.com/mattpocock/skills) into
`~/.claude/skills/`, recording provenance + hashes in
`~/.claude/skills/skills-lock.json`:

| Skill | Wired into `/deep` via |
|---|---|
| `grilling` | `Skill(grilling)` in interview protocols; inline fallback walk in `references/interview-protocol.md` |
| `grill-me` | standalone grill entry point, no direct `/deep` wiring |
| `handoff` | standalone session-handoff skill, no direct `/deep` wiring |

## Global skills `/deep` invokes opportunistically

Resolved from the user's `~/.claude/skills/` if present:

| Skill | Wired into `/deep` via |
|---|---|
| `tdd` | rules inlined in `references/coding-standards.md`, `agents/section-writer.md`, `agents/opus-plan-reviewer.md` |
| `domain-modeling` | always-on audit topic in `references/audit-topic-enumeration.md` |
| `codebase-design` | `Skill(codebase-design)` in `references/integration-protocol.md`; vocabulary inlined at `references/architecture-language.md` |
| `obsidian-vault` | `Skill(obsidian-vault)` from the `vault-curator` subagent |
| `write-a-skill` | standalone meta-skill, no `/deep` wiring |

**Dependency note:** the `/deep` flows degrade gracefully when a skill is
missing — interview protocols carry an inline fallback walk, and the
tdd/architecture rules are inlined in `references/`. Only the
opportunistic `Skill(...)` invocations no-op without the installed skills.

## Cross-references in protocol files

Load-bearing content from formerly vendored skills was inlined so the
plugin stays self-contained:

* `references/architecture-language.md` — the module/depth/seam/deletion-test
  vocabulary (formerly `improve-codebase-architecture/LANGUAGE.md`).
* `references/coding-standards.md` — tracer-bullet TDD rules (formerly
  `tdd/SKILL.md`).
* `references/plan-writing.md` — deep-modules-first planning rules
  (formerly `tdd/deep-modules.md`).
* `references/interview-protocol.md` — the inline grill walk (mirrors the
  upstream grill approach).

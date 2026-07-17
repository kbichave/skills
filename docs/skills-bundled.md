# Bundled Skills

The plugin previously vendored seven skills from
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT). Six were
**removed** in favor of their globally installed equivalents — vendoring
them alongside the global copies produced duplicate skill entries. Full
attribution history lives in [`NOTICE`](../NOTICE).

| Formerly vendored | Now resolved by (global skill) | Wired into `/deep` via |
|---|---|---|
| `grill-me` | `grilling` | `Skill(grilling)` in interview protocols; inline fallback walk in `references/interview-protocol.md` |
| `tdd` | `tdd` | rules inlined in `references/coding-standards.md`, `agents/section-writer.md`, `agents/opus-plan-reviewer.md` |
| `ubiquitous-language` | `domain-modeling` | always-on audit topic in `references/audit-topic-enumeration.md` |
| `improve-codebase-architecture` | `codebase-design` | `Skill(codebase-design)` in `references/integration-protocol.md`; vocabulary inlined at `references/architecture-language.md` |
| `obsidian-vault` | `obsidian-vault` | `Skill(obsidian-vault)` from the `vault-curator` subagent |
| `write-a-skill` | `write-a-skill` | standalone meta-skill, no `/deep` wiring |

**Dependency note:** the `/deep` flows degrade gracefully when a global
skill is missing — interview protocols carry an inline fallback walk, and
the tdd/architecture rules are inlined in `references/`. Only the
opportunistic `Skill(...)` invocations no-op without the global skills.

## Still bundled

| Skill | Purpose |
|---|---|
| `deep` | The plugin's own discovery/plan/implement pipeline. |
| `mp-zoom-out` | Strategic step-back prompt (Matt Pocock upstream `zoom-out`, renamed with the `mp-` prefix to mark provenance and avoid clashing with any global copy). |
| `code-review` | Standalone entry point to the `code-reviewer` agent with context gathering and web-verified findings. |

## Cross-references in protocol files

Load-bearing content from the removed skills was inlined so the plugin
stays self-contained:

* `references/architecture-language.md` — the module/depth/seam/deletion-test
  vocabulary (formerly `improve-codebase-architecture/LANGUAGE.md`).
* `references/coding-standards.md` — tracer-bullet TDD rules (formerly
  `tdd/SKILL.md`).
* `references/plan-writing.md` — deep-modules-first planning rules
  (formerly `tdd/deep-modules.md`).
* `references/interview-protocol.md` — the inline grill walk (mirrors the
  upstream grill approach).

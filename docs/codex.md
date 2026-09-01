# Running `deep` on Codex as well as Claude Code

Codex and Claude Code turn out to be close cousins. Both use `SKILL.md` with
`name` + `description` frontmatter, both have a plugin manifest and a
marketplace manifest, both support `PreToolUse` hooks, and both accept the
*same* deny payload. Most of this plugin is portable without change.

What follows is verified against a real Codex install on this machine
(`~/.codex/`, `~/.agents/skills/`, the bundled marketplace under
`~/.codex/.tmp/bundled-marketplaces/`), not inferred from documentation.

## What actually differs

| | Claude Code | Codex |
|---|---|---|
| Plugin manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| Marketplace manifest | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` |
| Marketplace `source` | bare string `"./"` | nested object `{"source": "local", "path": "./"}` |
| Skill search path | plugin `skills/` | `.agents/skills/`, `~/.agents/skills/`, plugin `skills/` |
| Hooks file | `hooks/hooks.json` | `~/.codex/hooks.json` or `<repo>/.codex/hooks.json` |
| Subagent format | Markdown with frontmatter | **TOML** in `~/.codex/agents/` |
| Config | `settings.json` | `config.toml` |

The Codex manifests are **generated** from the Claude ones:

```bash
uv run scripts/checks/sync-codex-manifests.py          # write
uv run scripts/checks/sync-codex-manifests.py --check  # CI drift guard
```

Do not hand-edit them. Two manifests maintained in parallel is exactly how
`marketplace.json` sat at 5.4.1 for ten releases while everything else moved on.

## What ports cleanly

**The Python.** `scripts/lib/` and `scripts/checks/` are stdlib-only,
subprocess-invoked, and emit JSON. Nothing about them is host-specific.

**The references.** `references/*.md` are prose protocols a model reads. Format
neutral.

**The quality packs.** `references/quality/` and `lint/*/adapter.json` are data.

**The skills.** One `skills/` tree serves both hosts. Codex's plugin manifest
points at the same directory.

**The guardrails.** Codex supports `PreToolUse` and honours the identical
envelope:

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "..."}}
```

So `guard-pre-tool-use.py` and the fix-lock work unchanged. Only the location of
the hook registration differs.

## What is degraded, honestly

**The review panel.** This is the real gap. Codex has subagents, and they run
concurrently, but:

- they are TOML, not Markdown, so `agents/*.md` needs converting
- there is **no documented per-agent tool allow/deny list** — only a sandbox
  override. Our panel relies on scoped `tools:` frontmatter
- there is **no documented structured-output contract**; results are described
  as summaries. The panel's JSON finding schema, and the verifier that consumes
  it, assume machine-parseable returns

Prototype one expert before converting all nine. If structured output does not
hold, the panel degrades to sequential inline review, which loses the separate
context window that is most of its value.

**Path references.** Our skills call scripts as
`${DEEP_PLUGIN_ROOT}/scripts/checks/x.py`. Codex's own skills use
**skill-relative** paths (`python3 scripts/render.py`) and no plugin-root
variable is documented. Until that is resolved, a Codex install needs either a
wrapper that exports `DEEP_PLUGIN_ROOT`, or the scripts reachable on `PATH`.

**Beads.** Unchanged — `bd` is a CLI, not a host feature.

## What is absent

Nothing load-bearing, so far as this investigation found. The gaps are the two
above, and both are engineering rather than impossibility.

## Recommended install (manual, until this is packaged)

```bash
# 1. Clone once
git clone https://github.com/kbichave/skills.git ~/src/deep

# 2. Make the skills visible to Codex
ln -s ~/src/deep/skills/deep         ~/.agents/skills/deep
ln -s ~/src/deep/skills/code-review  ~/.agents/skills/deep-code-review

# 3. Make the guardrails active (merge, do not overwrite an existing file)
cp ~/src/deep/hooks/hooks.json ~/.codex/hooks.json

# 4. Point the scripts at the checkout
echo 'export DEEP_PLUGIN_ROOT=~/src/deep' >> ~/.zshrc
```

Symlinks rather than copies, so `git pull` updates both hosts at once.

## Status

Manifests and the drift guard ship. The subagent conversion and the plugin-root
question are open and tracked in beads. Treat Codex support as **usable for the
skills and guardrails, not yet for the review panel.**

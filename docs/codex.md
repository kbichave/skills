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

## Install

```bash
brew install --cask codex      # or: npm i -g @openai/codex
```

### Marketplace registration may be blocked

`codex plugin marketplace add <path>` is the tidy route, but on a managed Mac it
can fail:

```
Error: marketplace source ... is not allowed by requirements from
enterprise-managed requirements Admin Groups Policy Mac
```

MDM policy restricts which marketplaces Codex will accept, and it also pins
`approval_policy` and `windows.sandbox` regardless of local config. Nothing to
work around — use the skills path instead, which needs no marketplace.

### Symlink route (works under MDM)

```bash
R=~/Personal/deep-plan-enhanced          # your checkout

ln -sfn $R/skills/deep           ~/.agents/skills/deep
ln -sfn $R/skills/code-review    ~/.agents/skills/deep-code-review
ln -sfn $R/skills/humanizer      ~/.agents/skills/deep-humanizer
ln -sfn $R/skills/no-op-remover  ~/.agents/skills/deep-no-op-remover

# Codex has no plugin-root variable of its own; the skills need this.
echo 'export DEEP_PLUGIN_ROOT="'$R'"' >> ~/.zshrc

# Guardrails — merge into an existing file, do not clobber it.
cp $R/hooks/hooks.json ~/.codex/hooks.json
```

Symlinks rather than copies, so `git pull` updates both hosts at once.

Verify:

```bash
codex exec --sandbox read-only "List every available skill whose name starts with 'deep'."
# → deep:code-review, deep:deep, deep:humanizer, deep:no-op-remover
```

## Status

Manifests and the drift guard ship. The subagent conversion and the plugin-root
question are open and tracked in beads. Treat Codex support as **usable for the
skills and guardrails, not yet for the review panel.**

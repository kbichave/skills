# Integration Protocol

`/deep` integrates with three cross-cutting systems: the Obsidian
knowledge vault, the architecture-audit prompt, and skill-aware
routing. The detailed steps live here so `skills/deep/SKILL.md` can
stay terse.

## 1. Vault initialisation (runs in step 1a of the SKILL)

Resolution is delegated to `scripts/lib/vault.py`:

```bash
uv run python -c "
import json
from scripts.lib.vault import resolve_vault_path, should_prompt_for_creation
status = resolve_vault_path()
print(json.dumps({
  'path': str(status.path) if status.path else '',
  'exists': status.exists,
  'source': status.source,
  'should_prompt': should_prompt_for_creation(status),
}))
"
```

Behaviour matrix:

| `source` | `exists` | Action |
|---|---|---|
| `env` | `true` | Use the path; set `vault_available = true`. |
| `env` | `false` | Warn that `DEEP_OBSIDIAN_VAULT` points to a missing dir; fall back to default and re-resolve. |
| `default` | `true` | Use `~/Obsidian/deep-plan/`; set `vault_available = true`. |
| `none` | `false` | **Ask once** via `AskUserQuestion`: *Create a new Obsidian vault at `~/Obsidian/deep-plan/`? (yes / specify path / no)*. On yes, run `ensure_vault_skeleton`; on path, run `ensure_vault_skeleton(path)`; on no, set `vault_available = false`. |

Persist the user's "no" choice for the session. If the user names a
custom path, store it in the session state — do NOT mutate the user's
shell environment. When `vault_available = true`, every step that emits
glossary terms, ADRs, or curated findings invokes the `vault-curator`
subagent at the end of the mode. When `false`, those artifacts land in
`~/.claude/projects/<slug>/memory/` instead. See `docs/vault.md`.

## 2. Skill-aware routing (runs between phases in every mode)

Invoke the `skill-router` subagent with this context block:

```json
{
  "mode": "<discovery | plan | implement | auto>",
  "current_step": "<step name from the tracker>",
  "files": ["<paths touched in this step>"],
  "imports": ["<module names imported>"],
  "output_kind": "<code | prose | commit | pr_comment>",
  "auto_mode": <true if mode == auto>,
  "mute_list": [<from ~/.claude/deep/muted-skills.json if present>],
  "plugin_root": "${plugin_root}"
}
```

The router returns three lists: `auto_invoked`, `prompted`, `skipped`.

* For each entry in `auto_invoked`, invoke the named skill via the
  `Skill` tool now. Append the decision to
  `{planning_dir}/findings/skills-considered.md`.
* For `prompted` entries, surface a single multi-select
  `AskUserQuestion` listing all candidates. Skip in auto mode.
* For `skipped` entries, log only.

Side-effect skills (`pr-reply`, `schedule`, `loop`, `internal-comms`,
`pptx*`, `browser-automation`) never auto-invoke even when keyword
match is HIGH. The hard list lives in
`scripts/lib/skills_registry.py::SIDE_EFFECT_SKILLS`. If
`--no-skill-routing` is set in the session state, skip routing
entirely. See `docs/skill-routing.md`.

## 3. Architecture-audit prompt (plan + implement)

Adopted from `skills/improve-codebase-architecture`. Always offered,
never flag-gated.

**During `/deep plan`** (between research and interview):

1. Run the audit:

   ```bash
   uv run python -c "
   from pathlib import Path
   from scripts.lib.architecture_audit import run_audit, render_audit_markdown
   result = run_audit(Path('.'))
   print(render_audit_markdown(result))
   " > "${planning_dir}/findings/architecture-audit.md"
   ```

2. If `result.total > 0`, surface a single `AskUserQuestion`:

   > **Audit found N deepening opportunities touching the area you're
   > planning. Fold an architecture improvement into this plan?**
   > Options: `Yes — pick one` / `Show candidates first` / `No — keep
   > plan focused`.

3. On `yes`, invoke `Skill(improve-codebase-architecture)` with the
   audit candidates. Merge its output into the plan as a dedicated
   `## Architecture improvement` section and emit an ADR file under
   `findings/adrs/<slug>-<date>.md`.
4. On `no`, persist the audit file for future runs; it informs
   `agents/section-writer.md` overlap checks during implement.

**During `/deep implement`** (per section start):

1. Read `findings/architecture-audit.md` if it exists.
2. If any file in the section's implementation block overlaps a
   candidate, surface a single `AskUserQuestion`:

   > **This section touches a known shallow module / hypothetical seam.
   > Deepen it as part of the section, or keep scope narrow?**
   > Default: **narrow**.

3. Default behaviour is narrow. Offering only — never auto-expand
   scope.

In `/deep auto` mode the prompts above are skipped; the audit results
are still written for later reference.

## 4. End-of-Mode wrap-up: vault-curator

After a mode reaches its terminal step (`output-summary` for
discovery / plan / auto, `final-verification` for implement),
invoke the `vault-curator` subagent. Pass:

```json
{
  "vault_path": "<resolved vault path or empty string>",
  "project_path": "<repo root>",
  "mode": "<discovery | plan | implement | auto>",
  "artifacts": [
    {"path": "<absolute path>", "kind": "glossary | adr | finding | plan | transcript | impl_summary", "summary": "<one-line>"}
  ],
  "cross_project_hits": [<list of (term, project_a, project_b) tuples>]
}
```

The curator returns a JSON block of routing decisions. Honour the
decisions: write artifacts marked `vault:...` via the `obsidian-vault`
skill (or the `Write` tool with vault paths), leave artifacts marked
`local` untouched. Append the curator's JSON to
`{planning_dir}/.deepstate/vault-decisions.json` for audit.

If `vault_path` is empty, the curator routes everything to `local` and
no `Skill` calls are made — graceful degrade.

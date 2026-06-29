# Quality Pack Template

Copy this directory to create a new pack under `references/quality/<pack>/`.
A pack is a group of rule families that get routed together (decision Q5). The
`index.md` frontmatter is read by `scripts/lib/pack_router.py` to decide whether
the pack is active for a given target repo + task.

## `index.md` frontmatter

```yaml
---
pack: <name>                 # unique; matches the directory name
applies_when:
  always: false              # true only for `core`
  languages: [python, typescript, go]
  project_types: [backend, api, frontend, library, cli, data, infra]
  changed_globs: ["**/api/**"]      # target-repo paths
  task_types: [add-endpoint, change-api]
provides_rules: [API, DATA]  # family prefixes authored as sibling sub-files
---
```

Matching is OR across the `applies_when` keys (any key matching activates the
pack); `core` uses `always: true`. Empty/unknown signals → `core` only.

## Family sub-files

One file per family prefix listed in `provides_rules`, named lowercase
(`api.md`, `data.md`). Each rule uses this shape:

```
### <PREFIX>-NNN: <one-line standard>
- **Trigger:** when this rule applies.
- **Required behavior:** what must be true.
- **Verification signal:** how a test / linter / reviewer confirms it.
- **Severity:** BLOCK | WARN | ADVISE
- **Enforcer:** linter | reviewer | router | human
```

## Per-language thresholds

Numeric thresholds live in the lint adapters (`lint/<lang>/`), not here — a rule
states the standard ("bound function complexity"); the adapter sets the number
per language (decision: Go differs from Python/TS).

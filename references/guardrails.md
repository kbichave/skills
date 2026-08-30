# Guardrails — deterministic PreToolUse blocking

The quality gate catches problems *after* code is on disk. Guardrails stop a
narrow class of them *before* the write lands: credentials, and files a repo has
declared off-limits.

This is deliberately small. Anything a linter can catch belongs in the Phase 6
gate, not here — a hook that runs on every edit has to be fast and quiet.

## What it does

| Trigger | Action | Why |
|---|---|---|
| Credential pattern in written content | `deny` | There is no legitimate override for a leaked key |
| Path matching a repo's `protected_paths` | `ask` (default) | Sometimes legitimate, so the engineer clears it with a keystroke |
| Everything else | silent allow | The common case must cost nothing |

`deny` is reserved for credentials. Protected paths default to `ask` so a
generated-code edit is a one-key confirmation rather than a JSON edit mid-flow.
A repo can opt a path into `deny` with `"action": "deny"`.

Secrets outrank protected paths. If a file is both, the answer is `deny`.

## Configuration

Layers merge lowest-to-highest, and lists concatenate:

1. `${CLAUDE_PLUGIN_ROOT}/guard-defaults.json` — plugin baseline
2. `<planning_dir>/deep-guard.json` — session-scoped override
3. `<cwd>/.claude/deep-guard.json` — **the normal case**, version-controlled
   with the target repo like `CLAUDE.md`
4. `$DEEP_GUARD_CONFIG` — absolute path, escape hatch for tests and CI

A layer setting `"inherit": false` resets accumulated lists at that point.

The baseline ships `protected_paths` and `format_on_edit` **empty**, and every
secret pattern is a vendor-prefixed high-entropy token or a structural marker.
There is deliberately no generic `password\s*=` rule: that class of regex is the
largest source of false-positive frustration, and `bandit`/`semgrep` already
cover it at Phase 6. So out of the box the guard blocks credentials and nothing
else. Protected paths are opt-in per repo, by design.

### Example repo config

```json
{
  "protected_paths": [
    {"glob": "src/generated/**", "reason": "generated from schema.proto — edit the proto"},
    {"glob": "migrations/**", "reason": "applied migrations are immutable", "action": "deny"}
  ],
  "allow_secret_paths": ["**/tests/fixtures/**"]
}
```

### Glob semantics

`fnmatch`, plus the two conveniences people expect from gitignore-style patterns:

- a leading `**/` matches at any depth **including none**, so `**/*.md` catches
  a top-level `README.md`
- a trailing `/**` matches the whole subtree, so `src/generated/**` catches
  `src/generated/a/b/c.py`

## Turning it off

`DEEP_GUARD=off` disables the guard for the session. `"enabled": false` in any
config layer does the same persistently. Both are named in every block message,
along with the config path and the rule id, because a block that does not say
how to unblock is a bad block.

## Failure behaviour

The guard **fails open**. A malformed config layer is skipped; a bad regex
disables only that rule; an unparseable payload, a missing file or any
unexpected exception exits 0 silently. The guard must never be the reason an
edit fails — that is the failure mode that gets a safety feature deleted.

## Latency

The hook runs on every `Write`/`Edit`/`MultiEdit`/`NotebookEdit`. Measured with
the 8 shipped patterns: 1 KB costs 0.1 ms, 50 KB costs 1.8 ms, and the 256 KB
scan cap costs 9.4 ms. Interpreter start (~25-35 ms) dominates in every case,
and the plugin already pays that on every tool call for
`deep-context-monitor.py`.

This is why the hook runs under `python3` rather than `uv run`, which would add
150-300 ms of resolver overhead. Config is memoised on `(path, mtime)` and
regexes are compiled once. `hooks.json` sets `"timeout": 5` so a pathological
pattern cannot wedge the session.

## The test-file lock

A second decision rides on the same `PreToolUse` hook, so a per-edit hook stays
one interpreter start. It is consulted only when the guard itself had nothing
to say.

**Why it exists.** "All tests pass" is only evidence if the agent could not have
edited the test. Without a lock, the fastest route to a green run is to change
the assertion, and the loop closes on itself.

**How it works.** Open the lock when a section's tests exist and before its
implementation does — Phase 3 step 1 — naming exactly those files:

```bash
python3 ${DEEP_PLUGIN_ROOT}/scripts/checks/fix-lock.py "${planning_dir}" \
  open --section section-04 --protected tests/test_retry.py
```

Edits to a named file are then **denied** (not `ask` — the point is that the
agent cannot clear it). Phase 9 widens the lock on strike ≥ 1 via `add`, since
repeated failure is when the temptation to edit the test is strongest. Close it
when the section lands.

**It blocks only files it names.** Not "anything test-shaped": the lock protects
the specific tests pinning the current bug, and over-blocking is how a safety
feature gets switched off.

**Releasing it.** `fix-lock.py <dir> override --reason "..."` requires a reason
and records it in the lock file, so an override is visible afterwards rather
than silent. `DEEP_FIX_LOCK=off` disables it for the session. Both are named in
the block message.

State lives at `<planning_dir>/.deepstate/fix-lock.json`. A missing or malformed
lock is no lock.

## Not covered

`Write|Edit` does not see `sed -i`, `tee`, or shell redirection. A `Bash`
matcher for those is materially more false-positive-prone (`grep "terraform
apply" notes.md` matches a naive rule), so it ships behind `"guard_bash": false`
and should only be enabled after the write layer has been quiet for a release.

Formatters (`format_on_edit`) are also off by default. A PostToolUse formatter
rewrites the file Claude just wrote, so a following `Edit` built on the
pre-format content fails on `old_string` mismatch. Enabling them requires
telling Claude the file changed underneath it.

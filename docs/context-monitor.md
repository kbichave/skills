# Context Monitor

A two-layer context-usage tracker for `/deep` sessions, modeled on GSD's pattern.

## What it does

1. **Statusline** — single-line bar in your Claude Code status area showing model, mode, active `/deep` step, and percent of input context consumed.
2. **In-conversation warnings** — a `PostToolUse` hook injects an `additionalContext` block into the agent's view when context crosses thresholds, so the agent can checkpoint and `/clear` before truncation hits.

## Install

Run once per machine:

```bash
uv run /path/to/deep-plan-enhanced/scripts/checks/install-statusline.py
```

This writes a `statusLine` entry into `~/.claude/settings.json`. If you already had a custom statusline, it is backed up to `~/.claude/settings.json.deep-backup-<timestamp>` before being replaced.

The `PostToolUse` hook side is registered automatically by the plugin's `hooks/hooks.json` — no separate install step.

### Status check

```bash
uv run .../scripts/checks/install-statusline.py --check
```

Exit `0` if installed, `1` otherwise.

### Uninstall

```bash
uv run .../scripts/checks/install-statusline.py --uninstall
```

Restores the latest backup if one exists; otherwise removes the `statusLine` entry entirely.

## Statusline format

Active `/deep` session:

```
deep:plan detailed-interview ▰▰▰▰▰▰▱▱▱▱ 62% [opus-4-7]
```

No active session (still useful):

```
ctx ▰▰▰▱▱▱▱▱▱▱ 32% [opus-4-7]
```

Before the first API call or right after `/compact` (current usage not yet reported):

```
ctx ▱▱▱▱▱▱▱▱▱▱ --% [opus-4-7]
```

The bar is 10 cells; each cell ≈ 10% of the configured context window.

## Thresholds

| Level | `used_percentage` | Behavior |
|---|---|---|
| `normal` | `< 65` | Statusline updates; no warning injected. |
| `warning` | `65–74` | Inject "WARNING: close active step, save findings, avoid opening new sections/subagents." |
| `critical` | `≥ 75` | Inject "CRITICAL: run `tracker-cli.py prime`, save to `impl-progress.md`, then `/clear`." |

`used_percentage` is input-only — output tokens are excluded (matches Claude Code's own field). Thresholds are read against the value Claude Code computes; if absent, the hook recomputes from `current_usage.{input_tokens, cache_creation_input_tokens, cache_read_input_tokens}` divided by the resolved context window size.

### Debounce

Same-level warnings are debounced by 5 tool calls. Escalation (`warning → critical`) bypasses the debounce so an urgent state is never suppressed.

## Context window sizes

The hook trusts the `context_window.context_window_size` field on the statusline stdin. If absent or zero, it falls back to a hardcoded table:

| Model | Fallback |
|---|---|
| `claude-opus-4-7` | 1,000,000 |
| `claude-sonnet-4-6` | 1,000,000 |
| `claude-haiku-4-5-20251001` | 200,000 |
| anything else | 200,000 (default) |

### Override the table

Drop a JSON file at `~/.claude/deep-context-limits.json`:

```json
{
  "claude-some-new-model": 2000000,
  "claude-haiku-4-5-20251001": 200000
}
```

Reloaded on every statusline tick; no restart required.

## Bridge file

Per-session JSON at `/tmp/deep-ctx-<session_id>.json`. Written by the statusline (~event-driven, 300ms debounced), read by the PostToolUse hook. Includes debounce state inline (`last_emitted_level`, `tool_calls_since_emit`).

If the file is older than 30 seconds when the monitor reads it, it's treated as stale and the monitor stays silent — usually means the statusline is not registered yet.

## Limitations

- **Subagent context not visible.** Tokens consumed inside `Agent(...)` runs are not reflected in the parent transcript's usage and so are not counted. Same limitation as GSD.
- **No auto-`/clear`.** The hook warns; you (or the agent) decide when to clear.
- **Plugin cannot register the statusline itself.** Plugin `hooks/hooks.json` and `settings.json` do not accept `statusLine`. The installer writes to the user `~/.claude/settings.json` instead.
- **`current_usage` is null pre-first-call and right after `/compact`.** The statusline renders `--%` and skips writing the bridge for that tick.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Statusline blank | Not installed | Run the install script |
| Statusline stuck on `--%` | First API call has not happened yet, or you just `/compact`ed | Send a message; it should resolve |
| No warnings ever fired | Bridge file stale | Verify `~/.claude/settings.json` has the `deepInstalledBy: deep-plan-enhanced` entry; check the file at `/tmp/deep-ctx-<session_id>.json` exists and `ts` is recent |
| Warnings repeat too often | Debounce expects 5 tool calls between same-level emits | Working as intended; escalation to `critical` bypasses |
| Custom statusline lost after install | Replaced (with backup) | `--uninstall` restores from the most recent `*.deep-backup-<ts>` file |

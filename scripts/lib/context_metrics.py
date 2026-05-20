"""Context-usage metrics for the deep statusline + monitor hooks.

Two consumers:
- ``deep-statusline.py`` builds the bridge file with current state.
- ``deep-context-monitor.py`` reads the bridge file and decides whether to
  emit a warning via ``additionalContext``.

Bridge file format (``/tmp/deep-ctx-{session_id}.json``):

    {
      "session_id": "...",
      "model_id": "claude-opus-4-7",
      "model_display": "Opus 4.7",
      "context_window_size": 1000000,
      "used_input_tokens": 327000,
      "used_percentage": 32.7,
      "level": "normal" | "warning" | "critical",
      "current_step_id": "detailed-interview" | null,
      "current_step_title": "Detailed Interview" | null,
      "planning_dir": "/abs/path" | null,
      "mode": "plan" | "implement" | "audit" | "auto" | null,
      "last_emitted_level": "warning" | "critical" | null,
      "tool_calls_since_emit": 0,
      "ts": 1709000000.0
    }

Thresholds are on ``used_percentage`` (rising), not remaining.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

# Fallback table for context_window_size when stdin lacks it.
# Source of truth is the stdin field ``context_window.context_window_size``.
# May 2026 values.
MODEL_CONTEXT_SIZE_FALLBACK: dict[str, int] = {
    "claude-opus-4-7": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5-20251001": 200_000,
}
DEFAULT_CONTEXT_SIZE = 200_000

# Threshold boundaries (inclusive lower bound).
WARNING_THRESHOLD = 65.0
CRITICAL_THRESHOLD = 75.0

# Debounce: same-level re-emit requires this many tool calls between emits.
DEBOUNCE_TOOL_CALLS = 5

# User-level overrides for the model context-size table.
USER_OVERRIDES_PATH = Path.home() / ".claude" / "deep-context-limits.json"


@dataclass
class BridgeState:
    """Snapshot written by the statusline hook, consumed by the monitor."""

    session_id: str
    model_id: str
    model_display: str
    context_window_size: int
    used_input_tokens: int
    used_percentage: float
    level: str  # normal | warning | critical
    current_step_id: str | None
    current_step_title: str | None
    planning_dir: str | None
    mode: str | None
    last_emitted_level: str | None
    tool_calls_since_emit: int
    ts: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_user_overrides(path: Path = USER_OVERRIDES_PATH) -> dict[str, int]:
    """Load user-level overrides for the model-size table. Returns {} if absent."""
    try:
        with path.open() as f:
            data = json.load(f)
        return {k: int(v) for k, v in data.items() if isinstance(v, (int, float))}
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
        return {}


def resolve_context_size(
    model_id: str | None,
    stdin_size: int | None,
    overrides: dict[str, int] | None = None,
) -> int:
    """Pick the context window size with this priority: stdin > overrides > fallback table > default."""
    if isinstance(stdin_size, int) and stdin_size > 0:
        return stdin_size
    if overrides is None:
        overrides = load_user_overrides()
    if model_id and model_id in overrides:
        return overrides[model_id]
    if model_id and model_id in MODEL_CONTEXT_SIZE_FALLBACK:
        return MODEL_CONTEXT_SIZE_FALLBACK[model_id]
    return DEFAULT_CONTEXT_SIZE


def compute_used_input_tokens(current_usage: dict[str, Any] | None) -> int:
    """Sum input + cache_creation + cache_read tokens. Excludes output (matches Claude Code's used_percentage)."""
    if not current_usage:
        return 0
    return int(
        (current_usage.get("input_tokens") or 0)
        + (current_usage.get("cache_creation_input_tokens") or 0)
        + (current_usage.get("cache_read_input_tokens") or 0)
    )


def compute_used_percentage(used_tokens: int, context_size: int) -> float:
    """Percentage of input context consumed. Clamped to [0, 100]."""
    if context_size <= 0:
        return 0.0
    pct = (used_tokens / context_size) * 100.0
    if pct < 0:
        return 0.0
    if pct > 100:
        return 100.0
    return round(pct, 2)


def classify_level(used_percentage: float) -> str:
    """Return ``normal`` / ``warning`` / ``critical`` from used %."""
    if used_percentage >= CRITICAL_THRESHOLD:
        return "critical"
    if used_percentage >= WARNING_THRESHOLD:
        return "warning"
    return "normal"


def should_emit(
    new_level: str, last_emitted_level: str | None, tool_calls_since_emit: int
) -> bool:
    """Debounce logic.

    Rules:
    - normal: never emit.
    - new_level differs from last_emitted_level (escalation OR decay): emit.
    - same level as last_emitted_level: emit only if tool_calls_since_emit >= DEBOUNCE_TOOL_CALLS.
    """
    if new_level == "normal":
        return False
    if last_emitted_level != new_level:
        return True
    return tool_calls_since_emit >= DEBOUNCE_TOOL_CALLS


def bridge_path(session_id: str, tmp_dir: Path | None = None) -> Path:
    """Path to the per-session bridge file."""
    base = tmp_dir if tmp_dir is not None else Path(tempfile.gettempdir())
    return base / f"deep-ctx-{session_id}.json"


def write_bridge(state: BridgeState, path: Path | None = None) -> Path:
    """Atomically write the bridge state JSON. Returns the path written."""
    target = path if path is not None else bridge_path(state.session_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state.to_dict(), f)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def read_bridge(path: Path) -> BridgeState | None:
    """Load a bridge file. Returns None on any read/parse failure."""
    try:
        with path.open() as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    try:
        return BridgeState(
            session_id=data["session_id"],
            model_id=data.get("model_id", ""),
            model_display=data.get("model_display", ""),
            context_window_size=int(data.get("context_window_size", DEFAULT_CONTEXT_SIZE)),
            used_input_tokens=int(data.get("used_input_tokens", 0)),
            used_percentage=float(data.get("used_percentage", 0.0)),
            level=data.get("level", "normal"),
            current_step_id=data.get("current_step_id"),
            current_step_title=data.get("current_step_title"),
            planning_dir=data.get("planning_dir"),
            mode=data.get("mode"),
            last_emitted_level=data.get("last_emitted_level"),
            tool_calls_since_emit=int(data.get("tool_calls_since_emit", 0)),
            ts=float(data.get("ts", 0.0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def is_stale(state: BridgeState, max_age_seconds: float = 30.0) -> bool:
    """Bridge is stale if older than max_age_seconds. The statusline writes
    on every refresh so a stale bridge means statusline is not running."""
    return (time.time() - state.ts) > max_age_seconds


def format_warning(state: BridgeState) -> str:
    """Build the warning string for additionalContext. Capped to ~1500 chars."""
    step_label = ""
    if state.current_step_id:
        title = state.current_step_title or state.current_step_id
        step_label = f"\nActive step: `{state.current_step_id}` — {title}"
    mode_label = f" ({state.mode} mode)" if state.mode else ""

    if state.level == "critical":
        body = (
            f"[deep-context] CRITICAL: context at {state.used_percentage:.1f}% "
            f"used ({state.used_input_tokens:,} / {state.context_window_size:,} input tokens){mode_label}."
            f"{step_label}\n"
            "Action required:\n"
            "  1. Summarize current state into `impl-progress.md` (or `findings/`) NOW.\n"
            "  2. Run `tracker-cli.py prime` to checkpoint the active step.\n"
            "  3. Then `/clear` and resume — see `references/resume.md`.\n"
            "Do NOT start a new section or open a new subagent at this level."
        )
    elif state.level == "warning":
        body = (
            f"[deep-context] WARNING: context at {state.used_percentage:.1f}% "
            f"used ({state.used_input_tokens:,} / {state.context_window_size:,} input tokens){mode_label}."
            f"{step_label}\n"
            "Action: close the active step via `tracker-cli.py close`, save findings, "
            "and avoid opening new sections/subagents until usage drops or you `/clear`."
        )
    else:
        body = ""

    if len(body) > 1500:
        body = body[:1497] + "..."
    return body


def build_envelope(message: str) -> dict[str, Any]:
    """Wrap a warning string in the PostToolUse hookSpecificOutput envelope."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }

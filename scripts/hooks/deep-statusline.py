#!/usr/bin/env python3
"""statusLine hook for deep-plan-enhanced.

Reads the JSON payload Claude Code passes on stdin, renders a single status
line, and writes a per-session bridge file consumed by ``deep-context-monitor.py``.

Registration (in user ``~/.claude/settings.json`` — plugins cannot ship a
``statusLine`` entry):

    {
      "statusLine": {
        "type": "command",
        "command": "uv run /abs/path/to/scripts/hooks/deep-statusline.py",
        "padding": 2,
        "refreshInterval": 5
      }
    }

Status line format (active deep session):

    deep:plan P02·detailed-interview ▰▰▰▰▰▰▱▱▱▱ 62% [opus-4-7]

Fallback (no active deep session):

    ctx ▰▰▰▱▱▱▱▱▱▱ 32% [opus-4-7]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from lib.context_metrics import (  # noqa: E402
    BridgeState,
    bridge_path,
    classify_level,
    compute_used_input_tokens,
    compute_used_percentage,
    read_bridge,
    resolve_context_size,
    write_bridge,
)

ACTIVE_POINTER = Path.home() / ".claude" / ".deep-plan-active"
BAR_WIDTH = 10
TRACKER_TIMEOUT_S = 2.0


def render_bar(used_pct: float, width: int = BAR_WIDTH) -> str:
    """ASCII bar. 10 cells by default."""
    if used_pct <= 0:
        filled = 0
    elif used_pct >= 100:
        filled = width
    else:
        filled = max(0, min(width, int(round((used_pct / 100.0) * width))))
    return "▰" * filled + "▱" * (width - filled)


def resolve_planning_dir() -> Path | None:
    """Read ``~/.claude/.deep-plan-active`` to find the active planning dir."""
    if not ACTIVE_POINTER.exists():
        return None
    try:
        text = ACTIVE_POINTER.read_text().strip()
    except OSError:
        return None
    if not text:
        return None
    candidate = Path(text)
    return candidate if candidate.exists() else None


def detect_mode(planning_dir: Path) -> str | None:
    """Cheap mode detection from artifacts in the planning dir."""
    if (planning_dir / "impl-progress.md").exists() or (
        planning_dir / "impl-summary.md"
    ).exists():
        return "implement"
    if (planning_dir / "phasing-overview.md").exists():
        return "auto"
    if (planning_dir / "claude-plan.md").exists():
        return "plan"
    if (planning_dir / "objective.md").exists() or (
        planning_dir / "findings"
    ).exists():
        return "audit"
    return None


def query_tracker(planning_dir: Path) -> tuple[str | None, str | None]:
    """Shell out to tracker-cli.py ready. Returns (id, title) of first ready step."""
    state_dir = planning_dir / ".deepstate"
    if not state_dir.exists():
        return None, None
    plugin_root = os.environ.get("DEEP_PLUGIN_ROOT")
    if not plugin_root:
        # Try plugin cache root inferred from this script (if statusline runs
        # from the cached plugin) — but typically statusline runs out of user
        # settings.json with an absolute path, so DEEP_PLUGIN_ROOT may be unset.
        plugin_root = str(SCRIPT_DIR.parent.parent)
    cli = Path(plugin_root) / "scripts" / "checks" / "tracker-cli.py"
    if not cli.exists():
        return None, None
    try:
        result = subprocess.run(
            ["uv", "run", str(cli), "--state-dir", str(state_dir), "ready"],
            capture_output=True,
            text=True,
            timeout=TRACKER_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, None
    if result.returncode != 0:
        return None, None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(data, list) or not data:
        return None, None
    first = data[0]
    return first.get("id"), first.get("title")


def short_model(model_id: str, model_display: str) -> str:
    """Compact model label for the status line."""
    if model_display:
        return model_display.lower().replace(" ", "-")
    return model_id.replace("claude-", "") if model_id else "?"


def render_line(state: BridgeState) -> str:
    bar = render_bar(state.used_percentage)
    pct = f"{state.used_percentage:.0f}%"
    model_tag = short_model(state.model_id, state.model_display)
    if state.current_step_id and state.mode:
        return (
            f"deep:{state.mode} {state.current_step_id} "
            f"{bar} {pct} [{model_tag}]"
        )
    return f"ctx {bar} {pct} [{model_tag}]"


def render_unavailable(model_id: str, model_display: str) -> str:
    """When current_usage is null (pre-first-call or post-/compact)."""
    bar = render_bar(0)
    return f"ctx {bar} --% [{short_model(model_id, model_display)}]"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # No JSON: print nothing, exit 0 (status line stays blank)
        return 0
    except Exception:
        return 0

    session_id = payload.get("session_id") or "unknown"
    model_obj = payload.get("model") or {}
    model_id = model_obj.get("id") or ""
    model_display = model_obj.get("display_name") or ""

    context_obj = payload.get("context_window") or {}
    current_usage = context_obj.get("current_usage")
    stdin_size = context_obj.get("context_window_size")

    context_size = resolve_context_size(model_id or None, stdin_size)

    if current_usage is None:
        # No usage data yet — render placeholder, do not write bridge.
        print(render_unavailable(model_id, model_display))
        return 0

    # Prefer Claude Code's own used_percentage if present; else compute.
    used_tokens = compute_used_input_tokens(current_usage)
    if "used_percentage" in context_obj and isinstance(
        context_obj["used_percentage"], (int, float)
    ):
        used_pct = round(float(context_obj["used_percentage"]), 2)
    else:
        used_pct = compute_used_percentage(used_tokens, context_size)

    level = classify_level(used_pct)

    planning_dir = resolve_planning_dir()
    mode: str | None = None
    step_id: str | None = None
    step_title: str | None = None
    if planning_dir is not None:
        mode = detect_mode(planning_dir)
        step_id, step_title = query_tracker(planning_dir)

    # Preserve debounce counters across writes by reading the existing bridge.
    prior_path = bridge_path(session_id)
    prior = read_bridge(prior_path) if prior_path.exists() else None
    last_emitted = prior.last_emitted_level if prior else None
    tool_calls = prior.tool_calls_since_emit if prior else 0

    state = BridgeState(
        session_id=session_id,
        model_id=model_id,
        model_display=model_display,
        context_window_size=context_size,
        used_input_tokens=used_tokens,
        used_percentage=used_pct,
        level=level,
        current_step_id=step_id,
        current_step_title=step_title,
        planning_dir=str(planning_dir) if planning_dir else None,
        mode=mode,
        last_emitted_level=last_emitted,
        tool_calls_since_emit=tool_calls,
        ts=time.time(),
    )

    try:
        write_bridge(state)
    except OSError:
        pass

    print(render_line(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())

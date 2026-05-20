#!/usr/bin/env python3
"""PostToolUse hook — inject context-pressure warnings into Claude's context.

Reads the bridge file written by ``deep-statusline.py`` and emits a JSON
envelope with ``additionalContext`` when ``used_percentage`` crosses warning
or critical thresholds.

Behavior:
- normal level: silent.
- warning / critical: emit the formatted message, update debounce state in
  the bridge file.
- escalation (warning → critical) bypasses the 5-tool-call debounce.
- missing/stale/unreadable bridge: silent.

Registration in ``hooks/hooks.json`` (PostToolUse, no matcher → runs after
every tool call). Plain stdout is discarded by Claude Code for PostToolUse;
the only way to inject context is the ``hookSpecificOutput.additionalContext``
JSON envelope.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from lib.context_metrics import (  # noqa: E402
    build_envelope,
    bridge_path,
    format_warning,
    is_stale,
    read_bridge,
    should_emit,
    write_bridge,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    except Exception:
        return 0

    session_id = payload.get("session_id")
    if not session_id:
        return 0

    path = bridge_path(session_id)
    state = read_bridge(path)
    if state is None:
        return 0
    if is_stale(state):
        return 0

    emit = should_emit(state.level, state.last_emitted_level, state.tool_calls_since_emit)

    if not emit:
        # Increment counter only when a prior emit exists at the same level
        # and we are still in a non-normal level.
        if state.level != "normal" and state.last_emitted_level == state.level:
            state.tool_calls_since_emit += 1
            try:
                write_bridge(state, path)
            except OSError:
                pass
        return 0

    message = format_warning(state)
    if not message:
        return 0

    envelope = build_envelope(message)
    print(json.dumps(envelope))

    state.last_emitted_level = state.level
    state.tool_calls_since_emit = 0
    try:
        write_bridge(state, path)
    except OSError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

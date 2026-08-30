#!/usr/bin/env python3
"""PreToolUse guardrail hook — blocks credentials, pauses on protected paths.

Thin adapter over scripts/lib/guard.py; all decision logic lives there so it can
be tested without a subprocess.

Fails open by design. Any exception, malformed payload or unreadable config
exits 0 silently: this hook must never be the reason an edit fails.

Never print anything except the JSON envelope — stray stdout breaks Claude
Code's hook parser.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    try:
        from lib.guard import decide, load_guard_config, render_pre_output

        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input") or {}
        cwd = Path(payload.get("cwd") or Path.cwd())

        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        config = load_guard_config(
            cwd,
            plugin_root=Path(plugin_root) if plugin_root else _fallback_plugin_root(),
        )

        output = render_pre_output(decide(tool_name, tool_input, cwd, config))
        if output is not None:
            print(json.dumps(output))
    except Exception:
        return 0

    return 0


def _fallback_plugin_root() -> Path:
    """CLAUDE_PLUGIN_ROOT is set in normal operation; this covers direct
    invocation in tests."""
    return Path(__file__).resolve().parent.parent.parent


if __name__ == "__main__":
    sys.exit(main())

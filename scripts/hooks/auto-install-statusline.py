#!/usr/bin/env python3
"""SessionStart hook — auto-install deep-statusline on first run.

Claude Code plugins cannot declare a top-level ``statusLine`` config in
``hooks/hooks.json`` or plugin ``settings.json``. To get parity with a
zero-touch install, this SessionStart hook shells to
``install-statusline.py`` once. It is idempotent — subsequent SessionStart
events are no-ops because the installer detects its own ``deepInstalledBy``
marker.

Stays silent unless the install actually performed work on this run. In
that case it injects a one-line ``additionalContext`` notice so the agent
can mention the change.

Opt-out: set ``DEEP_DISABLE_STATUSLINE_INSTALL=1`` in the environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
DEEP_MARKER = "deep-plan-enhanced"


def already_installed() -> bool:
    """Cheap check — avoids spawning the installer when nothing to do."""
    if not SETTINGS_PATH.exists():
        return False
    try:
        with SETTINGS_PATH.open() as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    sl = data.get("statusLine")
    return isinstance(sl, dict) and sl.get("deepInstalledBy") == DEEP_MARKER


def main() -> int:
    # Drain stdin so Claude Code does not block on a closed pipe.
    try:
        sys.stdin.read()
    except Exception:
        pass

    if os.environ.get("DEEP_DISABLE_STATUSLINE_INSTALL") == "1":
        return 0

    if already_installed():
        return 0

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get(
        "DEEP_PLUGIN_ROOT"
    )
    if not plugin_root:
        plugin_root = str(Path(__file__).resolve().parent.parent.parent)

    installer = Path(plugin_root) / "scripts" / "checks" / "install-statusline.py"
    if not installer.exists():
        return 0

    try:
        result = subprocess.run(
            ["uv", "run", str(installer)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0

    if result.returncode != 0:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "deep-plan-enhanced: installed statusLine entry in "
                f"{SETTINGS_PATH}. Restart Claude Code for the bar to render. "
                "Reverse with `uv run "
                f"{installer} --uninstall`. "
                "Disable auto-install permanently with "
                "`export DEEP_DISABLE_STATUSLINE_INSTALL=1`."
            ),
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())

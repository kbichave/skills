#!/usr/bin/env python3
"""PreToolUse hook: keep the warehouse tier's SQL read-only.

Thin adapter over scripts/lib/sql_guard.py. Acts only when the tool is a
warehouse SQL tool AND a data-tier run is open for this session (the marker
`scripts/checks/data-tier.py start` writes). Outside a data-tier run it does
nothing, so a user's own warehouse work in the same session is untouched.

Inside a run it denies a statement that is not single, read-only, star-free
and bounded, naming the rule so the agent can rewrite it.

Fails open on its own errors: a crashed hook must never block a tool call.
Never print anything except the JSON envelope; stray stdout breaks Claude
Code's hook parser.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    try:
        from lib.sql_guard import WAREHOUSE_TOOL, classify, extract_sql, is_active

        tool_name = payload.get("tool_name", "")
        if not WAREHOUSE_TOOL.match(tool_name):
            return 0
        if not is_active(str(payload.get("session_id") or "")):
            return 0

        for sql in extract_sql(payload.get("tool_input") or {}):
            reason = classify(sql)
            if reason:
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"data-tier SQL guard: {reason}",
                    }
                }))
                return 0
    except Exception:  # noqa: BLE001 - hooks fail open
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

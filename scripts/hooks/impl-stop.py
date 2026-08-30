#!/usr/bin/env python3
"""Stop hook for deep-implement: Verify sections and request exit summary.

Session binding is delegated to lib.session_paths, which prefers the session_id
on the hook payload over the env var and over stale on-disk markers.
"""

import json
import re
import sys
from pathlib import Path

# Ensure scripts/lib is importable when running as a hook (cwd may differ)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from lib.scratch import cleanup_scratch
except ImportError:
    cleanup_scratch = None  # type: ignore[assignment]
from lib.session_paths import find_planning_dir, session_id_from_payload


def _payload() -> dict:
    """Hook payload from stdin. Absent or malformed input is not an error —
    the resolver falls back to the env var and the active-session marker."""
    try:
        return json.load(sys.stdin) or {}
    except (ValueError, OSError):
        return {}


def find_active_dir(payload: dict | None = None) -> Path | None:
    """Find the active planning directory for the current session."""
    return find_planning_dir(session_id_from_payload(payload or {}))


def main() -> int:
    active_dir = find_active_dir(_payload())
    if not active_dir:
        return 0

    progress_file = active_dir / "impl-progress.md"
    if not progress_file.exists():
        return 0

    content = progress_file.read_text()

    # Count section checklist items
    total = len(re.findall(r"^- \[[ x]\]", content, re.MULTILINE))
    completed = len(re.findall(r"^- \[x\]", content, re.MULTILINE))

    if total == 0:
        return 0

    # Check if summary already exists (don't re-prompt)
    summary_file = active_dir / "impl-summary.md"
    has_summary = summary_file.exists() and summary_file.stat().st_size > 0

    if has_summary:
        # Mode is complete — sweep mode-scoped scratch artifacts
        if cleanup_scratch is not None:
            try:
                cleanup_scratch(active_dir, trigger="mode-complete")
            except Exception:
                pass  # Cleanup is best-effort; never block exit
        return 0

    if completed >= total:
        output = {
            "followup_message": (
                f"[deep-implement] ALL SECTIONS COMPLETE ({completed}/{total}). "
                "Before exiting, write an implementation summary to "
                f"{active_dir}/impl-summary.md with:\n"
                "1. What was implemented (section-by-section, 1-2 sentences each)\n"
                "2. Key technical decisions made\n"
                "3. Known issues or TODOs remaining\n"
                "4. Test results (pass/fail count)\n"
                "5. Files created or modified\n"
                "6. Post-mortem: \"what would have prevented the rework that "
                "happened in this mode?\" Answer honestly:\n"
                "   - If architectural (no good test seam, tangled callers, "
                "hidden coupling): add a `## Architectural follow-ups` section "
                "with specifics and suggest invoking "
                "Skill(improve-codebase-architecture) on the next session.\n"
                "   - If spec clarity (confidence gate kept firing at 5-7): "
                "add `## Spec gaps observed` with what was unclear, so the "
                "next plan iteration tightens.\n"
                "   - If nothing — went clean: say so explicitly. Do not "
                "invent rework.\n"
                "Then you may exit."
            )
        }
    else:
        pending = total - completed
        output = {
            "followup_message": (
                f"[deep-implement] Implementation incomplete ({completed}/{total} sections, "
                f"{pending} remaining). Before exiting, write a session summary to "
                f"{active_dir}/impl-summary.md with:\n"
                "1. What was completed this session\n"
                "2. What remains and any blockers\n"
                "3. Errors encountered and how they were resolved\n"
                "4. Where to pick up next session\n"
                "5. Post-mortem: any architectural or spec-clarity gaps "
                "discovered while landing the completed sections (see Phase 10 "
                "in references/implement-protocol.md)\n"
                "Then you may exit."
            )
        }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Resolve which planning directory the current session belongs to.

Shared by the implement hooks. It lives here rather than being copy-pasted into
each hook because the two copies had already drifted into the same silent
failure: they looked for a per-session marker that nothing in the codebase ever
wrote, then fell back to "most recently modified marker", and when those pointed
at long-deleted directories they returned None. A hook that returns None does
nothing, so `impl-stop`'s "you must write an implementation summary" gate had
been passing silently for months.

Resolution order, first hit that exists on disk wins:

1. `session_id` from the hook's stdin payload — the only source that is
   actually per-session and always present.
2. `$DEEP_SESSION_ID` marker — set by the SessionStart hook.
3. `~/.claude/.deep-plan-active` — written by `setup-session.py` on every new
   session, so it is the one file that is reliably maintained.
4. Most recently modified marker, skipping any whose target is gone.

Every candidate is checked with `is_dir()`. Returning a stale path is worse
than returning nothing, because the caller then writes progress into another
project's session.

Steps 1-2 are `find_session_planning_dir`; steps 3-4 are the fallback that
only `find_planning_dir` applies. A caller that *displays* state must use the
former — the global pointer belongs to whichever session ran `/deep` last on
this machine, which is nobody in particular.
"""

from __future__ import annotations

import os
from pathlib import Path

def _claude_home() -> Path:
    """`~/.claude`, overridable via `$DEEP_STATE_HOME`.

    Read lazily so tests can redirect it after import. Without the override the
    suite writes session markers into the developer's real home and then reads
    them back in later tests, which is how a marker from one test can decide
    another test's answer.
    """
    return Path(os.environ.get("DEEP_STATE_HOME") or Path.home() / ".claude")


def marker_dir() -> Path:
    return _claude_home() / ".deep-implement-sessions"


def active_marker() -> Path:
    return _claude_home() / ".deep-plan-active"


def _read_dir(path: Path) -> Path | None:
    try:
        candidate = Path(path.read_text().strip())
    except (OSError, ValueError):
        return None
    return candidate if candidate.is_dir() else None


def marker_path(session_id: str) -> Path:
    return marker_dir() / f"{session_id}.marker"


def write_marker(session_id: str, planning_dir: Path) -> bool:
    """Record which planning dir a session owns. Best-effort.

    Without this the per-session lookup can never hit, which is exactly how the
    hooks ended up silently inert.
    """
    if not session_id:
        return False
    try:
        marker_dir().mkdir(parents=True, exist_ok=True)
        marker_path(session_id).write_text(str(planning_dir))
        return True
    except OSError:
        return False


def find_session_planning_dir(session_id: str | None = None) -> Path | None:
    """The planning dir *this session* owns, or None. Never another session's.

    Split out of `find_planning_dir` because the two callers want opposite
    things when the session owns nothing. A hook about to write progress would
    rather fall back to the machine's active session than do nothing; a
    display would rather show nothing than another project's run.

    The display got the hook's answer, and it shipped: `~/.claude/.deep-plan-active`
    is one file for the whole machine, nothing clears it, so a stalled goalloop
    from another repo rendered into the status line of every session on the box
    until the next `/deep` overwrote the pointer.
    """
    candidates: list[str] = []
    if session_id:
        candidates.append(session_id)
    env_id = os.environ.get("DEEP_SESSION_ID")
    if env_id and env_id not in candidates:
        candidates.append(env_id)

    for candidate_id in candidates:
        marker = marker_path(candidate_id)
        if marker.exists():
            resolved = _read_dir(marker)
            if resolved:
                return resolved
    return None


def find_planning_dir(session_id: str | None = None) -> Path | None:
    """Best available planning directory, or None. Never raises."""
    owned = find_session_planning_dir(session_id)
    if owned is not None:
        return owned

    active = active_marker()
    if active.exists():
        resolved = _read_dir(active)
        if resolved:
            return resolved

    directory = marker_dir()
    if not directory.is_dir():
        return None
    try:
        markers = sorted(
            directory.glob("*.marker"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    for marker in markers:
        resolved = _read_dir(marker)
        if resolved:
            return resolved
    return None


def session_id_from_payload(payload: dict) -> str | None:
    """Claude Code puts `session_id` in every hook payload."""
    value = payload.get("session_id")
    return str(value) if value else None

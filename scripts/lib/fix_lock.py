"""Test-file lock — the thing that makes a passing test mean something.

Playbook Stage 4: a test that existed before the fix, and that the agent could
not rewrite, is the proof the bug is gone. Without the lock, "all tests pass"
is satisfiable by editing the test, and the loop closes on itself.

The lock is opened when tests are written (Phase 3 step 1, before any
implementation exists) and covers exactly the files named in it. It is a
`deny` rather than an `ask`, because the whole point is that the agent cannot
clear it on its own — but a human can, and the block message says how.

Fails open like every other guardrail here: unreadable or malformed lock means
no lock. A hook bug must never stop a person editing their own tests.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOCK_FILENAME = "fix-lock.json"
LOCK_OFF_ENV = "DEEP_FIX_LOCK"

# Conservative on purpose: a false positive here blocks a legitimate edit, and
# the cost of missing one file is only that the lock is narrower than ideal.
_TEST_PATTERNS = (
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"[^/]+_test\.(py|go)$"),
    re.compile(r"[^/]+\.(test|spec)\.(ts|tsx|js|jsx)$"),
    re.compile(r"(^|/)conftest\.py$"),
)


@dataclass(frozen=True, slots=True)
class FixLock:
    active: bool = False
    section_id: str = ""
    reason: str = ""
    protected: tuple[str, ...] = ()
    opened_at: str = ""
    override_reason: str | None = None
    blocks: int = 0

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "section_id": self.section_id,
            "reason": self.reason,
            "protected": list(self.protected),
            "opened_at": self.opened_at,
            "override_reason": self.override_reason,
            "blocks": self.blocks,
        }


@dataclass(frozen=True, slots=True)
class LockDecision:
    blocked: bool
    reason: str = ""
    protected_path: str = ""
    detail: dict = field(default_factory=dict)


ALLOWED = LockDecision(blocked=False)


def is_test_path(rel_path: str) -> bool:
    return any(pattern.search(rel_path) for pattern in _TEST_PATTERNS)


def lock_path(planning_dir: Path) -> Path:
    return Path(planning_dir) / ".deepstate" / LOCK_FILENAME


def lock_disabled_by_env() -> bool:
    return os.environ.get(LOCK_OFF_ENV, "").strip().lower() in {"off", "0", "false"}


def read_lock(planning_dir: Path) -> FixLock:
    """Never raises. A malformed lock is no lock."""
    try:
        data = json.loads(lock_path(planning_dir).read_text())
    except (OSError, ValueError):
        return FixLock()
    if not isinstance(data, dict):
        return FixLock()
    return FixLock(
        active=bool(data.get("active", False)),
        section_id=str(data.get("section_id", "")),
        reason=str(data.get("reason", "")),
        protected=tuple(
            p for p in (data.get("protected") or []) if isinstance(p, str)
        ),
        opened_at=str(data.get("opened_at", "")),
        override_reason=data.get("override_reason"),
        blocks=int(data.get("blocks", 0) or 0),
    )


def write_lock(planning_dir: Path, lock: FixLock) -> bool:
    """Best-effort, atomic. Returns False rather than raising."""
    path = lock_path(planning_dir)
    tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(lock.to_dict(), indent=2))
        os.replace(tmp, path)
        return True
    except OSError:
        # The cleanup can itself fail (the parent may not be a directory), and
        # an exception raised inside the handler would escape it.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def open_lock(
    planning_dir: Path, *, section_id: str, protected: list[str], reason: str = ""
) -> FixLock:
    lock = FixLock(
        active=True,
        section_id=section_id,
        reason=reason or "tests written before implementation",
        protected=tuple(sorted(set(protected))),
        opened_at=datetime.now(timezone.utc).isoformat(),
    )
    write_lock(planning_dir, lock)
    return lock


def close_lock(planning_dir: Path) -> bool:
    return write_lock(planning_dir, FixLock(active=False))


def add_protected(planning_dir: Path, paths: list[str]) -> FixLock:
    """Widen the lock. Phase 9 uses this on strike >= 1, when the temptation to
    edit the test rather than the code is strongest."""
    current = read_lock(planning_dir)
    from dataclasses import replace

    widened = replace(
        current, protected=tuple(sorted(set(current.protected) | set(paths)))
    )
    write_lock(planning_dir, widened)
    return widened


def override(planning_dir: Path, reason: str) -> FixLock:
    """Human escape hatch. Requires a reason, which lands in the lock file so
    the override is visible afterwards rather than silent."""
    from dataclasses import replace

    released = replace(read_lock(planning_dir), active=False, override_reason=reason)
    write_lock(planning_dir, released)
    return released


def decide(rel_path: str, lock: FixLock) -> LockDecision:
    """Block only files the lock explicitly names.

    Deliberately not "block anything that looks like a test": the lock exists to
    protect the specific tests that pin the current bug, and over-blocking is
    how the feature gets switched off.
    """
    if not lock.active or lock_disabled_by_env():
        return ALLOWED
    if rel_path not in lock.protected:
        return ALLOWED

    return LockDecision(
        blocked=True,
        protected_path=rel_path,
        reason=(
            f"[deep-fix-lock] BLOCKED: {rel_path} is one of the tests pinning "
            f"section {lock.section_id or 'in progress'}. It was written before "
            "the implementation, and not editing it is what makes it proof the "
            "bug is fixed. Change the code instead. If the test itself is "
            "genuinely wrong, release the lock explicitly: "
            "`fix-lock.py override --reason \"...\"`, or set "
            f"{LOCK_OFF_ENV}=off for this session."
        ),
        detail={"section_id": lock.section_id, "opened_at": lock.opened_at},
    )

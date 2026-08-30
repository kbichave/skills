"""Durable record of work an autonomous run could not finish.

`/deep implement --auto` never stops to ask. Phase 1 skips a section it cannot
rate, Phase 9 rolls one back after three strikes — and in interactive mode both
escalate to the user. In auto there is no user, so without this the escalation
evaporates and the run reports success over work it silently dropped.

This is the queue those escalations land in. It exists so the end-of-run summary
can answer "what did auto skip, and why", and so a later session can pick the
work up rather than rediscover it.

Deliberately not a blocker. An autonomous run that halts on the first hard
section gets nothing else done; one that skips, records, and reports is more
useful — provided the report is honest, which is what this enforces.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

HANDOFF_FILENAME = "needs-human.json"

# Why a section landed here. Kept small on purpose: a taxonomy nobody can
# remember gets filled in at random.
REASONS = frozenset(
    {
        "low_confidence",   # Phase 1 rated 1-4 and auto skipped rather than grilling
        "three_strikes",    # Phase 9 rolled back after three failed attempts
        "gate_failed",      # Phase 6 quality gate never passed
        "blocked",          # a dependency never landed
        "other",
    }
)


@dataclass(frozen=True, slots=True)
class HandoffItem:
    section: str
    reason: str
    detail: str = ""
    recorded_at: str = ""
    attempts: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def handoff_path(planning_dir: Path) -> Path:
    return Path(planning_dir) / ".deepstate" / HANDOFF_FILENAME


def load(planning_dir: Path) -> list[HandoffItem]:
    """Never raises. A malformed file is an empty queue."""
    try:
        data = json.loads(handoff_path(planning_dir).read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    items: list[HandoffItem] = []
    for entry in data:
        if not isinstance(entry, dict) or not entry.get("section"):
            continue
        items.append(
            HandoffItem(
                section=str(entry["section"]),
                reason=str(entry.get("reason", "other")),
                detail=str(entry.get("detail", "")),
                recorded_at=str(entry.get("recorded_at", "")),
                attempts=int(entry.get("attempts", 0) or 0),
            )
        )
    return items


def _save(planning_dir: Path, items: list[HandoffItem]) -> bool:
    path = handoff_path(planning_dir)
    tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps([i.to_dict() for i in items], indent=2))
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def record(
    planning_dir: Path,
    *,
    section: str,
    reason: str,
    detail: str = "",
    attempts: int = 0,
) -> HandoffItem:
    """Add or replace the entry for a section.

    Re-recording the same section overwrites rather than appends: the latest
    reason is the true one, and a duplicated section in the summary reads as
    two separate failures.
    """
    item = HandoffItem(
        section=section,
        reason=reason if reason in REASONS else "other",
        detail=detail,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        attempts=attempts,
    )
    items = [i for i in load(planning_dir) if i.section != section]
    items.append(item)
    _save(planning_dir, items)
    return item


def clear(planning_dir: Path, section: str) -> bool:
    """Drop a section, for when a later pass completes it."""
    items = load(planning_dir)
    remaining = [i for i in items if i.section != section]
    if len(remaining) == len(items):
        return False
    _save(planning_dir, remaining)
    return True


def summary(planning_dir: Path) -> str:
    """Markdown for the end-of-run summary.

    Returns an explicit "nothing was skipped" line rather than an empty string,
    because silence is indistinguishable from the feature not running.
    """
    items = load(planning_dir)
    if not items:
        return "## Needs human\n\nNothing was skipped or rolled back."

    lines = [
        "## Needs human",
        "",
        f"{len(items)} section{'s' if len(items) != 1 else ''} did not land. "
        "Autonomous mode recorded them and continued.",
        "",
        "| Section | Reason | Attempts | Detail |",
        "|---|---|---|---|",
    ]
    for item in sorted(items, key=lambda i: i.section):
        detail = item.detail.replace("|", "\\|")[:120] or "—"
        lines.append(
            f"| `{item.section}` | {item.reason} | {item.attempts} | {detail} |"
        )
    return "\n".join(lines)

"""Machine-readable verification status per section.

Today Phase 6 runs the quality gate and Phase 10 writes prose into
`impl-summary.md`. Prose cannot be routed on, so `/deep auto` has nothing to
consult and skips its human checkpoints unconditionally — it advances past a
phase it should have stopped at.

This is the status the autonomous loop routes on. Three values, deliberately:

- `passed`      — gates green, no blocking review findings, no strikes.
                  Safe to advance without a human.
- `gaps_found`  — something concrete failed. A human should look, and the run
                  should not silently continue as if it had not.
- `human_needed`— the run could not determine an answer by itself (confidence
                  too low, a decision it is not entitled to make).

The distinction between the last two matters: `gaps_found` is "this is broken",
`human_needed` is "I should not be the one deciding this". They warrant
different responses from a person.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

VERIFICATION_FILENAME = "verification.json"

PASSED = "passed"
GAPS_FOUND = "gaps_found"
HUMAN_NEEDED = "human_needed"

STATUSES = (PASSED, GAPS_FOUND, HUMAN_NEEDED)

# Worst-first. Aggregating a phase takes the worst section status, because one
# broken section does not become acceptable by sitting next to nine good ones.
_SEVERITY = {HUMAN_NEEDED: 2, GAPS_FOUND: 1, PASSED: 0}


@dataclass(frozen=True, slots=True)
class SectionResult:
    section: str
    status: str
    gates_passed: bool = True
    blocking_findings: int = 0
    strikes: int = 0
    detail: str = ""
    recorded_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PhaseStatus:
    status: str
    sections: int
    passed: int
    failing: tuple[str, ...] = ()
    reasons: dict = field(default_factory=dict)

    @property
    def can_advance(self) -> bool:
        return self.status == PASSED

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "can_advance": self.can_advance,
            "sections": self.sections,
            "passed": self.passed,
            "failing": list(self.failing),
            "reasons": dict(self.reasons),
        }


def verification_path(planning_dir: Path) -> Path:
    return Path(planning_dir) / ".deepstate" / VERIFICATION_FILENAME


def classify(
    *, gates_passed: bool, blocking_findings: int = 0, strikes: int = 0
) -> str:
    """Derive a status from what Phase 6 and Phase 5b actually observed."""
    if strikes >= 3:
        # Three attempts at the same failure is not a gap to fix, it is a
        # signal the run cannot get there on its own.
        return HUMAN_NEEDED
    if not gates_passed or blocking_findings > 0:
        return GAPS_FOUND
    return PASSED


def load(planning_dir: Path) -> list[SectionResult]:
    """Never raises. A malformed file means nothing has been verified."""
    try:
        data = json.loads(verification_path(planning_dir).read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    results: list[SectionResult] = []
    for entry in data:
        if not isinstance(entry, dict) or not entry.get("section"):
            continue
        status = str(entry.get("status", ""))
        results.append(
            SectionResult(
                section=str(entry["section"]),
                status=status if status in STATUSES else HUMAN_NEEDED,
                gates_passed=bool(entry.get("gates_passed", False)),
                blocking_findings=int(entry.get("blocking_findings", 0) or 0),
                strikes=int(entry.get("strikes", 0) or 0),
                detail=str(entry.get("detail", "")),
                recorded_at=str(entry.get("recorded_at", "")),
            )
        )
    return results


def _save(planning_dir: Path, results: list[SectionResult]) -> bool:
    path = verification_path(planning_dir)
    tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps([r.to_dict() for r in results], indent=2))
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
    gates_passed: bool,
    blocking_findings: int = 0,
    strikes: int = 0,
    detail: str = "",
) -> SectionResult:
    """Record one section's outcome, replacing any earlier entry for it."""
    result = SectionResult(
        section=section,
        status=classify(
            gates_passed=gates_passed,
            blocking_findings=blocking_findings,
            strikes=strikes,
        ),
        gates_passed=gates_passed,
        blocking_findings=blocking_findings,
        strikes=strikes,
        detail=detail,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    results = [r for r in load(planning_dir) if r.section != section]
    results.append(result)
    _save(planning_dir, results)
    return result


def phase_status(planning_dir: Path, *, expected_sections: int = 0) -> PhaseStatus:
    """Aggregate to a single routable status for the phase.

    Sections that were never verified count as `human_needed`, not as passing.
    Absence of evidence is the most common way an autonomous run convinces
    itself everything is fine.
    """
    results = load(planning_dir)
    reasons = {r.section: r.status for r in results if r.status != PASSED}
    failing = tuple(sorted(reasons))

    worst = PASSED
    for result in results:
        if _SEVERITY[result.status] > _SEVERITY[worst]:
            worst = result.status

    unverified = max(0, expected_sections - len(results))
    if unverified:
        worst = HUMAN_NEEDED if _SEVERITY[HUMAN_NEEDED] > _SEVERITY[worst] else worst
        reasons["<unverified>"] = f"{unverified} section(s) never recorded a result"
        failing = tuple(sorted(reasons))

    return PhaseStatus(
        status=worst,
        sections=len(results),
        passed=sum(1 for r in results if r.status == PASSED),
        failing=failing,
        reasons=reasons,
    )

"""Stall detection for external review revision loops.

Detects two stall patterns:

1. **No-progress diff** — consecutive revisions whose content differs by less
   than `min_diff_ratio` (default 10%). The reviewer is being placated, not
   improving the artifact.

2. **Recurring finding** — the same reviewer concern appears in two or more
   consecutive revisions. The fix attempts are not addressing the root issue.

Usage:

    detector = StallDetector(min_diff_ratio=0.10)
    detector.record_revision("rev-1", text="…", findings=["Add error handling"])
    detector.record_revision("rev-2", text="…", findings=["Add error handling"])
    verdict = detector.check()
    if verdict.stalled:
        # surface verdict.reason to the user, or auto-accept-with-caveat
        ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional


@dataclass
class Revision:
    """One revision of the artifact + reviewer findings against it."""
    label: str
    text: str
    findings: list[str] = field(default_factory=list)


@dataclass
class StallVerdict:
    """Result of stall detection.

    `stalled = True` means the parent loop should escalate (interactive) or
    accept-with-caveat (autonomous). `reason` is the human-readable
    explanation suitable for surfacing to the user or appending to a log.
    """
    stalled: bool
    reason: str
    diff_ratio: Optional[float] = None
    recurring_findings: list[str] = field(default_factory=list)


_FINDING_NORMALISE_RE = re.compile(r"[^a-z0-9]+")


def _normalise_finding(finding: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to spaces, strip."""
    return _FINDING_NORMALISE_RE.sub(" ", finding.lower()).strip()


def _content_diff_ratio(a: str, b: str) -> float:
    """Fraction of `b` content that differs from `a`. 0.0 = identical, 1.0 = unrelated.

    Uses SequenceMatcher.ratio() (symmetric similarity), then converts to
    diff ratio = 1 - similarity. Computed line-wise to focus on structural
    changes, not whitespace fiddles.
    """
    a_lines = [ln.strip() for ln in a.splitlines() if ln.strip()]
    b_lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
    if not a_lines and not b_lines:
        return 0.0
    similarity = SequenceMatcher(None, a_lines, b_lines).ratio()
    return 1.0 - similarity


class StallDetector:
    """Tracks revisions and surfaces stall conditions."""

    def __init__(self, min_diff_ratio: float = 0.10) -> None:
        """Initialise.

        `min_diff_ratio` — below this fraction of changed lines between two
        consecutive revisions, the loop is considered stalled. Default 0.10
        (10%) matches gsd's heuristic.
        """
        if not 0.0 < min_diff_ratio < 1.0:
            raise ValueError(
                f"min_diff_ratio must be in (0, 1), got {min_diff_ratio}"
            )
        self.min_diff_ratio = min_diff_ratio
        self.revisions: list[Revision] = []

    def record_revision(
        self,
        label: str,
        *,
        text: str,
        findings: Optional[list[str]] = None,
    ) -> None:
        """Append a revision. Call once per reviewer round."""
        self.revisions.append(
            Revision(label=label, text=text, findings=list(findings or []))
        )

    def check(self) -> StallVerdict:
        """Evaluate stall conditions across recorded revisions.

        Returns a verdict with the first detected stall condition. Order of
        checks: no-progress diff first (cheaper signal), then recurring
        finding. Both checks need at least two revisions.
        """
        if len(self.revisions) < 2:
            return StallVerdict(stalled=False, reason="Not enough revisions to evaluate")

        last = self.revisions[-1]
        prev = self.revisions[-2]

        # Check 1 — no-progress diff between last two revisions
        diff_ratio = _content_diff_ratio(prev.text, last.text)
        if diff_ratio < self.min_diff_ratio:
            return StallVerdict(
                stalled=True,
                reason=(
                    f"No-progress diff: revision {last.label} differs from "
                    f"{prev.label} by only {diff_ratio:.1%} (threshold "
                    f"{self.min_diff_ratio:.0%}). Reviewer revisions are "
                    "no longer changing the artifact materially."
                ),
                diff_ratio=diff_ratio,
            )

        # Check 2 — recurring finding across last two revisions
        last_findings = {_normalise_finding(f) for f in last.findings if f.strip()}
        prev_findings = {_normalise_finding(f) for f in prev.findings if f.strip()}
        recurring = last_findings & prev_findings
        if recurring:
            # Surface the original (un-normalised) wording from the latest revision
            recurring_originals = [
                f for f in last.findings
                if _normalise_finding(f) in recurring
            ]
            return StallVerdict(
                stalled=True,
                reason=(
                    f"Recurring finding(s) across {prev.label} and {last.label}: "
                    f"{', '.join(recurring_originals)}. Fix attempts not "
                    "addressing the root issue."
                ),
                diff_ratio=diff_ratio,
                recurring_findings=recurring_originals,
            )

        return StallVerdict(stalled=False, reason="Revision loop progressing", diff_ratio=diff_ratio)

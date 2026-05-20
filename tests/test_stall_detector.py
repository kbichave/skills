"""Tests for scripts/lib/stall_detector.py — revision loop stall detection."""

from __future__ import annotations

import pytest

from scripts.lib.stall_detector import (
    StallDetector,
    StallVerdict,
    _content_diff_ratio,
    _normalise_finding,
)


# ── Helpers ──────────────────────────────────────────────────────────


class TestContentDiffRatio:
    def test_identical_returns_zero(self):
        text = "line one\nline two\nline three"
        assert _content_diff_ratio(text, text) == 0.0

    def test_completely_different_high(self):
        # Sufficiently different to exceed any reasonable threshold
        assert _content_diff_ratio("a\nb\nc", "x\ny\nz") > 0.9

    def test_whitespace_only_change_ignored(self):
        a = "line one\nline two\nline three"
        b = "  line one  \n  line two  \n  line three  "
        assert _content_diff_ratio(a, b) == 0.0

    def test_empty_inputs(self):
        assert _content_diff_ratio("", "") == 0.0


class TestNormaliseFinding:
    def test_lowercases_and_strips_punctuation(self):
        assert _normalise_finding("Add Error Handling!") == "add error handling"

    def test_collapses_whitespace(self):
        assert _normalise_finding("foo    bar") == "foo bar"


# ── StallDetector ────────────────────────────────────────────────────


class TestStallDetector:
    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError):
            StallDetector(min_diff_ratio=0.0)
        with pytest.raises(ValueError):
            StallDetector(min_diff_ratio=1.0)

    def test_single_revision_not_stalled(self):
        d = StallDetector()
        d.record_revision("rev-1", text="foo")
        verdict = d.check()
        assert verdict.stalled is False
        assert "Not enough" in verdict.reason

    def test_substantial_diff_not_stalled(self):
        d = StallDetector(min_diff_ratio=0.10)
        d.record_revision("rev-1", text="line a\nline b\nline c\nline d")
        d.record_revision("rev-2", text="line a\nline e\nline f\nline g")
        verdict = d.check()
        assert verdict.stalled is False

    def test_identical_revisions_stalled(self):
        d = StallDetector(min_diff_ratio=0.10)
        text = "line a\nline b\nline c"
        d.record_revision("rev-1", text=text)
        d.record_revision("rev-2", text=text)
        verdict = d.check()
        assert verdict.stalled is True
        assert "No-progress diff" in verdict.reason

    def test_tiny_diff_stalled(self):
        d = StallDetector(min_diff_ratio=0.10)
        d.record_revision(
            "rev-1",
            text="\n".join(f"line {i}" for i in range(20))
        )
        # Change 1 of 20 lines = 5% diff, under the 10% threshold
        text_b = "\n".join(["line 0 EDITED"] + [f"line {i}" for i in range(1, 20)])
        d.record_revision("rev-2", text=text_b)
        verdict = d.check()
        assert verdict.stalled is True
        assert verdict.diff_ratio is not None
        assert verdict.diff_ratio < 0.10

    def test_recurring_finding_stalled(self):
        d = StallDetector(min_diff_ratio=0.05)
        # Substantial diff to bypass diff check
        d.record_revision(
            "rev-1",
            text="\n".join(f"line {i}" for i in range(20)),
            findings=["Missing error handling in token refresh"],
        )
        d.record_revision(
            "rev-2",
            text="\n".join(f"changed-line {i}" for i in range(20)),
            findings=["Missing error handling in token refresh", "Other thing"],
        )
        verdict = d.check()
        assert verdict.stalled is True
        assert "Recurring finding" in verdict.reason
        assert any("error handling" in f.lower() for f in verdict.recurring_findings)

    def test_finding_normalisation_catches_minor_rewording(self):
        d = StallDetector(min_diff_ratio=0.05)
        d.record_revision(
            "rev-1",
            text="\n".join(f"line {i}" for i in range(20)),
            findings=["Missing error handling!"],
        )
        d.record_revision(
            "rev-2",
            text="\n".join(f"changed-line {i}" for i in range(20)),
            findings=["MISSING ERROR HANDLING"],
        )
        verdict = d.check()
        assert verdict.stalled is True

    def test_distinct_findings_not_stalled(self):
        d = StallDetector(min_diff_ratio=0.05)
        d.record_revision(
            "rev-1",
            text="\n".join(f"line {i}" for i in range(20)),
            findings=["First concern"],
        )
        d.record_revision(
            "rev-2",
            text="\n".join(f"changed-line {i}" for i in range(20)),
            findings=["Different concern"],
        )
        verdict = d.check()
        assert verdict.stalled is False

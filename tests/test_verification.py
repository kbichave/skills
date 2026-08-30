"""Tests for verification status and the needs-human handoff queue.

These two together are what let an autonomous run advance on green and halt
otherwise, instead of closing every checkpoint with "Auto mode: skipped".

The property that matters most: **an unverified section is not a passing one.**
Absence of evidence is the usual way an autonomous run convinces itself
everything is fine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import handoff
from lib.verification import (
    GAPS_FOUND,
    HUMAN_NEEDED,
    PASSED,
    classify,
    load,
    phase_status,
    record,
)


@pytest.fixture
def planning(tmp_path: Path) -> Path:
    (tmp_path / ".deepstate").mkdir()
    return tmp_path


class TestClassify:
    def test_clean_run_passes(self):
        assert classify(gates_passed=True) == PASSED

    def test_failed_gate_is_a_gap(self):
        assert classify(gates_passed=False) == GAPS_FOUND

    def test_blocking_finding_is_a_gap(self):
        assert classify(gates_passed=True, blocking_findings=1) == GAPS_FOUND

    def test_three_strikes_needs_a_human(self):
        """Three attempts at the same failure is not a gap to fix; it is a
        signal the run cannot get there alone."""
        assert classify(gates_passed=False, strikes=3) == HUMAN_NEEDED

    def test_strikes_outrank_a_passing_gate(self):
        assert classify(gates_passed=True, strikes=3) == HUMAN_NEEDED

    def test_two_strikes_is_still_only_a_gap(self):
        assert classify(gates_passed=False, strikes=2) == GAPS_FOUND


class TestRecording:
    def test_round_trips(self, planning):
        record(planning, section="s-01", gates_passed=True)
        assert [r.section for r in load(planning)] == ["s-01"]

    def test_rerecording_replaces(self, planning):
        """The latest result is the true one; a duplicated section in the
        summary reads as two separate failures."""
        record(planning, section="s-01", gates_passed=False)
        record(planning, section="s-01", gates_passed=True)
        results = load(planning)
        assert len(results) == 1 and results[0].status == PASSED

    def test_missing_file_is_empty(self, planning):
        assert load(planning) == []

    def test_malformed_file_is_empty(self, planning):
        (planning / ".deepstate" / "verification.json").write_text("{not json")
        assert load(planning) == []

    def test_unknown_status_on_disk_is_treated_as_human_needed(self, planning):
        (planning / ".deepstate" / "verification.json").write_text(
            '[{"section": "s", "status": "definitely-fine"}]'
        )
        assert load(planning)[0].status == HUMAN_NEEDED


class TestPhaseStatus:
    def test_all_green_can_advance(self, planning):
        record(planning, section="s-01", gates_passed=True)
        record(planning, section="s-02", gates_passed=True)
        assert phase_status(planning, expected_sections=2).can_advance is True

    def test_one_gap_blocks_the_phase(self, planning):
        """One broken section does not become acceptable by sitting next to
        nine good ones."""
        record(planning, section="s-01", gates_passed=True)
        record(planning, section="s-02", gates_passed=False)
        status = phase_status(planning, expected_sections=2)
        assert status.can_advance is False
        assert status.status == GAPS_FOUND

    def test_worst_status_wins(self, planning):
        record(planning, section="s-01", gates_passed=False)
        record(planning, section="s-02", gates_passed=False, strikes=3)
        assert phase_status(planning, expected_sections=2).status == HUMAN_NEEDED

    def test_unverified_section_blocks(self, planning):
        record(planning, section="s-01", gates_passed=True)
        status = phase_status(planning, expected_sections=3)
        assert status.can_advance is False
        assert "<unverified>" in status.failing

    def test_nothing_recorded_blocks(self, planning):
        assert phase_status(planning, expected_sections=2).can_advance is False

    def test_no_expectation_and_no_records_is_vacuously_passed(self, planning):
        """Callers that do not pass expected_sections get no unverified check;
        the CLI always passes it."""
        assert phase_status(planning).status == PASSED

    def test_reports_failing_sections(self, planning):
        record(planning, section="s-01", gates_passed=True)
        record(planning, section="s-02", gates_passed=False)
        assert phase_status(planning, expected_sections=2).failing == ("s-02",)

    def test_counts_passed(self, planning):
        record(planning, section="s-01", gates_passed=True)
        record(planning, section="s-02", gates_passed=False)
        assert phase_status(planning, expected_sections=2).passed == 1


class TestHandoffQueue:
    def test_records_and_loads(self, planning):
        handoff.record(planning, section="s-01", reason="three_strikes", attempts=3)
        items = handoff.load(planning)
        assert items[0].section == "s-01" and items[0].attempts == 3

    def test_unknown_reason_becomes_other(self, planning):
        handoff.record(planning, section="s", reason="because-i-said-so")
        assert handoff.load(planning)[0].reason == "other"

    def test_rerecording_replaces(self, planning):
        handoff.record(planning, section="s", reason="low_confidence")
        handoff.record(planning, section="s", reason="three_strikes")
        items = handoff.load(planning)
        assert len(items) == 1 and items[0].reason == "three_strikes"

    def test_clear_removes(self, planning):
        handoff.record(planning, section="s", reason="blocked")
        assert handoff.clear(planning, "s") is True
        assert handoff.load(planning) == []

    def test_clear_missing_is_false(self, planning):
        assert handoff.clear(planning, "nope") is False

    def test_empty_summary_is_explicit(self, planning):
        """Silence is indistinguishable from the feature not running."""
        assert "Nothing was skipped" in handoff.summary(planning)

    def test_summary_lists_sections(self, planning):
        handoff.record(planning, section="s-02", reason="gate_failed", detail="mypy")
        summary = handoff.summary(planning)
        assert "s-02" in summary and "gate_failed" in summary and "mypy" in summary

    def test_summary_escapes_pipes(self, planning):
        """A detail containing | would otherwise break the markdown table."""
        handoff.record(planning, section="s", reason="other", detail="a | b")
        assert "a \\| b" in handoff.summary(planning)

    def test_malformed_queue_is_empty(self, planning):
        handoff.handoff_path(planning).write_text("not json")
        assert handoff.load(planning) == []

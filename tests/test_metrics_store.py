"""Tests for the cross-session run store.

Two properties worth defending:
  1. Telemetry never fails a run. Every write path swallows its errors, and a
     corrupt line must not make the whole history unreadable.
  2. It refuses to present a baseline it does not have. Median-and-MAD over
     three runs is not a baseline, and labelling it one is how a monitoring
     system starts producing confident nonsense.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.metrics_store import (
    MAX_RECORD_BYTES,
    MIN_SAMPLES_FOR_BASELINE,
    append_run,
    build_record,
    compute_baseline,
    derive,
    load_runs,
    metric_values,
    prune,
    runs_path,
    summarize,
)


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "metrics"


def a_record(**overrides):
    metrics = {
        "started_at": "2026-08-30T14:00:00+00:00",
        "completed_at": "2026-08-30T14:10:00+00:00",
        "wall_clock_seconds": 600,
        "wave_count": 2,
        "agents_launched": 6,
        "research_gate_pass": 4,
        "research_gate_fail": 1,
    }
    metrics.update(overrides.pop("metrics", {}))
    kwargs = dict(
        run_id="run-1", project_slug="proj-abc", mode="plan", metrics=metrics
    )
    kwargs.update(overrides)
    return build_record(**kwargs)


class TestDerive:
    def test_computes_gate_pass_rate(self):
        assert derive({"research_gate_pass": 4, "research_gate_fail": 1}, 0)[
            "research_gate_pass_rate"
        ] == 0.8

    def test_omits_rate_with_zero_denominator(self):
        """'No gates ran' and 'every gate failed' must not look identical."""
        assert "research_gate_pass_rate" not in derive({}, 0)

    def test_agents_per_wave(self):
        assert derive({"wave_count": 2, "agents_launched": 7}, 0)["agents_per_wave"] == 3.5


class TestAppendAndLoad:
    def test_round_trips(self, store):
        assert append_run(a_record(), store) is True
        runs = load_runs(store)
        assert len(runs) == 1 and runs[0]["run_id"] == "run-1"

    def test_appends_accumulate(self, store):
        append_run(a_record(run_id="a"), store)
        append_run(a_record(run_id="b"), store)
        assert [r["run_id"] for r in load_runs(store)] == ["a", "b"]

    def test_missing_store_reads_empty(self, store):
        assert load_runs(store) == []

    def test_corrupt_line_is_skipped_not_fatal(self, store):
        """A half-written record from a killed process must not make the whole
        history unreadable."""
        append_run(a_record(run_id="good-1"), store)
        with runs_path(store).open("a") as handle:
            handle.write("{not json at all\n")
        append_run(a_record(run_id="good-2"), store)
        assert [r["run_id"] for r in load_runs(store)] == ["good-1", "good-2"]

    def test_blank_lines_ignored(self, store):
        append_run(a_record(), store)
        with runs_path(store).open("a") as handle:
            handle.write("\n\n")
        assert len(load_runs(store)) == 1

    def test_unwritable_store_returns_false_not_raises(self, tmp_path):
        blocker = tmp_path / "blocked"
        blocker.write_text("i am a file, not a directory")
        assert append_run(a_record(), blocker / "sub") is False

    def test_oversized_record_keeps_derived_drops_metrics(self, store):
        """Degrade to less detail, never to no record."""
        append_run(a_record(metrics={"junk": "x" * (MAX_RECORD_BYTES * 2)}), store)
        run = load_runs(store)[0]
        assert run["metrics"] == {}
        assert run["derived"]["agents_per_wave"] == 3.0


class TestFiltering:
    def test_by_project_slug(self, store):
        append_run(a_record(run_id="a", project_slug="one"), store)
        append_run(a_record(run_id="b", project_slug="two"), store)
        assert [r["run_id"] for r in load_runs(store, project_slug="two")] == ["b"]

    def test_by_mode(self, store):
        append_run(a_record(run_id="a", mode="plan"), store)
        append_run(a_record(run_id="b", mode="implement"), store)
        assert [r["run_id"] for r in load_runs(store, mode="implement")] == ["b"]


class TestBaseline:
    def _runs(self, values):
        return [{"derived": {"m": v}} for v in values]

    def test_uses_median_not_mean(self, store):
        """One disastrous run must not drag the centre; that is the whole
        reason for median and MAD over mean and standard deviation."""
        baseline = compute_baseline(self._runs([10, 10, 10, 10, 10, 10, 10, 1000]), "m")
        assert baseline.center == 10

    def test_reports_n(self):
        assert compute_baseline(self._runs([1, 2, 3]), "m").n == 3

    def test_untrustworthy_below_threshold(self):
        few = [1.0] * (MIN_SAMPLES_FOR_BASELINE - 1)
        assert compute_baseline(self._runs(few), "m").trustworthy is False

    def test_trustworthy_at_threshold(self):
        enough = [1.0] * MIN_SAMPLES_FOR_BASELINE
        assert compute_baseline(self._runs(enough), "m").trustworthy is True

    def test_empty_is_untrustworthy_not_an_error(self):
        baseline = compute_baseline([], "m")
        assert baseline.n == 0 and baseline.trustworthy is False

    def test_ignores_booleans(self, store):
        """bool is a subclass of int; True must not count as 1.0."""
        assert metric_values([{"derived": {"m": True}}], "m") == []

    def test_ignores_missing_metric(self):
        assert metric_values([{"derived": {"other": 1}}], "m") == []


class TestPrune:
    def test_drops_oldest_beyond_max_records(self, store):
        for i in range(10):
            append_run(a_record(run_id=f"r{i}"), store)
        assert prune(store, max_records=4, max_age_days=0) == 6
        assert [r["run_id"] for r in load_runs(store)] == ["r6", "r7", "r8", "r9"]

    def test_noop_when_under_limits(self, store):
        append_run(a_record(), store)
        assert prune(store, max_records=100) == 0

    def test_empty_store_is_noop(self, store):
        assert prune(store) == 0

    def test_undated_records_are_kept(self, store):
        """Dropping records we cannot date would silently lose history."""
        append_run(a_record(metrics={"completed_at": ""}), store)
        assert prune(store, max_records=500, max_age_days=0) == 0


class TestSummarize:
    def test_counts_by_mode_and_outcome(self, store):
        append_run(a_record(run_id="a", mode="plan"), store)
        append_run(a_record(run_id="b", mode="plan"), store)
        append_run(a_record(run_id="c", mode="implement", outcome="error"), store)
        result = summarize(load_runs(store))
        assert result["runs"] == 3
        assert result["by_mode"] == {"plan": 2, "implement": 1}
        assert result["by_outcome"]["error"] == 1

    def test_median_wall_clock(self, store):
        for seconds in (100, 200, 300):
            append_run(
                a_record(run_id=str(seconds), metrics={"wall_clock_seconds": seconds}),
                store,
            )
        assert summarize(load_runs(store))["median_wall_clock_seconds"] == 200.0

    def test_empty_has_no_median(self):
        assert summarize([])["median_wall_clock_seconds"] is None


class TestPrivacy:
    def test_record_carries_no_free_text(self, store):
        """Counts, rates, timestamps and identifiers only — that is what keeps
        the privacy story short enough to hold."""
        append_run(a_record(), store)
        raw = runs_path(store).read_text()
        record = json.loads(raw)
        assert set(record) == {
            "schema",
            "run_id",
            "project_slug",
            "mode",
            "started_at",
            "completed_at",
            "wall_clock_seconds",
            "outcome",
            "plugin_version",
            "metrics",
            "derived",
        }

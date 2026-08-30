"""Tests for MetricsCollector — session metrics collection and dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib.deepstate import MetricsCollector


@pytest.fixture
def state_dir(tmp_path):
    d = tmp_path / ".deepstate"
    d.mkdir()
    return d


@pytest.fixture
def collector(state_dir):
    return MetricsCollector(state_dir=state_dir)


class TestMetricsCollector:
    def test_creates_metrics_file(self, collector, state_dir):
        assert (state_dir / "metrics.json").exists()

    def test_default_values(self, collector):
        data = json.loads(collector.metrics_file.read_text())
        assert data["wave_count"] == 0
        assert data["agents_launched"] == 0
        assert data["completed_at"] is None

    def test_record_sets_value(self, collector):
        collector.record("wave_count", 3)
        data = json.loads(collector.metrics_file.read_text())
        assert data["wave_count"] == 3

    def test_increment_adds(self, collector):
        collector.increment("agents_launched", 5)
        collector.increment("agents_launched", 3)
        data = json.loads(collector.metrics_file.read_text())
        assert data["agents_launched"] == 8

    def test_increment_default_amount(self, collector):
        collector.increment("section_rewrite_count")
        collector.increment("section_rewrite_count")
        data = json.loads(collector.metrics_file.read_text())
        assert data["section_rewrite_count"] == 2

    def test_finalize_sets_completed_at(self, collector):
        result = collector.finalize()
        assert result["completed_at"] is not None
        assert result["wall_clock_seconds"] is not None
        assert result["wall_clock_seconds"] >= 0

    def test_finalize_persists(self, collector, state_dir):
        collector.finalize()
        data = json.loads((state_dir / "metrics.json").read_text())
        assert data["completed_at"] is not None

    def test_atomic_write(self, collector, state_dir):
        """Verify tmp file is cleaned up after write."""
        collector.record("wave_count", 1)
        assert not (state_dir / "metrics.json.tmp").exists()

    def test_reload_existing(self, state_dir):
        """Creating a new collector loads existing metrics."""
        c1 = MetricsCollector(state_dir=state_dir)
        c1.record("wave_count", 5)
        c2 = MetricsCollector(state_dir=state_dir)
        assert c2._data["wave_count"] == 5

    def test_format_dashboard(self, collector):
        collector.record("wave_count", 2)
        collector.record("agents_launched", 11)
        collector.record("research_gate_pass", 12)
        collector.record("research_gate_fail", 3)
        collector.finalize()
        dashboard = collector.format_dashboard()
        assert "## Session Metrics" in dashboard
        assert "Research waves | 2" in dashboard
        assert "Agents launched | 11" in dashboard
        assert "12/15 passed" in dashboard

    def test_format_dashboard_no_gates(self, collector):
        collector.finalize()
        dashboard = collector.format_dashboard()
        assert "N/A" in dashboard

    def test_sub_minute_session_reports_zero_not_na(self, collector):
        """A session that finalizes in under a second measured 0s; it is not
        the same as a session that never finalized."""
        collector.finalize()
        assert "| Wall clock time | 0m 0s |" in collector.format_dashboard()

    def test_unfinalized_session_reports_na(self, collector):
        assert "| Wall clock time | N/A |" in collector.format_dashboard()

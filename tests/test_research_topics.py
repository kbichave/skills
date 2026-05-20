"""Tests for scripts/lib/research_topics.py — ResearchTopicStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Adjust sys.path so lib is importable from tests/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.research_topics import FlatFileBackend, ResearchTopicStore


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def planning_dir(tmp_path):
    d = tmp_path / "planning"
    d.mkdir()
    return d


@pytest.fixture
def store(planning_dir):
    return FlatFileBackend(planning_dir=planning_dir)


def _make_topic(store: FlatFileBackend, id: str = "rt-01", topic: str = "Auth", **kwargs) -> None:
    store.create_topic(
        id=id,
        topic=topic,
        category=kwargs.get("category", "security"),
        priority=kwargs.get("priority", "high"),
        questions=kwargs.get("questions", ["Q1", "Q2"]),
    )


# ── FlatFileBackend.create_topic ─────────────────────────────────────────────


class TestCreateTopic:
    def test_creates_topics_file(self, store, planning_dir):
        _make_topic(store)
        assert (planning_dir / "research-topics.yaml").exists()

    def test_topic_has_pending_status(self, store):
        _make_topic(store)
        topics = store.get_all()
        assert topics[0]["status"] == "pending"

    def test_topic_fields_persisted(self, store):
        store.create_topic("rt-01", "Auth & Authz", "security", "high", ["Q1"])
        t = store.get_all()[0]
        assert t["id"] == "rt-01"
        assert t["topic"] == "Auth & Authz"
        assert t["category"] == "security"
        assert t["priority"] == "high"
        assert t["questions"] == ["Q1"]
        assert t["findings_file"] is None

    def test_idempotent_create(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-01")
        assert len(store.get_all()) == 1

    def test_metadata_total_updated(self, store, planning_dir):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        import yaml
        data = yaml.safe_load((planning_dir / "research-topics.yaml").read_text())
        assert data["metadata"]["total"] == 2

    def test_multiple_topics_stored(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02", topic="Observability", category="observability")
        topics = store.get_all()
        assert len(topics) == 2
        ids = {t["id"] for t in topics}
        assert ids == {"rt-01", "rt-02"}


# ── FlatFileBackend.set_status ────────────────────────────────────────────────


class TestSetStatus:
    def test_set_covered(self, store):
        _make_topic(store)
        store.set_status("rt-01", "covered", findings_file="findings/rt-01-auth.md")
        t = store.get_all()[0]
        assert t["status"] == "covered"
        assert t["findings_file"] == "findings/rt-01-auth.md"

    def test_set_skipped(self, store):
        _make_topic(store)
        store.set_status("rt-01", "skipped")
        assert store.get_all()[0]["status"] == "skipped"

    def test_findings_file_not_overwritten_when_none(self, store):
        _make_topic(store)
        store.set_status("rt-01", "covered", findings_file="findings/rt-01.md")
        store.set_status("rt-01", "covered", findings_file=None)
        # findings_file should remain unchanged when None is passed
        t = store.get_all()[0]
        assert t["findings_file"] == "findings/rt-01.md"

    def test_metadata_coverage_pct_recomputed(self, store, planning_dir):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        store.set_status("rt-01", "covered")
        import yaml
        data = yaml.safe_load((planning_dir / "research-topics.yaml").read_text())
        assert data["metadata"]["coverage_pct"] == 50.0
        assert data["metadata"]["covered"] == 1

    def test_skipped_excluded_from_denominator(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        store.set_status("rt-01", "skipped")
        store.set_status("rt-02", "covered")
        # Only 1 researchable (rt-02); rt-02 is covered → 100%
        assert store.coverage_pct() == 100.0

    def test_unknown_id_is_noop(self, store):
        _make_topic(store)
        store.set_status("rt-99", "covered")  # No such ID — should not raise
        assert store.get_all()[0]["status"] == "pending"


# ── FlatFileBackend.get_missing ───────────────────────────────────────────────


class TestGetMissing:
    def test_all_pending_are_missing(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        missing = store.get_missing()
        assert len(missing) == 2

    def test_covered_not_missing(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        store.set_status("rt-01", "covered")
        missing = store.get_missing()
        assert len(missing) == 1
        assert missing[0]["id"] == "rt-02"

    def test_skipped_not_missing(self, store):
        _make_topic(store, id="rt-01")
        store.set_status("rt-01", "skipped")
        assert store.get_missing() == []

    def test_empty_store_returns_empty(self, store):
        assert store.get_missing() == []


# ── FlatFileBackend.coverage_pct ─────────────────────────────────────────────


class TestCoveragePct:
    def test_zero_topics_is_100(self, store):
        assert store.coverage_pct() == 100.0

    def test_all_pending_is_zero(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        assert store.coverage_pct() == 0.0

    def test_half_covered(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        store.set_status("rt-01", "covered")
        assert store.coverage_pct() == 50.0

    def test_all_covered_is_100(self, store):
        _make_topic(store, id="rt-01")
        _make_topic(store, id="rt-02")
        store.set_status("rt-01", "covered")
        store.set_status("rt-02", "covered")
        assert store.coverage_pct() == 100.0

    def test_all_skipped_is_100(self, store):
        _make_topic(store, id="rt-01")
        store.set_status("rt-01", "skipped")
        assert store.coverage_pct() == 100.0

    def test_rounding_to_one_decimal(self, store):
        for i in range(3):
            _make_topic(store, id=f"rt-0{i+1}", topic=f"Topic {i}")
        store.set_status("rt-01", "covered")
        # 1/3 = 33.3%
        assert store.coverage_pct() == 33.3


# ── ResearchTopicStore.create factory ────────────────────────────────────────


class TestFactory:
    def test_returns_flatfile(self, planning_dir):
        store = ResearchTopicStore.create(planning_dir=planning_dir, project_slug="test-a1b2c3")
        assert isinstance(store, FlatFileBackend)

    def test_flatfile_uses_correct_planning_dir(self, planning_dir):
        store = ResearchTopicStore.create(planning_dir=planning_dir, project_slug="test-a1b2c3")
        assert store.planning_dir == planning_dir


# ── search_prior (base class default) ────────────────────────────────────────


class TestSearchPrior:
    def test_flatfile_search_prior_returns_empty(self, store):
        assert store.search_prior("oauth JWT security") == []

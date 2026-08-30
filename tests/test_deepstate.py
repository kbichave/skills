"""Tests for DeepStateTracker — pure Python dependency tracker."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from lib.deepstate import DeepStateTracker


@pytest.fixture
def tracker(tmp_path: Path) -> DeepStateTracker:
    """Create a tracker with a temp .deepstate/ directory."""
    state_dir = tmp_path / ".deepstate"
    t = DeepStateTracker(state_dir=state_dir)
    t.init("test-epic", {"planning_dir": str(tmp_path)})
    return t


class TestInit:
    def test_creates_directory_and_state_json(self, tmp_path):
        state_dir = tmp_path / ".deepstate"
        t = DeepStateTracker(state_dir=state_dir)
        t.init("my-epic", {"key": "val"})
        assert state_dir.is_dir()
        assert (state_dir / "state.json").exists()

    def test_stores_epic_metadata(self, tmp_path):
        state_dir = tmp_path / ".deepstate"
        t = DeepStateTracker(state_dir=state_dir)
        t.init("my-epic", {"planning_dir": "/tmp/test"})
        state = json.loads((state_dir / "state.json").read_text())
        assert state["epic"]["title"] == "my-epic"
        assert state["epic"]["context"]["planning_dir"] == "/tmp/test"
        assert state["issues"] == {}

    def test_raises_if_already_initialized(self, tracker):
        with pytest.raises(FileExistsError):
            tracker.init("another-epic", {})

    def test_state_json_is_valid_json(self, tracker):
        state = json.loads((tracker.state_dir / "state.json").read_text())
        assert "epic" in state
        assert "issues" in state


class TestCreate:
    def test_adds_issue_with_open_status(self, tracker):
        result = tracker.create("step-01", "First Step")
        assert result["status"] == "open"
        assert result["title"] == "First Step"

    def test_stamps_created_at_and_leaves_closed_at_unset(self, tracker):
        result = tracker.create("step-01", "First Step")
        assert datetime.fromisoformat(result["created_at"]).tzinfo is not None
        assert result["closed_at"] is None

    def test_stores_depends_on(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.create("step-02", "Second", depends_on=["step-01"])
        assert result["depends_on"] == ["step-01"]

    def test_no_depends_on_defaults_empty(self, tracker):
        result = tracker.create("step-01", "First")
        assert result["depends_on"] == []

    def test_returns_issue_dict_with_id(self, tracker):
        result = tracker.create("step-01", "First")
        assert result["id"] == "step-01"
        assert "title" in result
        assert "status" in result
        assert "depends_on" in result

    def test_duplicate_id_raises(self, tracker):
        tracker.create("step-01", "First")
        with pytest.raises(ValueError, match="already exists"):
            tracker.create("step-01", "Duplicate")

    def test_invalid_dependency_raises(self, tracker):
        with pytest.raises(ValueError, match="does not exist"):
            tracker.create("step-02", "Second", depends_on=["nonexistent"])

    def test_stores_description(self, tracker):
        result = tracker.create("step-01", "First", description="Do the thing")
        assert result["description"] == "Do the thing"


class TestReady:
    def test_returns_open_issues_with_all_deps_closed(self, tracker):
        tracker.create("step-01", "First")
        tracker.create("step-02", "Second", depends_on=["step-01"])
        tracker.close("step-01", "done")
        ready = tracker.ready()
        assert len(ready) == 1
        assert ready[0]["id"] == "step-02"

    def test_excludes_issues_with_open_deps(self, tracker):
        tracker.create("step-01", "First")
        tracker.create("step-02", "Second", depends_on=["step-01"])
        ready = tracker.ready()
        ids = [i["id"] for i in ready]
        assert "step-02" not in ids
        assert "step-01" in ids

    def test_returns_empty_when_all_closed(self, tracker):
        tracker.create("step-01", "First")
        tracker.close("step-01", "done")
        assert tracker.ready() == []

    def test_returns_issues_with_no_deps_immediately(self, tracker):
        tracker.create("step-01", "First")
        tracker.create("step-02", "Second")
        ready = tracker.ready()
        ids = {i["id"] for i in ready}
        assert ids == {"step-01", "step-02"}

    def test_returns_multiple_unblocked(self, tracker):
        tracker.create("root", "Root")
        tracker.create("a", "A", depends_on=["root"])
        tracker.create("b", "B", depends_on=["root"])
        tracker.close("root", "done")
        ready = tracker.ready()
        ids = {i["id"] for i in ready}
        assert ids == {"a", "b"}

    def test_does_not_return_closed_issues(self, tracker):
        tracker.create("step-01", "First")
        tracker.close("step-01", "done")
        ready = tracker.ready()
        assert all(i["status"] == "open" for i in ready)


class TestClose:
    def test_sets_status_closed_and_stores_reason(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.close("step-01", "completed successfully")
        assert result["status"] == "closed"
        assert result["closed_reason"] == "completed successfully"

    def test_already_closed_raises(self, tracker):
        tracker.create("step-01", "First")
        tracker.close("step-01", "done")
        with pytest.raises(ValueError, match="already closed"):
            tracker.close("step-01", "again")

    def test_nonexistent_raises(self, tracker):
        with pytest.raises(KeyError):
            tracker.close("nope", "reason")

    def test_stamps_closed_at(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.close("step-01", "done")
        assert result["closed_at"] is not None
        assert datetime.fromisoformat(result["closed_at"]).tzinfo is not None

    def test_closed_at_is_after_created_at(self, tracker):
        created = tracker.create("step-01", "First")
        closed = tracker.close("step-01", "done")
        assert datetime.fromisoformat(closed["closed_at"]) >= datetime.fromisoformat(
            created["created_at"]
        )

    def test_returns_updated_dict(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.close("step-01", "reason")
        assert result["id"] == "step-01"
        assert result["status"] == "closed"

    def test_closing_dep_unblocks_dependents(self, tracker):
        tracker.create("step-01", "First")
        tracker.create("step-02", "Second", depends_on=["step-01"])
        assert tracker.ready()[0]["id"] == "step-01"
        tracker.close("step-01", "done")
        assert tracker.ready()[0]["id"] == "step-02"


class TestShow:
    def test_returns_full_issue(self, tracker):
        tracker.create("step-01", "First", description="desc")
        result = tracker.show("step-01")
        assert result["id"] == "step-01"
        assert result["title"] == "First"
        assert result["description"] == "desc"

    def test_nonexistent_raises(self, tracker):
        with pytest.raises(KeyError):
            tracker.show("nope")


class TestUpdate:
    def test_changes_description(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.update("step-01", description="new desc")
        assert result["description"] == "new desc"

    def test_changes_status(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.update("step-01", status="closed")
        assert result["status"] == "closed"

    def test_no_kwargs_is_noop(self, tracker):
        tracker.create("step-01", "First", description="orig")
        result = tracker.update("step-01")
        assert result["description"] == "orig"

    def test_nonexistent_raises(self, tracker):
        with pytest.raises(KeyError):
            tracker.update("nope", description="x")


class TestListIssues:
    def test_returns_all_when_no_filter(self, tracker):
        tracker.create("a", "A")
        tracker.create("b", "B")
        assert len(tracker.list_issues()) == 2

    def test_filters_by_open(self, tracker):
        tracker.create("a", "A")
        tracker.create("b", "B")
        tracker.close("a", "done")
        open_issues = tracker.list_issues(status="open")
        assert len(open_issues) == 1
        assert open_issues[0]["id"] == "b"

    def test_filters_by_closed(self, tracker):
        tracker.create("a", "A")
        tracker.create("b", "B")
        tracker.close("a", "done")
        closed = tracker.list_issues(status="closed")
        assert len(closed) == 1
        assert closed[0]["id"] == "a"

    def test_empty_when_no_issues(self, tracker):
        assert tracker.list_issues() == []


class TestPrime:
    def test_returns_summary_string(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.prime()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_epic_title(self, tracker):
        tracker.create("step-01", "First")
        result = tracker.prime()
        assert "test-epic" in result

    def test_includes_counts(self, tracker):
        tracker.create("a", "A")
        tracker.create("b", "B")
        tracker.close("a", "done")
        result = tracker.prime()
        assert "1" in result  # 1 closed
        assert "2" in result  # 2 total

    def test_writes_prime_md(self, tracker):
        tracker.create("step-01", "First")
        tracker.prime()
        assert (tracker.state_dir / "prime.md").exists()


class TestDepTree:
    def test_issue_with_no_deps(self, tracker):
        tracker.create("step-01", "First")
        tree = tracker.dep_tree("step-01")
        assert "step-01" in tree

    def test_shows_dependency_chain(self, tracker):
        tracker.create("step-01", "First")
        tracker.create("step-02", "Second", depends_on=["step-01"])
        tree = tracker.dep_tree("step-02")
        assert "step-01" in tree
        assert "step-02" in tree

    def test_shows_status_indicators(self, tracker):
        tracker.create("step-01", "First")
        tracker.create("step-02", "Second", depends_on=["step-01"])
        tracker.close("step-01", "done")
        tree = tracker.dep_tree("step-02")
        assert "[x]" in tree  # closed dep
        assert "[ ]" in tree  # open issue

    def test_nonexistent_raises(self, tracker):
        with pytest.raises(KeyError):
            tracker.dep_tree("nope")


class TestAtomicWrites:
    def test_save_uses_tmp_rename(self, tracker, tmp_path):
        tracker.create("step-01", "First")
        state_file = tracker.state_dir / "state.json"
        assert state_file.exists()
        # Verify no .tmp file left behind
        assert not (tracker.state_dir / "state.json.tmp").exists()

    def test_load_after_save_roundtrips(self, tracker):
        tracker.create("step-01", "First")
        state = tracker._load()
        assert "step-01" in state["issues"]

    def test_load_missing_raises(self, tmp_path):
        t = DeepStateTracker(state_dir=tmp_path / "empty")
        with pytest.raises(FileNotFoundError):
            t._load()

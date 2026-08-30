"""Tests for the test-file lock.

The property it exists to create: "all tests pass" is only evidence if the agent
could not have edited the test. So the lock is a deny, not an ask.

The property that keeps it from being ripped out: it blocks only the files it
explicitly names, and a human can always release it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.fix_lock import (
    FixLock,
    add_protected,
    close_lock,
    decide,
    is_test_path,
    lock_path,
    open_lock,
    override,
    read_lock,
    write_lock,
)


@pytest.fixture
def planning(tmp_path: Path) -> Path:
    (tmp_path / ".deepstate").mkdir()
    return tmp_path


class TestIsTestPath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("tests/test_client.py", True),
            ("test/test_client.py", True),
            ("src/test_helpers.py", True),
            ("pkg/client_test.go", True),
            ("src/App.test.tsx", True),
            ("src/App.spec.ts", True),
            ("conftest.py", True),
            ("src/client.py", False),
            ("src/contest.py", False),
            ("docs/testing.md", False),
        ],
    )
    def test_classification(self, path, expected):
        assert is_test_path(path) is expected


class TestLockLifecycle:
    def test_open_then_read(self, planning):
        open_lock(planning, section_id="s-04", protected=["tests/test_a.py"])
        lock = read_lock(planning)
        assert lock.active is True
        assert lock.protected == ("tests/test_a.py",)
        assert lock.section_id == "s-04"

    def test_open_records_a_timestamp(self, planning):
        assert open_lock(planning, section_id="s", protected=["tests/t.py"]).opened_at

    def test_close_deactivates(self, planning):
        open_lock(planning, section_id="s", protected=["tests/t.py"])
        close_lock(planning)
        assert read_lock(planning).active is False

    def test_add_widens_without_duplicating(self, planning):
        open_lock(planning, section_id="s", protected=["tests/a.py"])
        lock = add_protected(planning, ["tests/b.py", "tests/a.py"])
        assert lock.protected == ("tests/a.py", "tests/b.py")

    def test_override_requires_and_records_a_reason(self, planning):
        open_lock(planning, section_id="s", protected=["tests/a.py"])
        lock = override(planning, "the test asserted the wrong currency")
        assert lock.active is False
        assert lock.override_reason == "the test asserted the wrong currency"

    def test_override_is_visible_on_disk(self, planning):
        """An override that leaves no trace is indistinguishable from never
        having locked."""
        open_lock(planning, section_id="s", protected=["tests/a.py"])
        override(planning, "bad assertion")
        assert "bad assertion" in lock_path(planning).read_text()


class TestReadIsForgiving:
    def test_missing_file_is_no_lock(self, planning):
        assert read_lock(planning).active is False

    def test_malformed_json_is_no_lock(self, planning):
        lock_path(planning).write_text("{not json")
        assert read_lock(planning).active is False

    def test_non_dict_json_is_no_lock(self, planning):
        lock_path(planning).write_text("[1, 2, 3]")
        assert read_lock(planning).active is False

    def test_junk_entries_are_dropped(self, planning):
        lock_path(planning).write_text(
            json.dumps({"active": True, "protected": ["tests/a.py", 42, None]})
        )
        assert read_lock(planning).protected == ("tests/a.py",)


class TestDecide:
    def test_blocks_a_protected_test(self):
        lock = FixLock(active=True, protected=("tests/test_a.py",), section_id="s-04")
        assert decide("tests/test_a.py", lock).blocked is True

    def test_allows_an_unprotected_test(self):
        """Only files the lock names. Blocking every test-shaped path is how the
        feature gets switched off."""
        lock = FixLock(active=True, protected=("tests/test_a.py",))
        assert decide("tests/test_b.py", lock).blocked is False

    def test_allows_source_files(self):
        lock = FixLock(active=True, protected=("tests/test_a.py",))
        assert decide("src/client.py", lock).blocked is False

    def test_inactive_lock_blocks_nothing(self):
        lock = FixLock(active=False, protected=("tests/test_a.py",))
        assert decide("tests/test_a.py", lock).blocked is False

    def test_env_kill_switch(self, monkeypatch):
        monkeypatch.setenv("DEEP_FIX_LOCK", "off")
        lock = FixLock(active=True, protected=("tests/test_a.py",))
        assert decide("tests/test_a.py", lock).blocked is False

    def test_message_names_the_escape_hatches(self):
        lock = FixLock(active=True, protected=("tests/test_a.py",), section_id="s-04")
        reason = decide("tests/test_a.py", lock).reason
        assert "fix-lock.py override" in reason
        assert "DEEP_FIX_LOCK=off" in reason

    def test_message_says_to_change_the_code(self):
        lock = FixLock(active=True, protected=("tests/test_a.py",))
        assert "Change the code instead" in decide("tests/test_a.py", lock).reason


class TestWriteFailure:
    def test_write_to_unwritable_path_returns_false(self, tmp_path):
        blocker = tmp_path / "blocked"
        blocker.write_text("not a directory")
        assert write_lock(blocker / "sub", FixLock(active=True)) is False

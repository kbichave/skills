"""Tests for implement-hook session binding.

These exist because the binding failed silently for months. Nothing wrote the
per-session marker the hooks looked for, so they fell through to "most recently
modified marker", those pointed at deleted directories, and the resolver
returned None. A hook that gets None does nothing — which meant `impl-stop`'s
"you must write an implementation summary" gate was never enforced.

The regression is invisible by construction: no error, no log, just a hook that
quietly stops working. So the tests assert the resolution ORDER and that a stale
marker can never win.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.session_paths import (
    active_marker,
    find_planning_dir,
    marker_dir,
    marker_path,
    session_id_from_payload,
    write_marker,
)


@pytest.fixture
def live_dir(tmp_path: Path) -> Path:
    d = tmp_path / "planning"
    d.mkdir()
    return d


@pytest.fixture
def dead_dir(tmp_path: Path) -> Path:
    return tmp_path / "deleted-session"


class TestMarkerWriting:
    def test_write_then_find(self, live_dir):
        assert write_marker("sess-1", live_dir) is True
        assert find_planning_dir("sess-1") == live_dir

    def test_empty_session_id_is_refused(self, live_dir):
        assert write_marker("", live_dir) is False

    def test_marker_lands_in_the_marker_dir(self, live_dir):
        write_marker("sess-1", live_dir)
        assert marker_path("sess-1").parent == marker_dir()


class TestResolutionOrder:
    def test_payload_session_id_wins_over_env(self, tmp_path, monkeypatch):
        payload_dir = tmp_path / "payload"
        env_dir = tmp_path / "env"
        payload_dir.mkdir()
        env_dir.mkdir()
        write_marker("from-payload", payload_dir)
        write_marker("from-env", env_dir)
        monkeypatch.setenv("DEEP_SESSION_ID", "from-env")

        assert find_planning_dir("from-payload") == payload_dir

    def test_env_used_when_no_payload_id(self, live_dir, monkeypatch):
        write_marker("from-env", live_dir)
        monkeypatch.setenv("DEEP_SESSION_ID", "from-env")
        assert find_planning_dir(None) == live_dir

    def test_active_marker_is_the_fallback(self, live_dir):
        """`.deep-plan-active` is written on every new session, so it is the
        one file that is reliably maintained."""
        active_marker().parent.mkdir(parents=True, exist_ok=True)
        active_marker().write_text(str(live_dir))
        assert find_planning_dir("no-such-session") == live_dir

    def test_returns_none_when_nothing_is_known(self):
        assert find_planning_dir("no-such-session") is None


class TestStaleMarkersNeverWin:
    def test_marker_pointing_at_deleted_dir_is_skipped(self, dead_dir):
        write_marker("sess-dead", dead_dir)
        assert find_planning_dir("sess-dead") is None

    def test_falls_through_stale_to_a_live_marker(self, live_dir, dead_dir):
        write_marker("sess-dead", dead_dir)
        write_marker("sess-live", live_dir)
        assert find_planning_dir(None) == live_dir

    def test_stale_active_marker_is_skipped(self, live_dir, dead_dir):
        active_marker().parent.mkdir(parents=True, exist_ok=True)
        active_marker().write_text(str(dead_dir))
        write_marker("sess-live", live_dir)
        assert find_planning_dir(None) == live_dir

    def test_unreadable_marker_does_not_raise(self, live_dir):
        marker_dir().mkdir(parents=True, exist_ok=True)
        (marker_dir() / "broken.marker").write_bytes(b"\xff\xfe not a path")
        write_marker("sess-live", live_dir)
        assert find_planning_dir(None) == live_dir


class TestPayloadParsing:
    def test_extracts_session_id(self):
        assert session_id_from_payload({"session_id": "abc"}) == "abc"

    def test_absent_key_is_none(self):
        assert session_id_from_payload({}) is None

    def test_empty_value_is_none(self):
        assert session_id_from_payload({"session_id": ""}) is None


class TestIsolation:
    def test_state_home_override_is_honoured(self, tmp_path, monkeypatch):
        """The suite must never write markers into the developer's real home;
        a marker from one test could otherwise decide another test's answer."""
        monkeypatch.setenv("DEEP_STATE_HOME", str(tmp_path / "elsewhere"))
        assert str(tmp_path / "elsewhere") in str(marker_dir())

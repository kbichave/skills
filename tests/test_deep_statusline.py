"""Tests for ``scripts/hooks/deep-statusline.py``."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUSLINE_PATH = REPO_ROOT / "scripts" / "hooks" / "deep-statusline.py"


@pytest.fixture
def statusline_module():
    spec = importlib.util.spec_from_file_location(
        "deep_statusline", STATUSLINE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestRenderBar:
    def test_zero(self, statusline_module) -> None:
        assert statusline_module.render_bar(0.0) == "▱" * 10

    def test_full(self, statusline_module) -> None:
        assert statusline_module.render_bar(100.0) == "▰" * 10

    def test_half(self, statusline_module) -> None:
        bar = statusline_module.render_bar(50.0)
        assert bar.count("▰") == 5
        assert bar.count("▱") == 5

    def test_clamped_high(self, statusline_module) -> None:
        assert statusline_module.render_bar(999.0) == "▰" * 10

    def test_clamped_low(self, statusline_module) -> None:
        assert statusline_module.render_bar(-50.0) == "▱" * 10


class TestRenderLine:
    def test_no_step_no_mode_uses_ctx_prefix(self, statusline_module) -> None:
        state = statusline_module.BridgeState(
            session_id="s",
            model_id="claude-opus-4-7",
            model_display="Opus 4.7",
            context_window_size=1_000_000,
            used_input_tokens=100_000,
            used_percentage=10.0,
            level="normal",
            current_step_id=None,
            current_step_title=None,
            planning_dir=None,
            mode=None,
            last_emitted_level=None,
            tool_calls_since_emit=0,
            ts=0.0,
        )
        line = statusline_module.render_line(state)
        assert line.startswith("ctx ")
        assert "10%" in line
        assert "opus" in line.lower()

    def test_with_active_step_uses_deep_prefix(self, statusline_module) -> None:
        state = statusline_module.BridgeState(
            session_id="s",
            model_id="claude-opus-4-7",
            model_display="Opus 4.7",
            context_window_size=1_000_000,
            used_input_tokens=620_000,
            used_percentage=62.0,
            level="normal",
            current_step_id="detailed-interview",
            current_step_title="Detailed Interview",
            planning_dir="/tmp/p",
            mode="plan",
            last_emitted_level=None,
            tool_calls_since_emit=0,
            ts=0.0,
        )
        line = statusline_module.render_line(state)
        assert line.startswith("deep:plan ")
        assert "detailed-interview" in line
        assert "62%" in line


class TestMainEntrypoint:
    def _run(self, statusline_module, payload: dict, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        captured: list[str] = []
        monkeypatch.setattr(
            "builtins.print", lambda *a, **k: captured.append(" ".join(str(x) for x in a))
        )
        # Point the marker lookup at an empty home so no real session on the
        # developer's machine can decide what this test renders.
        monkeypatch.setenv("DEEP_STATE_HOME", str(tmp_path / "home"))
        rc = statusline_module.main()
        return rc, captured

    def test_null_current_usage_renders_dashes(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        payload = {
            "session_id": "abc",
            "model": {"id": "claude-opus-4-7", "display_name": "Opus 4.7"},
            "context_window": {
                "context_window_size": 1_000_000,
                "current_usage": None,
            },
        }
        rc, out = self._run(statusline_module, payload, monkeypatch, tmp_path)
        assert rc == 0
        assert any("--%" in line for line in out)

    def test_bad_stdin_silent(self, statusline_module, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
        captured: list[str] = []
        monkeypatch.setattr(
            "builtins.print", lambda *a, **k: captured.append(" ".join(str(x) for x in a))
        )
        assert statusline_module.main() == 0
        assert captured == []

    def test_writes_bridge_with_usage(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        from lib import context_metrics as cm

        bridge_dir = tmp_path / "tmp"
        bridge_dir.mkdir()
        target = bridge_dir / "deep-ctx-sess1.json"

        def fake_bridge_path(session_id, tmp_dir=None):
            return target

        monkeypatch.setattr(statusline_module, "bridge_path", fake_bridge_path)
        monkeypatch.setattr(cm, "bridge_path", fake_bridge_path)
        monkeypatch.setenv("DEEP_STATE_HOME", str(tmp_path / "home"))

        payload = {
            "session_id": "sess1",
            "model": {"id": "claude-opus-4-7", "display_name": "Opus 4.7"},
            "context_window": {
                "context_window_size": 1_000_000,
                "used_percentage": 72.3,
                "current_usage": {
                    "input_tokens": 600_000,
                    "cache_creation_input_tokens": 100_000,
                    "cache_read_input_tokens": 23_000,
                    "output_tokens": 50_000,
                },
            },
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr("builtins.print", lambda *a, **k: None)

        assert statusline_module.main() == 0
        assert target.exists()
        data = json.loads(target.read_text())
        assert data["session_id"] == "sess1"
        assert data["used_percentage"] == 72.3
        assert data["level"] == "warning"
        assert data["used_input_tokens"] == 723_000


class TestResolvePlanningDir:
    """The status line shows this session's run or nothing at all.

    It used to read `~/.claude/.deep-plan-active`, which is one file for the
    machine and is never cleared, so every session on the box displayed
    whichever project ran `/deep` last.
    """

    def home(self, monkeypatch, tmp_path: Path) -> Path:
        state_home = tmp_path / "home"
        (state_home / ".deep-implement-sessions").mkdir(parents=True)
        monkeypatch.setenv("DEEP_STATE_HOME", str(state_home))
        monkeypatch.delenv("DEEP_SESSION_ID", raising=False)
        return state_home

    def test_no_marker_returns_none(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        self.home(monkeypatch, tmp_path)
        assert statusline_module.resolve_planning_dir("sess1") is None

    def test_the_session_marker_resolves(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        state_home = self.home(monkeypatch, tmp_path)
        planning = tmp_path / "pd"
        planning.mkdir()
        (state_home / ".deep-implement-sessions" / "sess1.marker").write_text(
            str(planning) + "\n"
        )
        assert statusline_module.resolve_planning_dir("sess1") == planning

    def test_a_marker_pointing_at_a_deleted_dir_returns_none(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        state_home = self.home(monkeypatch, tmp_path)
        (state_home / ".deep-implement-sessions" / "sess1.marker").write_text(
            "/no/such/dir\n"
        )
        assert statusline_module.resolve_planning_dir("sess1") is None

    def test_another_sessions_marker_is_not_borrowed(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        state_home = self.home(monkeypatch, tmp_path)
        planning = tmp_path / "someone-elses"
        planning.mkdir()
        (state_home / ".deep-implement-sessions" / "other.marker").write_text(
            str(planning)
        )
        assert statusline_module.resolve_planning_dir("sess1") is None

    def test_the_machine_wide_pointer_is_not_consulted(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        # The shipped bug: a stalled goalloop from another repo rendered into
        # every session's status line, for as long as the pointer stood.
        state_home = self.home(monkeypatch, tmp_path)
        planning = tmp_path / "another-project"
        planning.mkdir()
        (state_home / ".deep-plan-active").write_text(str(planning))
        assert statusline_module.resolve_planning_dir("sess1") is None
        assert statusline_module.resolve_planning_dir(None) is None


class TestDetectMode:
    def test_implement_detected(self, statusline_module, tmp_path: Path) -> None:
        (tmp_path / "impl-progress.md").write_text("x")
        assert statusline_module.detect_mode(tmp_path) == "implement"

    def test_plan_detected(self, statusline_module, tmp_path: Path) -> None:
        (tmp_path / "claude-plan.md").write_text("x")
        assert statusline_module.detect_mode(tmp_path) == "plan"

    def test_auto_detected(self, statusline_module, tmp_path: Path) -> None:
        (tmp_path / "phasing-overview.md").write_text("x")
        assert statusline_module.detect_mode(tmp_path) == "auto"

    def test_audit_detected(self, statusline_module, tmp_path: Path) -> None:
        (tmp_path / "objective.md").write_text("x")
        assert statusline_module.detect_mode(tmp_path) == "audit"

    def test_goalloop_detected(self, statusline_module, tmp_path: Path) -> None:
        (tmp_path / ".deepstate").mkdir()
        (tmp_path / ".deepstate" / "goalloop.json").write_text("{}")
        assert statusline_module.detect_mode(tmp_path) == "goalloop"

    def test_goalloop_outranks_its_own_implement_artifacts(
        self, statusline_module, tmp_path: Path
    ) -> None:
        # How `deep:implement probe-target` reached a status line: a goalloop
        # directory carries impl-progress.md, the implement branch matched
        # first, and the tracker meanwhile reported a goalloop-only step.
        (tmp_path / ".deepstate").mkdir()
        (tmp_path / ".deepstate" / "goalloop.json").write_text("{}")
        (tmp_path / "impl-progress.md").write_text("x")
        (tmp_path / "goal-ledger.md").write_text("x")
        assert statusline_module.detect_mode(tmp_path) == "goalloop"

    def test_unknown_returns_none(self, statusline_module, tmp_path: Path) -> None:
        assert statusline_module.detect_mode(tmp_path) is None

"""Tests for ``scripts/hooks/deep-context-monitor.py``."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MONITOR_PATH = REPO_ROOT / "scripts" / "hooks" / "deep-context-monitor.py"

from lib.context_metrics import BridgeState, write_bridge


@pytest.fixture
def monitor_module():
    spec = importlib.util.spec_from_file_location(
        "deep_context_monitor", MONITOR_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_state(**overrides) -> BridgeState:
    defaults = dict(
        session_id="sess",
        model_id="claude-opus-4-7",
        model_display="Opus 4.7",
        context_window_size=1_000_000,
        used_input_tokens=0,
        used_percentage=0.0,
        level="normal",
        current_step_id=None,
        current_step_title=None,
        planning_dir=None,
        mode=None,
        last_emitted_level=None,
        tool_calls_since_emit=0,
        ts=time.time(),
    )
    defaults.update(overrides)
    return BridgeState(**defaults)


def _run_monitor(monitor_module, monkeypatch, tmp_path: Path, session_id: str = "sess"):
    bridge = tmp_path / f"deep-ctx-{session_id}.json"
    monkeypatch.setattr(
        monitor_module, "bridge_path", lambda sid, tmp_dir=None: bridge
    )
    captured: list[str] = []
    monkeypatch.setattr(
        "builtins.print",
        lambda *a, **k: captured.append(" ".join(str(x) for x in a)),
    )
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"session_id": session_id}))
    )
    rc = monitor_module.main()
    return rc, captured, bridge


class TestMonitorMain:
    def test_no_bridge_silent(self, monitor_module, monkeypatch, tmp_path: Path) -> None:
        rc, out, _ = _run_monitor(monitor_module, monkeypatch, tmp_path)
        assert rc == 0
        assert out == []

    def test_normal_level_silent(self, monitor_module, monkeypatch, tmp_path: Path) -> None:
        state = _make_state(level="normal", used_percentage=30.0)
        bridge = tmp_path / "deep-ctx-sess.json"
        write_bridge(state, bridge)
        rc, out, _ = _run_monitor(monitor_module, monkeypatch, tmp_path)
        assert rc == 0
        assert out == []

    def test_warning_first_emit(self, monitor_module, monkeypatch, tmp_path: Path) -> None:
        state = _make_state(level="warning", used_percentage=68.0)
        bridge = tmp_path / "deep-ctx-sess.json"
        write_bridge(state, bridge)
        rc, out, _ = _run_monitor(monitor_module, monkeypatch, tmp_path)
        assert rc == 0
        assert len(out) == 1
        envelope = json.loads(out[0])
        assert envelope["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "WARNING" in envelope["hookSpecificOutput"]["additionalContext"]
        # Bridge updated with last_emitted_level
        from lib.context_metrics import read_bridge

        updated = read_bridge(bridge)
        assert updated is not None
        assert updated.last_emitted_level == "warning"
        assert updated.tool_calls_since_emit == 0

    def test_repeat_warning_debounced(
        self, monitor_module, monkeypatch, tmp_path: Path
    ) -> None:
        state = _make_state(
            level="warning",
            used_percentage=68.0,
            last_emitted_level="warning",
            tool_calls_since_emit=2,
        )
        bridge = tmp_path / "deep-ctx-sess.json"
        write_bridge(state, bridge)
        rc, out, _ = _run_monitor(monitor_module, monkeypatch, tmp_path)
        assert rc == 0
        assert out == []
        # Counter bumped
        from lib.context_metrics import read_bridge

        updated = read_bridge(bridge)
        assert updated is not None
        assert updated.tool_calls_since_emit == 3

    def test_repeat_warning_after_debounce_emits(
        self, monitor_module, monkeypatch, tmp_path: Path
    ) -> None:
        state = _make_state(
            level="warning",
            used_percentage=68.0,
            last_emitted_level="warning",
            tool_calls_since_emit=5,
        )
        bridge = tmp_path / "deep-ctx-sess.json"
        write_bridge(state, bridge)
        rc, out, _ = _run_monitor(monitor_module, monkeypatch, tmp_path)
        assert rc == 0
        assert len(out) == 1
        assert "WARNING" in json.loads(out[0])["hookSpecificOutput"]["additionalContext"]

    def test_escalation_bypasses_debounce(
        self, monitor_module, monkeypatch, tmp_path: Path
    ) -> None:
        state = _make_state(
            level="critical",
            used_percentage=82.0,
            last_emitted_level="warning",
            tool_calls_since_emit=0,
        )
        bridge = tmp_path / "deep-ctx-sess.json"
        write_bridge(state, bridge)
        rc, out, _ = _run_monitor(monitor_module, monkeypatch, tmp_path)
        assert rc == 0
        assert len(out) == 1
        assert "CRITICAL" in json.loads(out[0])["hookSpecificOutput"]["additionalContext"]

    def test_stale_bridge_silent(
        self, monitor_module, monkeypatch, tmp_path: Path
    ) -> None:
        state = _make_state(
            level="critical", used_percentage=90.0, ts=time.time() - 600
        )
        bridge = tmp_path / "deep-ctx-sess.json"
        write_bridge(state, bridge)
        rc, out, _ = _run_monitor(monitor_module, monkeypatch, tmp_path)
        assert rc == 0
        assert out == []

    def test_no_session_id_silent(self, monitor_module, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({})))
        captured: list[str] = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: captured.append(" ".join(str(x) for x in a)),
        )
        assert monitor_module.main() == 0
        assert captured == []

    def test_bad_stdin_silent(self, monitor_module, monkeypatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("garbage"))
        captured: list[str] = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: captured.append(" ".join(str(x) for x in a)),
        )
        assert monitor_module.main() == 0
        assert captured == []

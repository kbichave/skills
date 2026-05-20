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
        # Pin tempfile dir so the bridge does not leak into /tmp during tests.
        monkeypatch.setattr(
            statusline_module, "ACTIVE_POINTER", tmp_path / "nope"
        )
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
        monkeypatch.setattr(statusline_module, "ACTIVE_POINTER", tmp_path / "absent")

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


class TestResolveActiveDir:
    def test_missing_pointer_returns_none(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(statusline_module, "ACTIVE_POINTER", tmp_path / "absent")
        assert statusline_module.resolve_planning_dir() is None

    def test_pointer_with_existing_path(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        planning = tmp_path / "pd"
        planning.mkdir()
        pointer = tmp_path / "active"
        pointer.write_text(str(planning) + "\n")
        monkeypatch.setattr(statusline_module, "ACTIVE_POINTER", pointer)
        assert statusline_module.resolve_planning_dir() == planning

    def test_pointer_with_stale_path(
        self, statusline_module, monkeypatch, tmp_path: Path
    ) -> None:
        pointer = tmp_path / "active"
        pointer.write_text("/no/such/dir\n")
        monkeypatch.setattr(statusline_module, "ACTIVE_POINTER", pointer)
        assert statusline_module.resolve_planning_dir() is None


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

    def test_unknown_returns_none(self, statusline_module, tmp_path: Path) -> None:
        assert statusline_module.detect_mode(tmp_path) is None

"""Tests for scripts/checks/setup-session.py."""

from __future__ import annotations

import contextlib
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test via importlib since it has sys.path.insert
import importlib.util
_script = Path(__file__).parent.parent / "scripts" / "checks" / "setup-session.py"
_spec = importlib.util.spec_from_file_location("setup_session", _script)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

setup_session = _mod.setup_session
determine_mode = _mod.determine_mode
resolve_planning_dir = _mod.resolve_planning_dir
find_existing_session_dir = _mod._find_legacy_session
is_legacy_config = _mod.is_legacy_config
check_partial_setup = _mod.check_partial_setup


def _patch_no_beads():
    """Patch detect_beads to return False (simulates bd missing — hard-fail path)."""
    return patch.object(_mod, "detect_beads", return_value=False)


def _patch_beads_available():
    """Patch detect_beads to return True (simulates bd installed)."""
    return patch.object(_mod, "detect_beads", return_value=True)


@contextlib.contextmanager
def _patch_tracker():
    """Simulate beads installed AND stub BeadsSyncTracker as a pass-through.

    Real beads is required in production. Unit tests should not spawn bd
    subprocesses, so we replace the wrapper with one that returns the inner
    tracker untouched.
    """
    def _passthrough(tracker, beads_available=True, beads_cwd=None):
        return tracker

    with _patch_beads_available(), \
         patch.object(_mod, "BeadsSyncTracker", side_effect=_passthrough):
        yield

from lib.deepstate import DeepStateTracker


@pytest.fixture
def spec_file(tmp_path):
    """Create a non-empty spec file."""
    f = tmp_path / "spec.md"
    f.write_text("# My Spec\nSome content here.")
    return f


@pytest.fixture
def plugin_root(tmp_path):
    """Create a plugin root with config.json."""
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "config.json").write_text(json.dumps({"version": "1.0"}))
    return root


# ── NewSession ──────────────────────────────────────────────────────


class TestNewSession:
    def test_creates_deepstate_directory(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        assert result["success"] is True
        assert result["mode"] == "new"
        planning_dir = Path(result["planning_dir"])
        assert (planning_dir / ".deepstate" / "state.json").exists()

    def test_returns_epic_id(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        assert "epic_id" in result
        assert "deep-plan: spec" == result["epic_id"]

    def test_writes_config_with_deepstate_epic_id(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        config_path = Path(result["planning_dir"]) / "deep_plan_config.json"
        config = json.loads(config_path.read_text())
        assert "deepstate_epic_id" in config

    def test_output_includes_required_fields(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        for field in ["success", "mode", "planning_dir", "initial_file",
                       "plugin_root", "workflow", "review_mode", "epic_id", "message"]:
            assert field in result, f"Missing field: {field}"


# ── ResumeSession ──────────────────────────────────────────────────


class TestResumeSession:
    def test_resume_detects_existing_epic(self, spec_file, plugin_root):
        with _patch_tracker():
            # First call: new session
            result1 = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
            assert result1["mode"] == "new"
            # Second call: should resume
            result2 = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        assert result2["success"] is True
        assert result2["mode"] == "resume"

    def test_resume_returns_ready_issues(self, spec_file, plugin_root):
        with _patch_tracker():
            setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        assert "ready_issues" in result
        assert len(result["ready_issues"]) > 0

    def test_resume_does_not_recreate_issues(self, spec_file, plugin_root):
        with _patch_tracker():
            result1 = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
            planning_dir = Path(result1["planning_dir"])
            state1 = json.loads((planning_dir / ".deepstate" / "state.json").read_text())
            issue_count1 = len(state1["issues"])

            setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
            state2 = json.loads((planning_dir / ".deepstate" / "state.json").read_text())
            issue_count2 = len(state2["issues"])

        assert issue_count1 == issue_count2


# ── PartialSetupRecovery ───────────────────────────────────────────


class TestPartialSetupRecovery:
    def test_partial_setup_without_force_returns_error(self, spec_file, plugin_root):
        with _patch_tracker():
            # Create a partial state
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
            planning_dir = Path(result["planning_dir"])
            # Corrupt state by removing some issues
            state = json.loads((planning_dir / ".deepstate" / "state.json").read_text())
            keys = list(state["issues"].keys())
            for k in keys[:5]:
                del state["issues"][k]
            (planning_dir / ".deepstate" / "state.json").write_text(json.dumps(state))

            result2 = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        assert result2["success"] is False
        assert "partial_setup" in result2["mode"]

    def test_force_reinitializes_cleanly(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
            planning_dir = Path(result["planning_dir"])
            # Corrupt state
            state = json.loads((planning_dir / ".deepstate" / "state.json").read_text())
            keys = list(state["issues"].keys())
            for k in keys[:5]:
                del state["issues"][k]
            (planning_dir / ".deepstate" / "state.json").write_text(json.dumps(state))

            result2 = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=True,
            )
        assert result2["success"] is True
        assert result2["mode"] == "new"


# ── InputValidation ────────────────────────────────────────────────


class TestInputValidation:
    def test_rejects_directory_for_plan_workflow(self, tmp_path, plugin_root):
        result = setup_session(
            file_path=tmp_path, plugin_root=plugin_root,
            review_mode="skip", session_id=None,
            workflow="plan", force=False,
        )
        assert result["success"] is False
        assert "directory" in result["error"].lower()

    def test_accepts_directory_for_audit_workflow(self, tmp_path, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=tmp_path, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="audit", force=False,
            )
        assert result["success"] is True

    def test_spec_file_must_exist(self, tmp_path, plugin_root):
        result = setup_session(
            file_path=tmp_path / "nonexistent.md", plugin_root=plugin_root,
            review_mode="skip", session_id=None,
            workflow="plan", force=False,
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_spec_file_must_have_content(self, tmp_path, plugin_root):
        empty = tmp_path / "empty.md"
        empty.write_text("")
        result = setup_session(
            file_path=empty, plugin_root=plugin_root,
            review_mode="skip", session_id=None,
            workflow="plan", force=False,
        )
        assert result["success"] is False
        assert "empty" in result["error"].lower()


# ── BeadsIntegration ───────────────────────────────────────────────


class TestBeadsIntegration:
    def test_beads_available_reported_true_when_installed(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        assert result["success"] is True
        assert result["beads_available"] is True

    def test_missing_beads_raises_system_exit(self, spec_file, plugin_root):
        """bd is required; absence must hard-fail with install guidance."""
        with _patch_no_beads():
            with pytest.raises(SystemExit) as exc_info:
                setup_session(
                    file_path=spec_file, plugin_root=plugin_root,
                    review_mode="skip", session_id=None,
                    workflow="plan", force=False,
                )
        msg = str(exc_info.value).lower()
        assert "bd" in msg or "beads" in msg
        assert "install" in msg


# ── LegacyConfigDetection ─────────────────────────────────────────


class TestLegacyConfigDetection:
    def test_legacy_config_returns_error(self, spec_file, plugin_root):
        # Create a legacy config manually
        planning_dir = spec_file.parent
        config = {
            "plugin_root": str(plugin_root),
            "planning_dir": str(planning_dir),
            "initial_file": str(spec_file),
            "task_list_id": "old-task-list-123",
        }
        (planning_dir / "deep_plan_config.json").write_text(json.dumps(config))

        result = setup_session(
            file_path=spec_file, plugin_root=plugin_root,
            review_mode="skip", session_id=None,
            workflow="plan", force=False,
        )
        assert result["success"] is False
        assert result["mode"] == "legacy_config"

    def test_fresh_config_proceeds_normally(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        assert result["success"] is True

    def test_is_legacy_config_helper(self):
        assert is_legacy_config({"task_list_id": "x"}) is True
        assert is_legacy_config({"task_list_id": "x", "deepstate_epic_id": "y"}) is False
        assert is_legacy_config({}) is False


# ── SessionIsolation ───────────────────────────────────────────────


class TestSessionIsolation:
    def test_session_id_stored_in_config(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id="abcdef12-3456-7890",
                workflow="plan", force=False,
            )
        config_path = Path(result["planning_dir"]) / "deep_plan_config.json"
        config = json.loads(config_path.read_text())
        assert config.get("session_id") == "abcdef12-3456-7890"

    def test_session_prefix_used_for_directory(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id="abcdef12-3456-7890",
                workflow="plan", force=False,
            )
        assert "abcdef12" in result["planning_dir"]

    def test_existing_session_dir_reused(self, spec_file, plugin_root):
        with _patch_tracker():
            result1 = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id="abcdef12-3456-7890",
                workflow="plan", force=False,
            )
            result2 = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id="abcdef12-3456-7890",
                workflow="plan", force=False,
            )
        assert result1["planning_dir"] == result2["planning_dir"]


# ── JSONOutput ─────────────────────────────────────────────────────


class TestJSONOutput:
    def test_success_output_fields(self, spec_file, plugin_root):
        with _patch_tracker():
            result = setup_session(
                file_path=spec_file, plugin_root=plugin_root,
                review_mode="skip", session_id=None,
                workflow="plan", force=False,
            )
        required = ["success", "mode", "planning_dir", "initial_file",
                     "plugin_root", "workflow", "review_mode", "message"]
        for field in required:
            assert field in result

    def test_error_output_fields(self, tmp_path, plugin_root):
        result = setup_session(
            file_path=tmp_path / "nope.md", plugin_root=plugin_root,
            review_mode="skip", session_id=None,
            workflow="plan", force=False,
        )
        assert result["success"] is False
        assert "error" in result
        assert "mode" in result


# ── DetermineMode ─────────────────────────────────────────────────


class TestDetermineMode:
    def test_new_when_no_state(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        mode, info = determine_mode(tracker)
        assert mode == "new"

    def test_resume_when_open_issues_exist(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        tracker.init("test", {})
        tracker.create("s1", "Step 1")
        mode, info = determine_mode(tracker)
        assert mode == "resume"
        assert len(info["ready_issues"]) == 1

    def test_complete_when_all_closed(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        tracker.init("test", {})
        tracker.create("s1", "Step 1")
        tracker.close("s1", "done")
        mode, info = determine_mode(tracker)
        assert mode == "complete"


# ── ResolvePlanningDir ─────────────────────────────────────────────


class TestResolvePlanningDir:
    def test_legacy_files_use_spec_parent(self, tmp_path):
        (tmp_path / "claude-plan.md").write_text("x")
        result = resolve_planning_dir(tmp_path, "abcdef12")
        assert result == tmp_path

    def test_no_session_id_uses_sessions_root(self, tmp_path):
        result = resolve_planning_dir(tmp_path, None)
        # Without a session_id, falls into SESSIONS_ROOT under "default" prefix
        assert str(_mod.SESSIONS_ROOT) in str(result)
        assert "default" in str(result)

    def test_new_session_creates_subdirectory(self, tmp_path):
        result = resolve_planning_dir(tmp_path, "abcdef12-rest")
        # New sessions go to SESSIONS_ROOT, not inside the project tree
        assert str(_mod.SESSIONS_ROOT) in str(result)
        assert "abcdef12" in str(result)

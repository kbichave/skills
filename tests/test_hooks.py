"""Tests for hook configuration and scripts.

The section-writer hook tests are now in test_write_section_on_stop.py.
This file contains tests for hooks.json configuration validity and
truncation guard behavior.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

# Import truncation guard from hook script
_hook_path = Path(__file__).parent.parent / "scripts" / "hooks" / "impl-post-tool-use.py"
_spec = importlib.util.spec_from_file_location("impl_post_tool_use", _hook_path)
_hook_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook_mod)
check_truncation = _hook_mod.check_truncation
CRITICAL_FILES = _hook_mod.CRITICAL_FILES


class TestHooksJsonConfig:
    """Tests for hooks.json configuration validity."""

    @pytest.fixture
    def hooks_json_path(self):
        """Return path to hooks.json."""
        return Path(__file__).parent.parent / "hooks" / "hooks.json"

    def test_hooks_json_is_valid_json(self, hooks_json_path):
        """hooks.json should be valid JSON."""
        content = hooks_json_path.read_text()
        data = json.loads(content)  # Will raise if invalid
        assert "hooks" in data

    def test_plugin_root_not_quoted_in_commands(self, hooks_json_path):
        """${CLAUDE_PLUGIN_ROOT} must not be quoted in commands.

        Claude Code doesn't expand env vars inside quotes, so commands like:
            "command": "uv run \"${CLAUDE_PLUGIN_ROOT}/script.py\""
        will fail because the variable isn't expanded.

        Correct format:
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/script.py"
        """
        content = hooks_json_path.read_text()

        # Find all command values
        data = json.loads(content)
        for hook_type, hook_list in data.get("hooks", {}).items():
            for hook_group in hook_list:
                for hook in hook_group.get("hooks", []):
                    command = hook.get("command", "")
                    # Check for quoted variable (escaped quote followed by ${)
                    if r'\"${CLAUDE_PLUGIN_ROOT}' in command or r"\'${CLAUDE_PLUGIN_ROOT}" in command:
                        pytest.fail(
                            f"{hook_type} hook has quoted ${{CLAUDE_PLUGIN_ROOT}} which prevents expansion:\n"
                            f"  {command}\n"
                            f"Remove quotes around ${{CLAUDE_PLUGIN_ROOT}}"
                        )

    def test_all_hook_scripts_exist(self, hooks_json_path):
        """All scripts referenced in hooks.json should exist."""
        plugin_root = hooks_json_path.parent.parent
        data = json.loads(hooks_json_path.read_text())

        for hook_type, hook_list in data.get("hooks", {}).items():
            for hook_group in hook_list:
                for hook in hook_group.get("hooks", []):
                    command = hook.get("command", "")
                    # Extract script path after ${CLAUDE_PLUGIN_ROOT}
                    match = re.search(r'\$\{CLAUDE_PLUGIN_ROOT\}(/[^\s"\']+)', command)
                    if match:
                        relative_path = match.group(1)
                        full_path = plugin_root / relative_path.lstrip("/")
                        assert full_path.exists(), (
                            f"{hook_type} hook references non-existent script: {relative_path}"
                        )

    def test_expected_hook_types_present(self, hooks_json_path):
        """Verify expected hook types are configured.

        - SessionStart: captures session ID and transcript path
        - SubagentStop: writes section files when section-writer completes (with matcher)
        - SubagentStart: should NOT exist (tracking files no longer needed)
        """
        data = json.loads(hooks_json_path.read_text())
        hooks = data.get("hooks", {})

        assert "SessionStart" in hooks, "SessionStart hook should exist"
        assert "SubagentStop" in hooks, "SubagentStop hook should exist"
        assert "SubagentStart" not in hooks, "SubagentStart hook should be removed"

    def test_pre_tool_use_guard_is_wired(self, hooks_json_path):
        """The guard is the blocking layer Stages 3/4/5 all build on. Without a
        PreToolUse entry the plugin cannot block anything at all."""
        hooks = json.loads(hooks_json_path.read_text())["hooks"]
        assert "PreToolUse" in hooks
        groups = hooks["PreToolUse"]
        guard = [
            h
            for g in groups
            for h in g["hooks"]
            if "guard-pre-tool-use.py" in h["command"]
        ]
        assert len(guard) == 1, "guard hook should be wired exactly once"

    def test_pre_tool_use_guard_matches_write_shaped_tools(self, hooks_json_path):
        hooks = json.loads(hooks_json_path.read_text())["hooks"]
        matchers = [g.get("matcher", "") for g in hooks["PreToolUse"]]
        assert any(
            all(tool in m for tool in ("Write", "Edit", "NotebookEdit"))
            for m in matchers
        )

    def test_guard_hook_uses_python3_and_has_a_timeout(self, hooks_json_path):
        """uv run costs 150-300 ms of resolver overhead, which is unaffordable
        on a per-edit hook. The timeout stops a pathological regex wedging the
        session."""
        hooks = json.loads(hooks_json_path.read_text())["hooks"]
        for group in hooks["PreToolUse"]:
            for hook in group["hooks"]:
                if "guard-pre-tool-use.py" not in hook["command"]:
                    continue
                assert hook["command"].startswith("python3 ")
                assert "uv run" not in hook["command"]
                assert hook.get("timeout") is not None

    def test_subagent_stop_has_matcher(self, hooks_json_path):
        """SubagentStop hook should have matcher for section-writer."""
        data = json.loads(hooks_json_path.read_text())
        hooks = data.get("hooks", {})

        subagent_stop = hooks.get("SubagentStop", [])
        assert len(subagent_stop) > 0, "Should have SubagentStop hooks"

        # Check that it has a matcher for section-writer
        matchers = [hg.get("matcher", "") for hg in subagent_stop]
        assert any("section-writer" in m for m in matchers), (
            "SubagentStop should have matcher for section-writer"
        )

    def test_session_start_captures_transcript_path(self, hooks_json_path):
        """SessionStart hook should reference capture-session-id.py."""
        data = json.loads(hooks_json_path.read_text())
        hooks = data.get("hooks", {})

        session_start = hooks.get("SessionStart", [])
        assert len(session_start) > 0, "Should have SessionStart hooks"

        # Check command references capture-session-id.py
        commands = []
        for hook_group in session_start:
            for hook in hook_group.get("hooks", []):
                commands.append(hook.get("command", ""))

        assert any("capture-session-id.py" in cmd for cmd in commands), (
            "SessionStart should reference capture-session-id.py"
        )


class TestTruncationGuard:
    """Tests for the PostToolUse truncation guard."""

    def test_detects_size_reduction_in_critical_files(self, tmp_path):
        """Truncation guard warns when a critical file shrinks by >50%."""
        plan_file = tmp_path / "claude-plan.md"
        plan_file.write_text("x" * 5000)
        # Seed the cache with the original size
        cache = {"claude-plan.md": 5000}
        (tmp_path / ".file-sizes.json").write_text(json.dumps(cache))
        # Shrink the file
        plan_file.write_text("x" * 500)
        warnings = check_truncation(tmp_path)
        assert len(warnings) == 1
        assert "claude-plan.md" in warnings[0]
        assert "shrank" in warnings[0]

    def test_allows_normal_edits(self, tmp_path):
        """Small reductions (<50%) should not trigger a warning."""
        plan_file = tmp_path / "claude-plan.md"
        plan_file.write_text("x" * 5000)
        cache = {"claude-plan.md": 5000}
        (tmp_path / ".file-sizes.json").write_text(json.dumps(cache))
        plan_file.write_text("x" * 4800)
        warnings = check_truncation(tmp_path)
        assert len(warnings) == 0

    def test_allows_growth(self, tmp_path):
        """File growth should not trigger a warning."""
        plan_file = tmp_path / "claude-plan.md"
        plan_file.write_text("x" * 7000)
        cache = {"claude-plan.md": 5000}
        (tmp_path / ".file-sizes.json").write_text(json.dumps(cache))
        warnings = check_truncation(tmp_path)
        assert len(warnings) == 0

    def test_ignores_non_critical_files(self, tmp_path):
        """Non-critical files should be ignored even if they shrink."""
        other_file = tmp_path / "random.py"
        other_file.write_text("x" * 5000)
        cache = {"random.py": 5000}
        (tmp_path / ".file-sizes.json").write_text(json.dumps(cache))
        other_file.write_text("x" * 100)
        warnings = check_truncation(tmp_path)
        assert len(warnings) == 0

    def test_creates_cache_on_first_run(self, tmp_path):
        """First run with no cache should create it without warnings."""
        plan_file = tmp_path / "claude-plan.md"
        plan_file.write_text("x" * 3000)
        warnings = check_truncation(tmp_path)
        assert len(warnings) == 0
        assert (tmp_path / ".file-sizes.json").exists()


class TestSessionStartNoTracker:
    """Verify SessionStart hook does NOT call tracker or beads."""

    def test_session_start_has_no_tracker_or_beads_references(self):
        """capture-session-id.py must not reference deepstate, beads, or bd prime."""
        script = Path(__file__).parent.parent / "scripts" / "hooks" / "capture-session-id.py"
        source = script.read_text()
        forbidden = ["deepstate", "beads_sync", "bd prime", "tracker.prime", "DeepStateTracker"]
        for term in forbidden:
            assert term not in source, f"SessionStart hook must not reference '{term}'"

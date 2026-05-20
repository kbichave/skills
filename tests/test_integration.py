"""Integration tests for deep-plan plugin.

Tests the full lifecycle of deepstate-based workflows: session setup,
dependency resolution, step execution, resume, and cross-component interaction.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.beads_sync import BeadsSyncTracker, detect_beads
from lib.deepstate import DeepStateTracker
from lib.tasks import TASK_IDS, TASK_DEPENDENCIES
from lib.workflow import (
    create_plan_workflow,
    create_section_issues,
    create_autonomous_workflow,
)


# ── Markers ───────────────────────────────────────────────────────────

requires_bd = pytest.mark.skipif(
    shutil.which("bd") is None,
    reason="bd (beads) CLI not installed",
)


# ── Test 1: Full Lifecycle ────────────────────────────────────────────


class TestFullLifecycle:
    """Create workflow → step through deps → resume from disk → prime."""

    @pytest.fixture
    def tracker(self, tmp_path):
        return DeepStateTracker(state_dir=tmp_path / ".deepstate")

    @pytest.fixture
    def populated_tracker(self, tracker, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec")
        create_plan_workflow(
            tracker,
            plugin_root="/fake",
            planning_dir=str(tmp_path),
            initial_file=str(spec),
            review_mode="skip",
        )
        return tracker

    def test_first_ready_is_research_decision(self, populated_tracker):
        ready = populated_tracker.ready()
        ready_ids = {i["id"] for i in ready}
        assert "research-decision" in ready_ids

    def test_closing_step_unblocks_next(self, populated_tracker):
        populated_tracker.close("research-decision", "Topics selected")
        ready = populated_tracker.ready()
        ready_ids = {i["id"] for i in ready}
        assert "execute-research" in ready_ids
        assert "research-decision" not in ready_ids

    def test_dependency_chain_walks_forward(self, populated_tracker):
        """Close first 4 steps; write-spec should become ready."""
        chain = ["research-decision", "execute-research", "detailed-interview", "save-interview"]
        for step in chain:
            populated_tracker.close(step, "done")
        ready_ids = {i["id"] for i in populated_tracker.ready()}
        assert "write-spec" in ready_ids

    def test_resume_from_disk(self, populated_tracker, tmp_path):
        """A new tracker instance reads persisted state correctly."""
        populated_tracker.close("research-decision", "done")
        populated_tracker.close("execute-research", "done")

        # New instance — simulates session resume after /clear
        fresh = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        ready_ids = {i["id"] for i in fresh.ready()}
        assert "detailed-interview" in ready_ids
        assert "research-decision" not in ready_ids

    def test_prime_output(self, populated_tracker):
        populated_tracker.close("research-decision", "done")
        prime = populated_tracker.prime()
        assert len(prime) > 0
        # Prime includes progress and epic title
        assert "deep-plan" in prime
        assert "1/" in prime  # "1/17 issues closed"

    def test_full_walkthrough_to_completion(self, populated_tracker):
        """Close every step in order; tracker should have no open issues."""
        for step_num in sorted(TASK_IDS.keys()):
            task_id = TASK_IDS[step_num]
            populated_tracker.close(task_id, "done")

        all_issues = populated_tracker.list_issues()
        open_issues = [i for i in all_issues if i["status"] == "open"]
        assert open_issues == []
        assert populated_tracker.ready() == []


# ── Test 2: Section Creation with Parallel Ready ──────────────────────


class TestSectionParallelReady:
    """Section issues respect depends_on edges; parallel sections surface together."""

    @pytest.fixture
    def tracker_with_sections(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        tracker.init("test-epic", {})
        # Create a pre-requisite step that sections depend on
        tracker.create("generate-section-tasks", "Generate Section Tasks")
        tracker.close("generate-section-tasks", "done")

        sections_dir = tmp_path / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text(
            "# Sections\n\n"
            "<!-- SECTION_MANIFEST\n"
            "section-01-foundation\n"
            "section-02-config              depends_on:section-01-foundation\n"
            "section-03-parser\n"
            "section-04-workflow             depends_on:section-01-foundation,section-03-parser\n"
            "END_MANIFEST -->\n"
        )
        mapping = create_section_issues(
            tracker, planning_dir=str(tmp_path), plugin_root="/fake"
        )
        return tracker, mapping

    def test_independent_sections_ready_in_parallel(self, tracker_with_sections):
        tracker, _ = tracker_with_sections
        ready_ids = {i["id"] for i in tracker.ready()}
        assert "section-01-foundation" in ready_ids
        assert "section-03-parser" in ready_ids
        # Blocked sections should NOT be ready
        assert "section-02-config" not in ready_ids
        assert "section-04-workflow" not in ready_ids

    def test_closing_one_unblocks_dependent(self, tracker_with_sections):
        tracker, _ = tracker_with_sections
        tracker.close("section-01-foundation", "done")
        ready_ids = {i["id"] for i in tracker.ready()}
        assert "section-02-config" in ready_ids
        # section-04 still blocked by section-03
        assert "section-04-workflow" not in ready_ids

    def test_closing_both_deps_unblocks_section_04(self, tracker_with_sections):
        tracker, _ = tracker_with_sections
        tracker.close("section-01-foundation", "done")
        tracker.close("section-03-parser", "done")
        ready_ids = {i["id"] for i in tracker.ready()}
        assert "section-04-workflow" in ready_ids

    def test_final_verification_blocked_until_all_sections_done(self, tracker_with_sections):
        tracker, _ = tracker_with_sections
        # Close all sections
        for sid in ["section-01-foundation", "section-02-config",
                     "section-03-parser", "section-04-workflow"]:
            tracker.close(sid, "done")
        ready_ids = {i["id"] for i in tracker.ready()}
        assert "final-verification" in ready_ids

    def test_mapping_returns_correct_ids(self, tracker_with_sections):
        _, mapping = tracker_with_sections
        assert "section-01-foundation" in mapping
        assert "section-04-workflow" in mapping
        assert len(mapping) == 4


# ── Test 3: Beads Sync Fire-and-Forget ────────────────────────────────


class TestBeadsSyncFireAndForget:
    """BeadsSyncTracker mirrors to bd CLI; failures are non-fatal."""

    @pytest.fixture
    def tracker(self, tmp_path):
        return DeepStateTracker(state_dir=tmp_path / ".deepstate")

    def test_create_calls_bd(self, tracker, monkeypatch):
        sync = BeadsSyncTracker(tracker=tracker, beads_available=True, beads_cwd=Path("/tmp"))
        sync.tracker.init("test", {})

        bd_calls = []

        def mock_run(*args, **kwargs):
            bd_calls.append(args[0])
            return subprocess.CompletedProcess(args[0], 0, stdout='{"id": "1"}', stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        sync.create("issue-1", "Test Issue")

        # Should have called bd create
        bd_cmds = [c for c in bd_calls if c[0] == "bd" and c[1] == "create"]
        assert len(bd_cmds) >= 1
        # Issue should exist in deepstate
        issue = tracker.show("issue-1")
        assert issue["status"] == "open"

    def test_close_calls_bd(self, tracker, monkeypatch):
        sync = BeadsSyncTracker(tracker=tracker, beads_available=True, beads_cwd=Path("/tmp"))
        sync.tracker.init("test", {})
        sync.tracker.create("issue-1", "Test")

        bd_calls = []

        def mock_run(*args, **kwargs):
            bd_calls.append(args[0])
            return subprocess.CompletedProcess(args[0], 0, stdout='{"id": "1"}', stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        sync.close("issue-1", "Done")

        bd_cmds = [c for c in bd_calls if c[0] == "bd" and c[1] == "close"]
        assert len(bd_cmds) >= 1
        assert tracker.show("issue-1")["status"] == "closed"

    def test_bd_timeout_does_not_corrupt_state(self, tracker, monkeypatch):
        sync = BeadsSyncTracker(tracker=tracker, beads_available=True, beads_cwd=Path("/tmp"))
        sync.tracker.init("test", {})

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="bd", timeout=30)

        monkeypatch.setattr(subprocess, "run", mock_run)
        # Should not raise — beads failure is non-fatal
        sync.create("issue-2", "Timeout Test")
        assert tracker.show("issue-2")["status"] == "open"

    def test_beads_unavailable_skips_subprocess(self, tracker, monkeypatch):
        sync = BeadsSyncTracker(tracker=tracker, beads_available=False)
        sync.tracker.init("test", {})

        calls = []
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))
        sync.create("issue-3", "No beads")
        assert calls == []
        assert tracker.show("issue-3")["status"] == "open"


# ── Test 4: Autonomous Multi-Phase Sequencing ─────────────────────────


class TestAutonomousPhaseSequencing:
    """Phase sub-epics respect inter-phase deps; parallel phases surface together."""

    @pytest.fixture
    def tracker_with_phases(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = tmp_path / "phases"
        phases_dir.mkdir()
        (phases_dir / "phasing-overview.md").write_text(
            "# Phasing Overview\n\n"
            "## Dependency Graph\n\n"
            "P01 --> P02 --> P04\n"
            "P01 --> P03 --> P04\n"
        )
        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings="/fake/findings",
        )
        return tracker

    def test_only_p01_ready_initially(self, tracker_with_phases):
        ready_ids = {i["id"] for i in tracker_with_phases.ready()}
        assert "phase-P01" in ready_ids
        assert "phase-P02" not in ready_ids
        assert "phase-P03" not in ready_ids
        assert "phase-P04" not in ready_ids

    def test_closing_p01_unblocks_p02_and_p03(self, tracker_with_phases):
        tracker = tracker_with_phases
        # Close phase-P01 and all its step issues
        for step_num in sorted(TASK_IDS.keys()):
            task_id = TASK_IDS[step_num]
            tracker.close(f"P01-{task_id}", "done")
        tracker.close("phase-P01", "done")

        ready_ids = {i["id"] for i in tracker.ready()}
        assert "phase-P02" in ready_ids
        assert "phase-P03" in ready_ids
        assert "phase-P04" not in ready_ids

    def test_p04_waits_for_both_p02_and_p03(self, tracker_with_phases):
        tracker = tracker_with_phases
        # Close P01 fully
        for step_num in sorted(TASK_IDS.keys()):
            tracker.close(f"P01-{TASK_IDS[step_num]}", "done")
        tracker.close("phase-P01", "done")

        # Close P02 fully (but not P03)
        for step_num in sorted(TASK_IDS.keys()):
            task_id = TASK_IDS[step_num]
            nid = f"P02-{task_id}"
            issue = tracker.show(nid)
            if issue["status"] == "open":
                tracker.close(nid, "done")
        tracker.close("phase-P02", "done")

        ready_ids = {i["id"] for i in tracker.ready()}
        assert "phase-P04" not in ready_ids

    def test_p04_unblocked_after_both_p02_p03(self, tracker_with_phases):
        tracker = tracker_with_phases
        # Close P01, P02, P03 fully
        for phase in ["P01", "P02", "P03"]:
            for step_num in sorted(TASK_IDS.keys()):
                task_id = TASK_IDS[step_num]
                nid = f"{phase}-{task_id}"
                issue = tracker.show(nid)
                if issue["status"] == "open":
                    tracker.close(nid, "done")
            tracker.close(f"phase-{phase}", "done")

        ready_ids = {i["id"] for i in tracker.ready()}
        assert "phase-P04" in ready_ids


# ── Test 5: Old Task Scripts Deleted ──────────────────────────────────


class TestOldFilesDeleted:
    def test_old_task_scripts_deleted(self):
        """Verify legacy task system files have been removed."""
        plugin_root = Path(__file__).parent.parent
        deleted_files = [
            "scripts/lib/task_storage.py",
            "scripts/lib/task_reconciliation.py",
            "scripts/checks/setup-planning-session.py",
            "scripts/checks/generate-section-tasks.py",
            "tests/test_task_storage.py",
            "tests/test_task_reconciliation.py",
            "tests/test_setup_planning_session.py",
            "tests/test_generate_section_tasks.py",
        ]
        for rel_path in deleted_files:
            assert not (plugin_root / rel_path).exists(), f"Should be deleted: {rel_path}"


# ── Test 6: New Scripts Exist ─────────────────────────────────────────


class TestNewFilesExist:
    def test_new_scripts_exist(self):
        """Verify all new files from the deepstate migration are present."""
        plugin_root = Path(__file__).parent.parent
        new_files = [
            "scripts/lib/deepstate.py",
            "scripts/lib/beads_sync.py",
            "scripts/lib/workflow.py",
            "scripts/lib/research_topics.py",
            "scripts/checks/setup-session.py",
            "scripts/checks/generate-sections.py",
            "scripts/checks/validate-coverage.py",
            "skills/deep/SKILL.md",
        ]
        for rel_path in new_files:
            assert (plugin_root / rel_path).exists(), f"Missing new file: {rel_path}"


# ── Test 7: Real Beads Sync (optional) ────────────────────────────────


@requires_bd
class TestRealBeadsSync:
    def test_real_bd_init_create_close(self, tmp_path):
        """Real bd CLI integration — only runs when bd is installed."""
        # Init a real beads repo
        subprocess.run(
            ["bd", "init", "--stealth", "--skip-hooks"],
            cwd=tmp_path,
            capture_output=True,
            timeout=15,
        )
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        sync = BeadsSyncTracker(
            tracker=tracker,
            beads_available=True,
            beads_cwd=tmp_path,
        )
        sync.tracker.init("bd-test", {})
        sync.create("bd-issue-1", "Real BD Test")
        sync.close("bd-issue-1", "Closed via test")

        # Verify deepstate is correct regardless of bd behavior
        issue = tracker.show("bd-issue-1")
        assert issue["status"] == "closed"


# ── Plugin Structure (preserved from original) ───────────────────────


class TestPluginStructure:
    """Tests that validate plugin structure is correct."""

    @pytest.fixture
    def plugin_root(self):
        return Path(__file__).parent.parent

    def test_plugin_json_exists(self, plugin_root):
        plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
        assert plugin_json.exists()

    def test_plugin_json_valid(self, plugin_root):
        plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
        data = json.loads(plugin_json.read_text())
        assert "name" in data
        assert "description" in data
        assert "version" in data

    def test_config_json_exists(self, plugin_root):
        assert (plugin_root / "config.json").exists()

    def test_config_json_valid(self, plugin_root):
        data = json.loads((plugin_root / "config.json").read_text())
        for key in ("context", "external_review", "models", "llm_client"):
            assert key in data

    def test_skill_exists(self, plugin_root):
        assert (plugin_root / "skills" / "deep" / "SKILL.md").exists()

    def test_prompts_exist(self, plugin_root):
        assert (plugin_root / "prompts" / "plan_reviewer" / "system").exists()
        assert (plugin_root / "prompts" / "plan_reviewer" / "user").exists()

    def test_lib_modules_exist(self, plugin_root):
        lib = plugin_root / "scripts" / "lib"
        for module in ("config.py", "prompts.py", "deepstate.py", "beads_sync.py", "workflow.py"):
            assert (lib / module).exists(), f"Missing: {module}"

    def test_check_scripts_exist(self, plugin_root):
        checks = plugin_root / "scripts" / "checks"
        assert (checks / "validate-env.sh").exists()
        assert (checks / "check-context-decision.py").exists()
        assert (checks / "setup-session.py").exists()
        assert (checks / "generate-sections.py").exists()


class TestOutputFormat:
    """Tests that validate output format contracts."""

    def test_section_index_has_required_format(self):
        expected_headers = [
            "# Implementation Sections Index",
            "## Dependency Graph",
            "## Execution Order",
        ]
        sample_index = """# Implementation Sections Index

## Dependency Graph

| Section | Depends On | Blocks | Parallelizable |
|---------|------------|--------|----------------|
| section-01 | - | section-02 | Yes |

## Execution Order

1. section-01 (no dependencies)
"""
        for header in expected_headers:
            assert header in sample_index

    def test_planning_state_json_schema(self):
        sample_state = {
            "current_step": 10,
            "completed_steps": [1, 2, 3, 4, 5, 6, 7, 8, 9],
            "planning_dir": "/path/to/planning",
            "has_research": True,
            "has_spec": True,
            "has_plan": True,
            "external_review": {
                "current_iteration": 1,
                "total_iterations": 2,
                "gemini_available": True,
                "chatgpt_available": True,
            },
            "last_updated": "2026-01-05T10:30:00Z",
        }
        assert "current_step" in sample_state
        assert "completed_steps" in sample_state
        assert isinstance(sample_state["completed_steps"], list)

"""Tests for the discovery bridge: cross-mode research reuse and interview passthrough."""

from pathlib import Path

import pytest

from scripts.lib.deepstate import DeepStateTracker
from scripts.lib.tasks import TASK_DEFINITIONS
from scripts.lib.workflow import (
    create_autonomous_workflow,
    create_plan_workflow,
)


@pytest.fixture
def tracker(tmp_path):
    return DeepStateTracker(state_dir=tmp_path / ".deepstate")


def _make_phases(tmp_path: Path, *, num_phases: int = 2) -> Path:
    """Create a minimal phases directory with phasing-overview.md."""
    phases_dir = tmp_path / "phases"
    phases_dir.mkdir()
    if num_phases == 2:
        (phases_dir / "phasing-overview.md").write_text(
            "## Dependency Graph\n\nP01 ──→ P02\n"
        )
    elif num_phases == 3:
        (phases_dir / "phasing-overview.md").write_text(
            "## Dependency Graph\n\nP01 ──→ P02 ──→ P03\n"
        )
    return phases_dir


# ── Auto Mode: Research Bridge ────────────────────────────────────────


class TestAutoResearchBridge:
    def test_non_first_research_has_bridge_ref(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = _make_phases(tmp_path)
        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings="/fake/discovery",
        )
        research = tracker.show("P02-research-decision")
        assert "discovery-bridge.md" in research["description"]

    def test_non_first_execute_research_has_bridge_ref(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = _make_phases(tmp_path)
        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings="/fake/discovery",
        )
        research = tracker.show("P02-execute-research")
        assert "discovery-bridge.md" in research["description"]


# ── Auto Mode: Interview Guard ────────────────────────────────────────


class TestAutoInterviewGuard:
    def test_first_phase_self_interview(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = _make_phases(tmp_path)
        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings="/fake/discovery",
        )
        interview = tracker.show("P01-detailed-interview")
        assert "SELF-INTERVIEW" in interview["description"]

    def test_non_first_uses_discovery_interview(self, tmp_path):
        tracker = DeepStateTracker(state_dir=tmp_path / ".deepstate")
        phases_dir = _make_phases(tmp_path)
        create_autonomous_workflow(
            tracker,
            phases_dir=str(phases_dir),
            plugin_root="/fake",
            discovery_findings="/fake/discovery",
        )
        interview = tracker.show("P02-detailed-interview")
        assert "SELF-INTERVIEW" not in interview["description"]
        assert "discovery interview" in interview["description"].lower() or "interview.md" in interview["description"]


# ── Task Definitions ──────────────────────────────────────────────────


class TestTaskDefinitions:
    def test_integrate_feedback_no_integration_notes(self):
        desc = TASK_DEFINITIONS["integrate-feedback"].description
        assert "integration notes" not in desc.lower()

    def test_integrate_feedback_description_updated(self):
        desc = TASK_DEFINITIONS["integrate-feedback"].description
        assert "Apply" in desc
        assert "claude-plan.md" in desc


# ── Plan Mode Isolation ───────────────────────────────────────────────


class TestPlanModeIsolation:
    def test_plan_mode_no_bridge_reference(self, tracker, tmp_path):
        create_plan_workflow(
            tracker,
            plugin_root="/fake",
            planning_dir=str(tmp_path),
            initial_file=str(tmp_path / "spec.md"),
            review_mode="skip",
        )
        state = tracker._load()
        for issue_id, issue in state["issues"].items():
            assert "discovery-bridge.md" not in issue.get("description", ""), (
                f"Plan mode issue {issue_id} should not reference discovery-bridge.md"
            )


# ── Reference File Existence ─────────────────────────────────────────


class TestReferenceFileExists:
    def test_discovery_bridge_exists(self):
        bridge = Path(__file__).parent.parent / "references" / "discovery-bridge.md"
        assert bridge.exists(), "references/discovery-bridge.md must exist"

    def test_discovery_bridge_has_required_sections(self):
        bridge = Path(__file__).parent.parent / "references" / "discovery-bridge.md"
        content = bridge.read_text()
        assert "Phase A" in content
        assert "Phase B" in content
        assert "Phase C" in content
        assert "5" in content  # budget rule
        assert "Stale Discovery" in content or "stale" in content.lower()
        assert "Interview Passthrough" in content

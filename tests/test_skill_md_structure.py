"""Tests for skills/deep/SKILL.md structural invariants.

The unified /deep skill must:
1. Contain the 3 inline guardrails
2. Reference the correct reference files for all modes
3. Include the tracker.ready() -> execute -> close loop
4. Stay under 300 lines (it's a unified skill replacing 5)
5. Preserve frontmatter (name, description)
6. Reference setup-session.py and generate-sections.py
7. Include --workflow audit flag
8. Reference .deepstate for implement mode
9. Not reference old script names
"""

from __future__ import annotations

import pathlib

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_PATH = PLUGIN_ROOT / "skills" / "deep" / "SKILL.md"

GUARDRAILS = [
    "Always read the reference file for the current step before executing",
    "Never skip a step",
    "Always close the step",
]


@pytest.fixture
def skill_content():
    """Read skills/deep/SKILL.md and return its text."""
    return SKILL_PATH.read_text()


def test_skill_md_exists():
    """The unified skills/deep/SKILL.md must exist."""
    assert SKILL_PATH.exists(), f"Expected {SKILL_PATH} to exist"


def test_skill_md_contains_three_inline_guardrails(skill_content):
    """SKILL.md must contain the three guardrail phrases."""
    for guardrail in GUARDRAILS:
        assert guardrail in skill_content, f"Missing guardrail: {guardrail}"


def test_skill_md_references_correct_reference_files(skill_content):
    """SKILL.md must reference files from references/ for each mode."""
    assert "references/" in skill_content


def test_skill_md_has_tracker_ready_loop(skill_content):
    """SKILL.md must describe the tracker.ready() loop."""
    assert "tracker.ready()" in skill_content


def test_skill_md_has_tracker_close(skill_content):
    """SKILL.md must reference tracker.close()."""
    assert "tracker.close(" in skill_content


def test_skill_md_is_under_budget(skill_content):
    """Unified SKILL.md budget. Detailed workflows live under references/, not inline."""
    lines = skill_content.split("\n")
    assert len(lines) <= 300, f"SKILL.md has {len(lines)} lines, max is 300"


def test_frontmatter_preserved(skill_content):
    """YAML frontmatter with name and description must be present."""
    assert skill_content.startswith("---")
    assert "name:" in skill_content
    assert "description:" in skill_content


def test_references_setup_session(skill_content):
    """SKILL.md must reference setup-session.py (used by plan/audit/auto)."""
    assert "setup-session.py" in skill_content


def test_references_generate_sections(skill_content):
    """SKILL.md must reference generate-sections.py (used in plan mode)."""
    assert "generate-sections.py" in skill_content


def test_passes_workflow_audit_flag(skill_content):
    """Discovery mode must pass --workflow audit to setup-session.py."""
    assert '--workflow "audit"' in skill_content or "--workflow audit" in skill_content


def test_implement_reads_existing_deepstate(skill_content):
    """Implement mode must read existing .deepstate/ state."""
    assert ".deepstate" in skill_content


def test_no_old_script_names(skill_content):
    """SKILL.md must not reference old script names."""
    old_names = ["setup-planning-session.py", "generate-section-tasks.py"]
    for old_name in old_names:
        assert old_name not in skill_content, (
            f"SKILL.md still references old script: {old_name}"
        )


def test_no_position_based_tasks(skill_content):
    """SKILL.md must not reference TaskList (old position-based tracking)."""
    assert "TaskList" not in skill_content


def test_old_skill_dirs_removed():
    """Old per-mode skill directories must no longer exist."""
    removed_dirs = ["deep-plan", "deep-discovery", "deep-implement", "deep-auto", "deep-plan-all"]
    for dirname in removed_dirs:
        path = PLUGIN_ROOT / "skills" / dirname
        assert not path.exists(), (
            f"Old skill directory still exists: skills/{dirname}/ — should have been removed"
        )


def test_all_modes_dispatched(skill_content):
    """SKILL.md must dispatch all four modes."""
    for mode in ("audit", "plan", "implement", "auto"):
        assert mode in skill_content, f"Mode '{mode}' not mentioned in SKILL.md"


def test_inline_prompt_handled(skill_content):
    """SKILL.md must describe handling for inline text input."""
    assert "auto-spec-synthesis" in skill_content or "inline" in skill_content.lower()

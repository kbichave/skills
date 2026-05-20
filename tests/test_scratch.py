"""Tests for scripts/lib/scratch.py — throwaway artifact lifecycle."""

from __future__ import annotations

import pytest

from scripts.lib.scratch import (
    DELETE_AFTER_VALUES,
    SCRATCH_DIRNAME,
    ScratchArtifact,
    cleanup_scratch,
    list_scratch_artifacts,
    write_scratch_artifact,
)


@pytest.fixture
def planning_dir(tmp_path):
    return tmp_path


class TestWriteScratchArtifact:
    def test_creates_file_under_scratch_dir(self, planning_dir):
        write_scratch_artifact(planning_dir, "notes.md", "some content")
        assert (planning_dir / SCRATCH_DIRNAME / "notes.md").exists()

    def test_prepends_throwaway_header(self, planning_dir):
        write_scratch_artifact(planning_dir, "notes.md", "body text")
        content = (planning_dir / SCRATCH_DIRNAME / "notes.md").read_text()
        assert "THROWAWAY:" in content
        assert "body text" in content
        assert "Scratch artifact" in content  # the human-visible warning line

    def test_respects_delete_after_in_header(self, planning_dir):
        write_scratch_artifact(planning_dir, "x.md", "x", delete_after="step")
        content = (planning_dir / SCRATCH_DIRNAME / "x.md").read_text()
        assert "delete-after=step" in content

    def test_rejects_invalid_delete_after(self, planning_dir):
        with pytest.raises(ValueError):
            write_scratch_artifact(planning_dir, "x.md", "x", delete_after="forever")

    def test_rejects_path_traversal(self, planning_dir):
        with pytest.raises(ValueError):
            write_scratch_artifact(planning_dir, "../escape.md", "x")
        with pytest.raises(ValueError):
            write_scratch_artifact(planning_dir, "sub/inside.md", "x")
        with pytest.raises(ValueError):
            write_scratch_artifact(planning_dir, "", "x")

    def test_overwrites_same_name(self, planning_dir):
        write_scratch_artifact(planning_dir, "x.md", "v1")
        write_scratch_artifact(planning_dir, "x.md", "v2")
        content = (planning_dir / SCRATCH_DIRNAME / "x.md").read_text()
        assert "v2" in content
        assert "v1" not in content.replace("v2", "")  # crude: no v1 left


class TestListScratchArtifacts:
    def test_empty_when_no_dir(self, planning_dir):
        assert list_scratch_artifacts(planning_dir) == []

    def test_returns_written_artifacts(self, planning_dir):
        write_scratch_artifact(planning_dir, "a.md", "x", delete_after="step")
        write_scratch_artifact(planning_dir, "b.md", "y", delete_after="mode-complete")
        artifacts = list_scratch_artifacts(planning_dir)
        names = {a.path.name for a in artifacts}
        assert names == {"a.md", "b.md"}

    def test_recovers_delete_after_from_header(self, planning_dir):
        write_scratch_artifact(planning_dir, "step.md", "x", delete_after="step")
        write_scratch_artifact(planning_dir, "mode.md", "y", delete_after="mode-complete")
        artifacts = {a.path.name: a.delete_after for a in list_scratch_artifacts(planning_dir)}
        assert artifacts["step.md"] == "step"
        assert artifacts["mode.md"] == "mode-complete"

    def test_unmarked_file_defaults_to_mode_complete(self, planning_dir):
        scratch_dir = planning_dir / SCRATCH_DIRNAME
        scratch_dir.mkdir()
        (scratch_dir / "orphan.md").write_text("no header here\n")
        artifacts = list_scratch_artifacts(planning_dir)
        assert len(artifacts) == 1
        assert artifacts[0].delete_after == "mode-complete"


class TestCleanupScratch:
    def test_step_trigger_removes_only_step_scoped(self, planning_dir):
        write_scratch_artifact(planning_dir, "a.md", "x", delete_after="step")
        write_scratch_artifact(planning_dir, "b.md", "y", delete_after="mode-complete")
        write_scratch_artifact(planning_dir, "c.md", "z", delete_after="session-end")
        removed = cleanup_scratch(planning_dir, trigger="step")
        survivors = {a.path.name for a in list_scratch_artifacts(planning_dir)}
        assert {p.name for p in removed} == {"a.md"}
        assert survivors == {"b.md", "c.md"}

    def test_mode_trigger_removes_step_and_mode(self, planning_dir):
        write_scratch_artifact(planning_dir, "a.md", "x", delete_after="step")
        write_scratch_artifact(planning_dir, "b.md", "y", delete_after="mode-complete")
        write_scratch_artifact(planning_dir, "c.md", "z", delete_after="session-end")
        removed = cleanup_scratch(planning_dir, trigger="mode-complete")
        survivors = {a.path.name for a in list_scratch_artifacts(planning_dir)}
        assert {p.name for p in removed} == {"a.md", "b.md"}
        assert survivors == {"c.md"}

    def test_session_trigger_removes_everything(self, planning_dir):
        write_scratch_artifact(planning_dir, "a.md", "x", delete_after="step")
        write_scratch_artifact(planning_dir, "c.md", "z", delete_after="session-end")
        cleanup_scratch(planning_dir, trigger="session-end")
        assert list_scratch_artifacts(planning_dir) == []

    def test_cleanup_removes_empty_scratch_dir(self, planning_dir):
        write_scratch_artifact(planning_dir, "a.md", "x", delete_after="step")
        cleanup_scratch(planning_dir, trigger="step")
        assert not (planning_dir / SCRATCH_DIRNAME).exists()

    def test_cleanup_preserves_non_empty_scratch_dir(self, planning_dir):
        write_scratch_artifact(planning_dir, "a.md", "x", delete_after="step")
        write_scratch_artifact(planning_dir, "b.md", "y", delete_after="session-end")
        cleanup_scratch(planning_dir, trigger="step")
        assert (planning_dir / SCRATCH_DIRNAME).exists()

    def test_invalid_trigger_raises(self, planning_dir):
        with pytest.raises(ValueError):
            cleanup_scratch(planning_dir, trigger="never")

    def test_constants_are_sorted_by_strictness(self):
        # step ⊂ mode-complete ⊂ session-end
        assert DELETE_AFTER_VALUES.index("step") < DELETE_AFTER_VALUES.index("mode-complete")
        assert DELETE_AFTER_VALUES.index("mode-complete") < DELETE_AFTER_VALUES.index("session-end")

"""Tests for the git wrapper behind intent publishing.

The property worth protecting: publishing stages and commits exactly ONE file.
`git add -A` in a plugin is how a credential file ends up in a commit nobody
reviewed, so the isolation is asserted directly against a dirty index.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import vcs

pytestmark = pytest.mark.skipif(not vcs.git_available(), reason="git not on PATH")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for key, value in (("user.email", "dev@example.com"), ("user.name", "Dev")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    return tmp_path


class TestRepoDetection:
    def test_detects_a_work_tree(self, repo):
        assert vcs.is_repo(repo) is True

    def test_non_repo_is_not_a_work_tree(self, tmp_path):
        assert vcs.is_repo(tmp_path / "nowhere") is False

    def test_repo_root_resolves(self, repo):
        nested = repo / "a" / "b"
        nested.mkdir(parents=True)
        assert vcs.repo_root(nested).resolve() == repo.resolve()


class TestAuthorResolution:
    def test_explicit_author_wins(self, repo):
        assert vcs.resolve_author(repo, explicit="someone@else.com") == "someone@else.com"

    def test_falls_back_to_git_config(self, repo):
        assert vcs.resolve_author(repo) == "dev@example.com"

    def test_unknown_when_nothing_is_configured(self, tmp_path):
        """Never blocks. 'unknown' is a legal author — this is attestation,
        not authentication, and building auth here would be scope creep."""
        assert vcs.resolve_author(tmp_path / "nowhere") == vcs.UNKNOWN_AUTHOR

    def test_blank_explicit_author_falls_through(self, repo):
        assert vcs.resolve_author(repo, explicit="   ") == "dev@example.com"


class TestCommitIsolation:
    def test_commits_the_named_file(self, repo):
        target = repo / "intent.md"
        target.write_text("# intent\n")
        assert vcs.commit_file(target, "docs(intent): add", repo).ok

        listed = subprocess.run(
            ["git", "-C", str(repo), "show", "--name-only", "--format=", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert listed == ["intent.md"]

    def test_leaves_an_unrelated_staged_file_alone(self, repo):
        """A dirty index must not get swept into the intent commit."""
        unrelated = repo / "secrets.env"
        unrelated.write_text("TOKEN=abc\n")
        subprocess.run(["git", "-C", str(repo), "add", "secrets.env"], check=True)

        target = repo / "intent.md"
        target.write_text("# intent\n")
        vcs.commit_file(target, "docs(intent): add", repo)

        listed = subprocess.run(
            ["git", "-C", str(repo), "show", "--name-only", "--format=", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert listed == ["intent.md"]
        assert vcs.has_staged_changes(repo), "the unrelated file should still be staged"

    def test_failure_is_reported_not_raised(self, tmp_path):
        result = vcs.commit_file(tmp_path / "x.md", "msg", tmp_path / "nowhere")
        assert result.ok is False
        assert result.error


class TestTracking:
    def test_untracked_file_is_not_tracked(self, repo):
        (repo / "a.md").write_text("x")
        assert vcs.is_tracked(repo / "a.md", repo) is False

    def test_committed_file_is_tracked(self, repo):
        target = repo / "a.md"
        target.write_text("x")
        vcs.commit_file(target, "add", repo)
        assert vcs.is_tracked(target, repo) is True


class TestCommitTime:
    def test_returns_first_commit_time(self, repo):
        """Capture-to-commit measures when the artifact ARRIVED, so a later
        edit must not move the timestamp."""
        target = repo / "intent.md"
        target.write_text("v1\n")
        vcs.commit_file(target, "add", repo)
        first = vcs.file_commit_time(target, repo)

        target.write_text("v2\n")
        vcs.commit_file(target, "edit", repo)

        assert vcs.file_commit_time(target, repo) == first

    def test_none_for_uncommitted_file(self, repo):
        (repo / "a.md").write_text("x")
        assert vcs.file_commit_time(repo / "a.md", repo) is None

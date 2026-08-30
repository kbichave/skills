"""Thin git wrapper for publishing intents.

Every function is non-raising and returns a result object, following
`beads_sync.py`'s convention that a git failure is non-fatal — the artifact
already exists on disk, and a missing commit must never lose it.

Scope is deliberately narrow. This stages and commits ONE named file. It never
pushes, never adds `-A`, never amends, and never resolves a conflict. Publishing
into the user's working tree is already a departure from the plugin's
"session state stays outside the repo" invariant, so it stays as small as it can
be.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT_SECONDS = 15
UNKNOWN_AUTHOR = "unknown"


@dataclass(frozen=True, slots=True)
class GitResult:
    ok: bool
    stdout: str = ""
    error: str = ""


def git_available() -> bool:
    return shutil.which("git") is not None


def _run(args: list[str], cwd: Path) -> GitResult:
    if not git_available():
        return GitResult(False, error="git is not on PATH")
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return GitResult(False, error=str(exc))
    if proc.returncode != 0:
        return GitResult(False, stdout=proc.stdout.strip(), error=proc.stderr.strip())
    return GitResult(True, stdout=proc.stdout.strip())


def is_repo(cwd: Path) -> bool:
    return _run(["rev-parse", "--is-inside-work-tree"], cwd).stdout == "true"


def repo_root(cwd: Path) -> Path | None:
    result = _run(["rev-parse", "--show-toplevel"], cwd)
    return Path(result.stdout) if result.ok and result.stdout else None


def resolve_author(cwd: Path, *, explicit: str | None = None) -> str:
    """`--author` always wins. Then git config, then "unknown".

    Never blocks and never authenticates. `git config user.email` is a claim,
    not an identity — in CI it is a bot and on a shared machine it may be stale.
    Treat the result as an attestation.
    """
    if explicit and explicit.strip():
        return explicit.strip()
    for key in ("user.email", "user.name"):
        result = _run(["config", "--get", key], cwd)
        if result.ok and result.stdout:
            return result.stdout
    return UNKNOWN_AUTHOR


def is_tracked(path: Path, cwd: Path) -> bool:
    return _run(["ls-files", "--error-unmatch", str(path)], cwd).ok


def has_staged_changes(cwd: Path) -> bool:
    return not _run(["diff", "--cached", "--quiet"], cwd).ok


def stage_file(path: Path, cwd: Path) -> GitResult:
    """Stage exactly one path. Never `git add -A`, which is how a credential
    file ends up in a commit nobody reviewed."""
    return _run(["add", "--", str(path)], cwd)


def commit_file(path: Path, message: str, cwd: Path) -> GitResult:
    """Stage one file and commit only that file.

    Uses a pathspec on `commit` so anything else the user had staged is left
    alone. Callers must confirm with the user before calling this: writing to
    the user's git history is a side effect they have to opt into.
    """
    staged = stage_file(path, cwd)
    if not staged.ok:
        return staged
    return _run(["commit", "-m", message, "--", str(path)], cwd)


def file_commit_time(path: Path, cwd: Path) -> str | None:
    """Author date of the commit that introduced the path, ISO 8601.

    This is what makes "time from conversation to committed artifact"
    measurable, so it reads the FIRST commit touching the file, not the last.
    """
    result = _run(
        ["log", "--diff-filter=A", "--follow", "--format=%aI", "--", str(path)], cwd
    )
    if not result.ok or not result.stdout:
        return None
    return result.stdout.splitlines()[-1].strip()

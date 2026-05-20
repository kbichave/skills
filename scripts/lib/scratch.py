"""Throwaway scratch artifacts for `/deep` sessions.

Pattern (adopted from matt-pocock/skills `prototype`):
- Scratch artifacts are clearly marked as such (header comment).
- They live under `{planning_dir}/scratch/` so they are easy to find,
  easy to ignore in commits, and easy to clean up.
- Each artifact declares its `delete_after` predicate so cleanup is
  unambiguous.

Use this for:
- Research notes that informed a finding but should not survive the session
- Throwaway prototype scripts validating an approach before plan-writing
- Reviewer drafts before the final review is written

Do NOT use this for:
- Anything referenced by `claude-plan.md` / `claude-spec.md` / `findings/`
- Anything that would be useful to a future `/deep` session
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SCRATCH_DIRNAME = "scratch"

# Valid `delete_after` values. Cleanup interprets these in order of strictness.
DELETE_AFTER_VALUES = ("step", "mode-complete", "session-end")


@dataclass(frozen=True)
class ScratchArtifact:
    """One throwaway artifact + its disposal contract."""
    path: Path
    delete_after: str
    created_at: str


def _validate_delete_after(delete_after: str) -> None:
    if delete_after not in DELETE_AFTER_VALUES:
        raise ValueError(
            f"delete_after must be one of {DELETE_AFTER_VALUES}, got {delete_after!r}"
        )


def _header(name: str, delete_after: str) -> str:
    """Build the THROWAWAY header that goes at the top of every artifact.

    Distinguishes scratch files from durable artifacts at a glance and
    survives accidental copy-paste into the wrong place.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (
        f"<!-- THROWAWAY: delete-after={delete_after} created={now} name={name} -->\n"
        f"> ⚠️ Scratch artifact. Auto-deleted when the mode finishes. Do not link from durable docs.\n\n"
    )


def write_scratch_artifact(
    planning_dir: Path,
    name: str,
    content: str,
    *,
    delete_after: str = "mode-complete",
) -> ScratchArtifact:
    """Write `content` to `{planning_dir}/scratch/{name}` with a THROWAWAY header.

    `name` should be a filename (e.g. `"oauth-research-notes.md"`), not a path.
    `delete_after` controls when cleanup_scratch() will remove it.

    Idempotent at the path level — same name overwrites. Returns the artifact
    record (path, delete_after, created_at).
    """
    _validate_delete_after(delete_after)
    # Reject path traversal: names must not contain separators
    if "/" in name or "\\" in name or name in {"", ".", ".."}:
        raise ValueError(f"name must be a flat filename, got {name!r}")

    scratch_dir = planning_dir / SCRATCH_DIRNAME
    scratch_dir.mkdir(parents=True, exist_ok=True)

    path = scratch_dir / name
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(_header(name, delete_after) + content, encoding="utf-8")
    return ScratchArtifact(path=path, delete_after=delete_after, created_at=now)


_HEADER_RE = re.compile(
    r"<!--\s*THROWAWAY:\s*delete-after=([a-z\-]+)\s+created=([^\s]+)\s+name=([^\s>]+)\s*-->"
)


def list_scratch_artifacts(planning_dir: Path) -> list[ScratchArtifact]:
    """Enumerate scratch artifacts under `{planning_dir}/scratch/`.

    Reads each file's header to recover its `delete_after`. Files lacking a
    THROWAWAY header are treated as `mode-complete` (the strictest default)
    so they don't accumulate forever.
    """
    scratch_dir = planning_dir / SCRATCH_DIRNAME
    if not scratch_dir.exists():
        return []
    artifacts: list[ScratchArtifact] = []
    for entry in sorted(scratch_dir.iterdir()):
        if not entry.is_file():
            continue
        try:
            head = entry.read_text(encoding="utf-8", errors="replace").splitlines()[:2]
        except OSError:
            continue
        match = _HEADER_RE.search("\n".join(head)) if head else None
        if match:
            delete_after, created, _ = match.groups()
        else:
            delete_after, created = "mode-complete", ""
        artifacts.append(
            ScratchArtifact(path=entry, delete_after=delete_after, created_at=created)
        )
    return artifacts


def cleanup_scratch(
    planning_dir: Path,
    *,
    trigger: str,
) -> list[Path]:
    """Remove scratch artifacts whose `delete_after` matches `trigger`.

    `trigger` is one of DELETE_AFTER_VALUES — pass the strictest applicable
    value at each lifecycle point:
    - `"step"` — between workflow steps (removes step-scoped scratch only)
    - `"mode-complete"` — at output-summary / final-verification (removes
      step + mode-complete scratch)
    - `"session-end"` — removes everything, including session-scoped scratch

    Returns the list of removed paths. If the scratch directory becomes
    empty after cleanup, removes it too.
    """
    _validate_delete_after(trigger)
    # Inclusion: a stricter trigger sweeps all lighter retention levels too
    trigger_index = DELETE_AFTER_VALUES.index(trigger)
    sweep_set = set(DELETE_AFTER_VALUES[: trigger_index + 1])

    removed: list[Path] = []
    for artifact in list_scratch_artifacts(planning_dir):
        if artifact.delete_after in sweep_set:
            try:
                artifact.path.unlink()
                removed.append(artifact.path)
            except OSError:
                pass

    scratch_dir = planning_dir / SCRATCH_DIRNAME
    if scratch_dir.exists() and not any(scratch_dir.iterdir()):
        try:
            shutil.rmtree(scratch_dir)
        except OSError:
            pass

    return removed

"""Obsidian vault integration for long-lived knowledge.

Resolves the vault path, creates a skeleton on first use, and provides
helpers for writing curated artifacts (glossary terms, ADRs, findings)
in Obsidian-flavored markdown.

Vault resolution order:
1. ``$DEEP_OBSIDIAN_VAULT`` if set and the path exists.
2. ``~/Obsidian/deep-plan/`` if it already exists.
3. Otherwise the caller is expected to prompt the user for consent
   (see :func:`should_prompt_for_creation`) and then call
   :func:`ensure_vault_skeleton` with the chosen path.

The module is stdlib-only so it can run in any deep-plan invocation.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VAULT = Path.home() / "Obsidian" / "deep-plan"
GLOBAL_GLOSSARY_DIR = Path.home() / ".claude" / "glossary"


@dataclass(frozen=True)
class VaultStatus:
    """Result of resolving the vault.

    Attributes:
        path: The resolved vault path, or ``None`` when no vault is
            configured and creation has not yet been confirmed.
        exists: ``True`` if the vault directory already exists on disk.
        source: One of ``"env"``, ``"default"``, or ``"none"`` indicating
            how the path was selected.
    """

    path: Path | None
    exists: bool
    source: str


def resolve_vault_path() -> VaultStatus:
    """Locate the active vault without creating anything.

    Returns:
        :class:`VaultStatus` describing the current vault situation.
    """

    env_value = os.environ.get("DEEP_OBSIDIAN_VAULT", "").strip()
    if env_value:
        candidate = Path(env_value).expanduser()
        return VaultStatus(path=candidate, exists=candidate.is_dir(), source="env")
    if DEFAULT_VAULT.is_dir():
        return VaultStatus(path=DEFAULT_VAULT, exists=True, source="default")
    return VaultStatus(path=None, exists=False, source="none")


def should_prompt_for_creation(status: VaultStatus) -> bool:
    """Return ``True`` when the caller should ask the user before creating
    a fresh vault skeleton.

    Prompting happens only when no vault is configured at all. Callers
    that already have a vault (env or default) should not re-prompt.
    """

    return status.source == "none"


def ensure_vault_skeleton(vault: Path) -> Path:
    """Create the directory tree expected by deep-plan inside ``vault``.

    Idempotent: existing files and directories are left untouched. Returns
    the resolved absolute vault path.
    """

    vault = vault.expanduser().resolve()
    subdirs = [
        vault / ".obsidian",
        vault / "projects",
        vault / "glossary",
        vault / "adrs",
        vault / "findings",
    ]
    for sub in subdirs:
        sub.mkdir(parents=True, exist_ok=True)

    readme = vault / "README.md"
    if not readme.exists():
        readme.write_text(_README_BODY, encoding="utf-8")

    index = vault / "_index.md"
    if not index.exists():
        index.write_text(_INDEX_BODY, encoding="utf-8")

    obsidian_config = vault / ".obsidian" / "app.json"
    if not obsidian_config.exists():
        obsidian_config.write_text("{}\n", encoding="utf-8")

    return vault


def slugify_project(project_path: Path) -> str:
    """Convert a project directory into a stable filesystem-safe slug.

    The slug is the lowercased basename with any non-alphanumeric
    characters collapsed to single hyphens. Empty results fall back to
    ``"project"`` so that downstream paths never contain bare separators.
    """

    name = project_path.expanduser().resolve().name or "project"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "project"


def project_dir(vault: Path, project_path: Path) -> Path:
    """Return the per-project notes directory inside ``vault``.

    Creates the directory if missing.
    """

    target = vault / "projects" / slugify_project(project_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def glossary_dir(vault: Path, project_path: Path) -> Path:
    """Return the per-project glossary directory inside ``vault``."""

    target = vault / "glossary" / slugify_project(project_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def adrs_dir(vault: Path, project_path: Path) -> Path:
    """Return the per-project ADR directory inside ``vault``."""

    target = vault / "adrs" / slugify_project(project_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def findings_dir(vault: Path, project_path: Path) -> Path:
    """Return the per-project findings directory inside ``vault``."""

    target = vault / "findings" / slugify_project(project_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


_README_BODY = """# deep-plan vault

This vault is the long-lived knowledge store for the
[deep](https://github.com/kbichave/skills)
plugin.

It is created the first time a `/deep` workflow needs to persist
knowledge across sessions. You can move or rename it; point the
`DEEP_OBSIDIAN_VAULT` environment variable at the new location to keep
deep-plan in sync.

## Layout

- `projects/<slug>/` — per-project notes, links into the codebase
- `glossary/<slug>/` — ubiquitous-language terms scoped to a project
- `glossary/_global/` — terms promoted across projects
- `adrs/<slug>/` — architecture decision records produced during plan/implement
- `findings/<slug>/` — curated discovery output worth keeping

## How content lands here

A `vault-curator` subagent runs at the end of each `/deep` mode and
decides which session artifacts deserve long-lived storage. Ephemeral
files (plan files, .deepstate JSON, raw transcripts) stay in the
plugin's session directory.
"""


_INDEX_BODY = """# Map of Content

Top-level entry point for the vault.

- [[projects/]] — per-project notes
- [[glossary/]] — ubiquitous-language terms
- [[adrs/]] — architecture decision records
- [[findings/]] — curated discovery output

This file is created automatically by deep-plan and is safe to edit.
"""

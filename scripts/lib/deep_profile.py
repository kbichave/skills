"""Load the deployment profile: the facts about one organization's warehouse.

The review panel's warehouse tier and `dq-investigate` need to know things no
repo states: which database is production, how CI names a pull request's build
schema, where the knowledge space lives, which check system is in use, which
columns hold personal data. Those facts identify the organization, so they
never go in this plugin's tracked files. They live in a TOML file under
`~/.claude/deep/profiles/`, outside every repo.

Resolution, first hit wins:

1. `$DEEP_PROFILE` naming a file path, or a profile name under the profiles dir.
2. The profile whose `match_remotes` entry is a substring of the target repo's
   `origin` URL.

No profile is a normal state, not an error: every caller degrades to the
generic behavior and says so in one line.
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KNOWLEDGE_TYPES = frozenset(
    {"confluence", "semantic_layer", "knowledge_graph", "catalog", "repo_docs"}
)

_TOP_LEVEL_KEYS = frozenset(
    {
        "name", "match_remotes", "environments", "layers", "ci_schema_pattern",
        "warehouse", "knowledge_sources", "check_systems", "business_units",
        "pii_column_patterns", "source_aliases", "checks",
    }
)


class ProfileError(ValueError):
    """The profile file exists but cannot be used as written."""


@dataclass(frozen=True)
class Profile:
    name: str
    path: Path
    data: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"name": self.name, "path": str(self.path), **self.data}


def profiles_dir() -> Path:
    """`~/.claude/deep/profiles`, honoring `$DEEP_STATE_HOME` like session_paths."""
    home = Path(os.environ.get("DEEP_STATE_HOME") or Path.home() / ".claude")
    return home / "deep" / "profiles"


def _misplaced(data: dict) -> list[str]:
    """Top-level keys that TOML nested under a table because they came after
    its header. The file parses, so without this check the key is silently lost."""
    tables = [(k, v) for k, v in data.items() if isinstance(v, dict)]
    tables += [("knowledge_sources", s) for s in data.get("knowledge_sources", [])
               if isinstance(s, dict)]
    return [
        f"{key!r} is nested under [{table}]; move it above the first table header"
        for table, body in tables
        for key in body
        if key in _TOP_LEVEL_KEYS
    ]


def validate(data: dict, path: Path) -> list[str]:
    """Return problems with a parsed profile. Empty list means usable."""
    problems = [f"unknown key {k!r}" for k in sorted(set(data) - _TOP_LEVEL_KEYS)]
    problems += _misplaced(data)
    for list_key in ("match_remotes", "check_systems", "business_units",
                     "pii_column_patterns"):
        value = data.get(list_key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            problems.append(f"{list_key} must be a list of strings")
    for source in data.get("knowledge_sources", []):
        kind = source.get("type") if isinstance(source, dict) else None
        if kind not in KNOWLEDGE_TYPES:
            problems.append(f"knowledge_sources type {kind!r} not in {sorted(KNOWLEDGE_TYPES)}")
    warehouse = data.get("warehouse", {})
    if not isinstance(warehouse, dict):
        problems.append("warehouse must be a table")
    return problems


def load_file(path: Path) -> Profile:
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f"{path}: {exc}") from exc
    problems = validate(data, path)
    if problems:
        raise ProfileError(f"{path}: " + "; ".join(problems))
    return Profile(name=data.get("name") or path.stem, path=path, data=data)


def origin_url(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def _from_env(env_value: str) -> Profile | None:
    candidate = Path(env_value).expanduser()
    if candidate.suffix != ".toml":
        candidate = profiles_dir() / f"{env_value}.toml"
    if not candidate.is_file():
        raise ProfileError(f"DEEP_PROFILE={env_value!r} names no profile file")
    return load_file(candidate)


def normalize_remote(url: str) -> str:
    """`git@host:org/repo.git` and `https://host/org/repo.git` both become
    `host/org/repo.git`, so one `match_remotes` entry covers either form."""
    url = re.sub(r"^[a-z+]+://(?:[^@/]+@)?", "", url.strip())
    return re.sub(r"^[^@/]+@([^:/]+):", r"\1/", url)


def _from_remote(repo: Path) -> Profile | None:
    url = normalize_remote(origin_url(repo))
    directory = profiles_dir()
    if not url or not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.toml")):
        profile = load_file(path)
        if any(m and m in url for m in profile.data.get("match_remotes", [])):
            return profile
    return None


def resolve(repo: Path | None = None) -> Profile | None:
    """The active profile for `repo` (default cwd), or None when there is none."""
    env_value = os.environ.get("DEEP_PROFILE", "").strip()
    if env_value:
        return _from_env(env_value)
    return _from_remote(repo or Path.cwd())

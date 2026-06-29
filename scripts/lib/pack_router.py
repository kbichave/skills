"""Resolve which quality rule-packs apply to a target repository.

This is the net-new resolver called for from the quality-pipeline plan
(``docs/quality-pipeline-plan.md`` §4, decision D2). It is **not** the
``skill-router`` subagent: that routes Claude Code *skills* by keyword and
inspects the plugin install dirs. This module inspects the *target* repository
that ``/deep`` operates on and decides which rule-packs are active.

Pipeline split:

* ``detect_signals`` — read the target repo (and, at plan time when there is no
  diff yet, the spec text) into a :class:`TargetSignals`.
* ``resolve_packs`` — match those signals against each pack's ``applies_when``
  frontmatter and return the active set with a per-pack reason.

Matching model:

* ``core`` is always active.
* ``languages`` is an *eligibility filter* — a pack is eligible only if its
  languages intersect the target's (a pack with no ``languages`` key, or a
  target with no detected language, passes the filter). This prevents a
  TypeScript frontend from activating the backend ``service`` pack just because
  both use TypeScript.
* A pack *activates* when, being eligible, it matches on any of
  ``project_types`` / ``changed_globs`` / ``task_types``.
* Unknown signals fall back to ``core`` only; the language filter is permissive
  so packs can still activate on project-type/task at plan time.

Stdlib only (no PyYAML). The frontmatter parser handles the controlled subset
used by ``references/quality/*/index.md``. Contract is pinned by
``tests/test_pack_router.py``.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


QUALITY_MODE_ENV = "DEEP_QUALITY_MODE"
_VALID_MODES = ("active", "legacy")

_EXT_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
}

_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".beads", ".mypy_cache"}

# manifest dependency substrings → project types
_BACKEND_DEPS = ("fastapi", "flask", "django", "starlette", "uvicorn", "express", "fastify", "nestjs", "@nestjs", "koa")
_FRONTEND_DEPS = ("react", "react-dom", "vue", "svelte", "next", "@angular")

# spec keyword → signal inference (lowercased substring match)
_SPEC_LANG = {
    "python": ("python", "fastapi", "django", "flask", "pytest"),
    "typescript": ("typescript", "react", "node", "next.js", "nestjs"),
    "go": ("golang", " go ", "goroutine"),
}
_SPEC_PROJECT = {
    "backend": ("backend", "service", "api", "endpoint", "fastapi", "rest", "microservice"),
    "api": ("api", "endpoint", "rest", "graphql"),
    "frontend": ("frontend", "ui", "button", "contrast", "component", "page", "css", "react"),
    "library": ("library", "sdk", "package", "publish"),
    "infra": ("docker", "terraform", "kubernetes", "k8s", "helm", "infra"),
    "llm": ("prompt", "agent", "llm", "tool call", "tool-call"),
}
_SPEC_TASK = {
    "add-endpoint": ("endpoint", "route", "handler"),
    "change-api": ("api", "contract", "response shape"),
    "add-migration": ("migration", "schema", "database table"),
    "ui": ("ui", "button", "contrast", "layout", "component", "style"),
    "accessibility": ("accessib", "a11y", "wcag", "screen reader"),
    "add-dependency": ("dependency", "upgrade", "bump", "package"),
    "perf": ("performance", "optimize", "slow", "latency", "throughput"),
    "agent": ("agent", "tool call", "tool-call"),
    "change-prompt": ("prompt",),
    "infra": ("docker", "terraform", "kubernetes", "k8s", "deploy"),
    "release": ("release", "publish", "semver"),
}


@dataclass(frozen=True)
class TargetSignals:
    """Detected facts about the target repo, used to match ``applies_when``."""

    languages: tuple[str, ...] = ()
    project_types: tuple[str, ...] = ()
    changed_globs: tuple[str, ...] = ()
    task_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class Resolution:
    """Result of pack resolution: the active set plus why each pack is on."""

    active_packs: tuple[str, ...]
    reasons: dict[str, str] = field(default_factory=dict)


def resolve_quality_mode(cli_value: str | None = None, env: dict[str, str] | None = None) -> str:
    """Return ``"active"`` or ``"legacy"``.

    Precedence: explicit ``cli_value`` (e.g. ``--quality=legacy``) over the
    ``DEEP_QUALITY_MODE`` env var over the default ``"active"``. Invalid values
    raise ``ValueError`` so a typo fails loud rather than silently disabling the
    quality system.
    """
    import os

    raw = cli_value if cli_value is not None else (env or os.environ).get(QUALITY_MODE_ENV)
    if raw is None or raw == "":
        return "active"
    mode = raw.strip().lower()
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid quality mode {raw!r}; expected one of {_VALID_MODES}")
    return mode


# --- frontmatter parsing --------------------------------------------------


def _parse_scalar(value: str) -> bool | list[str] | str:
    v = value.strip()
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
    return v.strip('"').strip("'")


def _as_list(value: object) -> list[str]:
    """Coerce a parsed frontmatter value to a list of strings (else empty)."""
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _parse_frontmatter(text: str) -> dict[str, object]:
    """Parse the leading ``--- ... ---`` block (controlled one-level-nested subset)."""
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    data: dict[str, object] = {}
    current_block: dict[str, object] | None = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(":")
        key = key.strip()
        if indent == 0:
            if val.strip() == "":
                block: dict[str, object] = {}
                data[key] = block
                current_block = block
            else:
                data[key] = _parse_scalar(val)
                current_block = None
        elif current_block is not None:
            current_block[key] = _parse_scalar(val)
    return data


def load_pack(index_path: Path) -> dict[str, object]:
    """Load a pack's frontmatter: ``{name, applies_when, provides_rules}``."""
    fm = _parse_frontmatter(index_path.read_text(encoding="utf-8"))
    applies = fm.get("applies_when", {})
    return {
        "name": fm.get("pack", index_path.parent.name),
        "applies_when": applies if isinstance(applies, dict) else {},
        "provides_rules": _as_list(fm.get("provides_rules", [])),
    }


def discover_packs(packs_dir: Path) -> list[dict[str, object]]:
    """Load every ``<pack>/index.md`` under ``packs_dir`` (sorted by name)."""
    return [load_pack(idx) for idx in sorted(packs_dir.glob("*/index.md"))]


# --- detection ------------------------------------------------------------


def _detect_languages(target_root: Path) -> set[str]:
    langs: set[str] = set()
    for path in target_root.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            lang = _EXT_LANG.get(path.suffix)
            if lang:
                langs.add(lang)
    return langs


def _read_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").lower()
    except (OSError, UnicodeDecodeError):
        return ""


def _detect_project_types(target_root: Path, languages: set[str]) -> set[str]:
    types: set[str] = set()
    pyproject = _read_if_exists(target_root / "pyproject.toml") + _read_if_exists(target_root / "requirements.txt")
    pkg = _read_if_exists(target_root / "package.json")
    manifest = pyproject + "\n" + pkg
    if any(dep in manifest for dep in _BACKEND_DEPS):
        types.update(("backend", "api"))
    if any(dep in pkg for dep in _FRONTEND_DEPS):
        types.add("frontend")
    if (target_root / "go.mod").exists():
        types.add("backend")
    # directory markers
    for marker, ptype in (("api", "backend"), ("routes", "backend"), ("controllers", "backend"), ("components", "frontend")):
        if any(p.name == marker and p.is_dir() for p in target_root.rglob(marker) if not any(s in p.parts for s in _SKIP_DIRS)):
            types.add(ptype)
            if ptype == "backend":
                types.add("api")
    return types


def _infer_from_spec(spec_text: str) -> tuple[set[str], set[str], set[str]]:
    text = (spec_text or "").lower()
    langs = {lang for lang, kws in _SPEC_LANG.items() if any(k in text for k in kws)}
    projects = {p for p, kws in _SPEC_PROJECT.items() if any(k in text for k in kws)}
    tasks = {t for t, kws in _SPEC_TASK.items() if any(k in text for k in kws)}
    return langs, projects, tasks


def _git_changed(target_root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(target_root), "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            return [line.strip() for line in out.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    return []


def detect_signals(
    target_root: Path,
    *,
    spec_text: str | None = None,
    changed: list[str] | None = None,
) -> TargetSignals:
    """Inspect the target repo (+ spec at plan time) → :class:`TargetSignals`.

    Repo signals (file extensions, manifests, dir markers, git diff) are the
    primary source. When the repo is empty/greenfield, spec-derived inference
    fills in languages/project-types/tasks (decision Q9). Spec also augments
    task types, which are hard to read off files alone.
    """
    target_root = Path(target_root)
    languages = _detect_languages(target_root)
    project_types = _detect_project_types(target_root, languages)

    changed_globs = list(changed) if changed is not None else _git_changed(target_root)

    spec_langs, spec_projects, spec_tasks = _infer_from_spec(spec_text or "")
    task_types = set(spec_tasks)

    # Greenfield / thin repo: lean on the spec for languages + project types.
    if not languages:
        languages = spec_langs
    if not project_types:
        project_types = spec_projects

    return TargetSignals(
        languages=tuple(sorted(languages)),
        project_types=tuple(sorted(project_types)),
        changed_globs=tuple(changed_globs),
        task_types=tuple(sorted(task_types)),
    )


# --- resolution -----------------------------------------------------------


def _is_eligible(pack_langs: object, target_langs: tuple[str, ...]) -> bool:
    langs = _as_list(pack_langs)
    if not langs or not target_langs:
        return True
    return bool(set(langs) & set(target_langs))


def _activation_reason(applies_when: dict[str, object], signals: TargetSignals) -> str | None:
    proj = set(_as_list(applies_when.get("project_types")))
    if proj & set(signals.project_types):
        return f"project_types {sorted(proj & set(signals.project_types))}"
    tasks = set(_as_list(applies_when.get("task_types")))
    if tasks & set(signals.task_types):
        return f"task_types {sorted(tasks & set(signals.task_types))}"
    for changed in signals.changed_globs:
        for pattern in _as_list(applies_when.get("changed_globs")):
            if fnmatch.fnmatch(changed, pattern):
                return f"changed_globs {pattern} ~ {changed}"
    return None


def resolve_packs(signals: TargetSignals, packs_dir: Path) -> Resolution:
    """Match ``signals`` against pack ``applies_when`` frontmatter.

    Returns the active set (always including ``core``) with a per-pack reason.
    """
    packs_dir = Path(packs_dir)
    active: list[str] = []
    reasons: dict[str, str] = {}

    for pack in discover_packs(packs_dir):
        name = str(pack["name"])
        applies = pack["applies_when"]
        applies = applies if isinstance(applies, dict) else {}
        if applies.get("always") is True or name == "core":
            active.append(name)
            reasons[name] = "always-on"
            continue
        if not _is_eligible(applies.get("languages"), signals.languages):
            continue
        reason = _activation_reason(applies, signals)
        if reason is not None:
            active.append(name)
            reasons[name] = reason

    if "core" not in active:
        active.insert(0, "core")
        reasons.setdefault("core", "always-on")

    return Resolution(active_packs=tuple(active), reasons=reasons)

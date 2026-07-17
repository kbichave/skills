"""Enumerate Claude Code skills installed on the local machine.

Used by the ``skill-router`` subagent to decide whether an existing
skill should be invoked at a given hook point during ``/deep`` execution.

Discovery scans:

* ``~/.claude/skills/`` — user-level skills
* ``~/.claude/plugins/cache/*/skills/`` — plugin-installed skills
* ``<project>/.claude/skills/`` — project-scoped skills

Each ``SKILL.md`` is parsed for its YAML frontmatter (``name``,
``description`` are required; everything else is optional and forwarded
verbatim).

Stdlib only. The parser is intentionally permissive — it skips files
whose frontmatter is malformed instead of raising.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


HIGH_CONFIDENCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "claude-api": ("anthropic", "claude api", "anthropic sdk"),
    "code-review": ("review", "pre-commit", "code quality"),
    "security-review": ("security", "vulnerability", "secrets"),
    "humanizer": ("draft", "prose", "rephrase", "in my style"),
    "internal-comms": ("status report", "leadership update", "incident report"),
    "pptx": (".pptx", "slide deck", "presentation"),
    "pptx-gp-template": ("gp slides", "gp template", "global partners deck"),
    "mcp-builder": ("mcp server", "model context protocol"),
    "pr-reply": ("pr comment", "review comment", "reply"),
    "karpathy-guidelines": ("anti-pattern", "surgical edit", "verifiable success"),
    "simplify": ("simplify", "refactor for clarity", "reuse"),
    "browser-automation:Browser-Automation": ("browse", "navigate to", "screenshot"),
    "caveman:caveman-commit": ("commit message", "/commit"),
}


SIDE_EFFECT_SKILLS: frozenset[str] = frozenset(
    {
        "pr-reply",
        "schedule",
        "loop",
        "internal-comms",
        "pptx",
        "pptx-gp-template",
        "browser-automation:Browser-Automation",
    }
)


@dataclass(frozen=True)
class SkillEntry:
    """A single skill discovered on disk."""

    name: str
    description: str
    source: str
    path: Path
    triggers: tuple[str, ...] = ()


@dataclass
class RouterMatch:
    """A skill considered by the router for a given context."""

    skill: SkillEntry
    confidence: str  # "high", "medium", "low"
    reason: str


def enumerate_skills(*, project_root: Path | None = None) -> list[SkillEntry]:
    """Return every skill discoverable on disk, deduplicated by name.

    When the same skill name appears in multiple locations the entry
    closest to the project (project > plugin > user) wins, matching
    Claude Code's own resolution order.
    """

    roots: list[tuple[Path, str]] = []
    if project_root is not None:
        proj_skills = (project_root / ".claude" / "skills").expanduser()
        if proj_skills.is_dir():
            roots.append((proj_skills, "project"))

    plugins_root = (Path.home() / ".claude" / "plugins" / "cache").expanduser()
    if plugins_root.is_dir():
        for plugin_dir in sorted(plugins_root.glob("*/")):
            for version_dir in sorted(plugin_dir.glob("*/")):
                skills_dir = version_dir / "skills"
                if skills_dir.is_dir():
                    roots.append((skills_dir, f"plugin:{plugin_dir.name}"))

    user_skills = (Path.home() / ".claude" / "skills").expanduser()
    if user_skills.is_dir():
        roots.append((user_skills, "user"))

    seen: dict[str, SkillEntry] = {}
    for root, source in roots:
        for skill_md in sorted(root.rglob("SKILL.md")):
            entry = parse_skill_md(skill_md, source=source)
            if entry is None:
                continue
            seen.setdefault(entry.name, entry)
    return list(seen.values())


def parse_skill_md(path: Path, *, source: str = "unknown") -> SkillEntry | None:
    """Parse a ``SKILL.md`` file. Returns ``None`` on malformed input."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.match(r"^---\n(?P<fm>.*?)\n---\n", text, re.DOTALL)
    if not match:
        return None
    fields = _parse_frontmatter(match.group("fm"))
    name = fields.get("name", "").strip()
    if not name:
        return None
    description = fields.get("description", "").strip()
    triggers = tuple(t.strip() for t in fields.get("triggers", "").split(",") if t.strip())
    return SkillEntry(
        name=name,
        description=description,
        source=source,
        path=path,
        triggers=triggers,
    )


def _parse_frontmatter(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^(?P<key>[A-Za-z0-9_]+):\s*(?P<value>.*)$", line)
        if m:
            current_key = m.group("key").strip()
            out[current_key] = m.group("value").strip()
        elif current_key is not None and line.startswith((" ", "\t")):
            out[current_key] = (out[current_key] + " " + line.strip()).strip()
    return out


def filter_relevant(
    entries: list[SkillEntry],
    *,
    context: dict,
    auto_mode: bool = False,
    mute_list: frozenset[str] = frozenset(),
) -> list[RouterMatch]:
    """Score each candidate skill against the supplied execution context.

    ``context`` is a free-form dict produced by the calling ``/deep``
    step. The keys recognised here are:

    * ``files`` — list of paths touched in this step
    * ``imports`` — list of module names imported in those files
    * ``output_kind`` — one of ``code``, ``prose``, ``commit``, ``pr_comment``
    * ``current_step`` — name of the workflow step
    * ``mode`` — ``discovery`` | ``plan`` | ``implement`` | ``auto``

    Returns a list of :class:`RouterMatch` ordered by descending
    confidence. Side-effect skills are downgraded to ``medium`` even
    when keywords match because the router never auto-invokes them.
    """

    matches: list[RouterMatch] = []
    haystack = _build_haystack(context)
    for entry in entries:
        if entry.name in mute_list:
            continue
        if entry.name in {"deep", "deep:deep"}:
            continue
        confidence, reason = _score(entry, haystack, context)
        if confidence == "skip":
            continue
        if entry.name in SIDE_EFFECT_SKILLS:
            confidence = "medium" if confidence == "high" else confidence
            reason = f"side-effect skill, never auto: {reason}"
        if auto_mode and confidence != "high":
            continue
        matches.append(RouterMatch(skill=entry, confidence=confidence, reason=reason))
    order = {"high": 0, "medium": 1, "low": 2}
    matches.sort(key=lambda m: (order[m.confidence], m.skill.name))
    return matches


def _build_haystack(context: dict) -> str:
    parts: list[str] = []
    parts.extend(str(p) for p in context.get("files", []))
    parts.extend(str(i) for i in context.get("imports", []))
    parts.append(str(context.get("output_kind", "")))
    parts.append(str(context.get("current_step", "")))
    parts.append(str(context.get("notes", "")))
    return " ".join(parts).lower()


def _score(entry: SkillEntry, haystack: str, context: dict) -> tuple[str, str]:
    keywords = HIGH_CONFIDENCE_KEYWORDS.get(entry.name, ())
    for kw in keywords:
        if kw in haystack:
            return "high", f"matched keyword '{kw}'"

    desc = entry.description.lower()
    output_kind = str(context.get("output_kind", "")).lower()
    if output_kind and output_kind in desc:
        return "medium", f"description mentions output kind '{output_kind}'"
    if any(token in desc for token in haystack.split() if len(token) > 4):
        return "low", "weak description overlap"
    return "skip", "no signal"


def to_dict(match: RouterMatch) -> dict:
    """Serialise a :class:`RouterMatch` for transcript logging."""

    return {
        "skill": match.skill.name,
        "source": match.skill.source,
        "confidence": match.confidence,
        "reason": match.reason,
    }

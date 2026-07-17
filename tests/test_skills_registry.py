"""Tests for scripts/lib/skills_registry.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lib import skills_registry as sr


def _write_skill(root: Path, name: str, description: str, *, triggers: str = "") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    body = ["---", f"name: {name}", f"description: {description}"]
    if triggers:
        body.append(f"triggers: {triggers}")
    body.append("---")
    body.append("")
    body.append("# Body")
    path = skill_dir / "SKILL.md"
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def test_parse_skill_md_returns_none_for_missing_frontmatter(tmp_path):
    bad = tmp_path / "bad" / "SKILL.md"
    bad.parent.mkdir()
    bad.write_text("no frontmatter here", encoding="utf-8")
    assert sr.parse_skill_md(bad) is None


def test_parse_skill_md_parses_simple_frontmatter(tmp_path):
    path = _write_skill(tmp_path, "demo", "Demo skill", triggers="alpha,beta")
    entry = sr.parse_skill_md(path, source="user")
    assert entry is not None
    assert entry.name == "demo"
    assert entry.description == "Demo skill"
    assert entry.triggers == ("alpha", "beta")
    assert entry.source == "user"


def test_filter_relevant_high_match_for_anthropic_import(tmp_path):
    path = _write_skill(tmp_path, "claude-api", "Build, debug Claude API apps")
    entries = [sr.parse_skill_md(path, source="user")]
    matches = sr.filter_relevant(
        entries,
        context={"files": ["src/agents/agent.py"], "imports": ["anthropic"], "output_kind": "code"},
    )
    assert any(m.skill.name == "claude-api" and m.confidence == "high" for m in matches)


def test_filter_relevant_demotes_side_effect_skills(tmp_path):
    path = _write_skill(tmp_path, "pr-reply", "Reply to PR review comments")
    entries = [sr.parse_skill_md(path, source="user")]
    matches = sr.filter_relevant(
        entries,
        context={"output_kind": "pr_comment", "notes": "review comment reply"},
    )
    pr_match = next(m for m in matches if m.skill.name == "pr-reply")
    assert pr_match.confidence == "medium"
    assert "side-effect" in pr_match.reason


def test_filter_relevant_excludes_deep(tmp_path):
    path = _write_skill(tmp_path, "deep", "deep self")
    entries = [sr.parse_skill_md(path, source="plugin:deep")]
    matches = sr.filter_relevant(entries, context={"files": []})
    assert all(m.skill.name != "deep" for m in matches)


def test_filter_relevant_honours_mute_list(tmp_path):
    path = _write_skill(tmp_path, "code-review", "Code review for PRs")
    entries = [sr.parse_skill_md(path, source="user")]
    matches = sr.filter_relevant(
        entries,
        context={"output_kind": "code", "current_step": "pre-commit review"},
        mute_list=frozenset({"code-review"}),
    )
    assert all(m.skill.name != "code-review" for m in matches)


def test_filter_relevant_auto_mode_drops_non_high(tmp_path):
    high = _write_skill(tmp_path, "claude-api", "Build, debug Claude API apps")
    medium = _write_skill(tmp_path, "simplify", "Refactor for clarity")
    entries = [
        sr.parse_skill_md(high, source="user"),
        sr.parse_skill_md(medium, source="user"),
    ]
    matches = sr.filter_relevant(
        entries,
        context={"imports": ["anthropic"], "output_kind": "code", "current_step": "section"},
        auto_mode=True,
    )
    assert {m.skill.name for m in matches} == {"claude-api"}


def test_enumerate_skills_walks_project_dir(tmp_path):
    project = tmp_path / "proj"
    skills_dir = project / ".claude" / "skills"
    _write_skill(skills_dir, "demo-a", "First")
    _write_skill(skills_dir, "demo-b", "Second")
    entries = sr.enumerate_skills(project_root=project)
    names = {e.name for e in entries}
    assert {"demo-a", "demo-b"}.issubset(names)

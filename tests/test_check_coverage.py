"""Tests for scripts/checks/check-coverage.py — spec → sections coverage gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec_path = PLUGIN_ROOT / "scripts" / "checks" / "check-coverage.py"
    spec = importlib.util.spec_from_file_location("check_coverage", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cc():
    return _load_module()


@pytest.fixture
def planning_dir(tmp_path):
    return tmp_path


def _write_spec(planning_dir: Path, items: list[str], heading: str = "Requirements") -> None:
    bullets = "\n".join(f"- {item}" for item in items)
    (planning_dir / "claude-spec.md").write_text(
        f"# Spec\n\n## {heading}\n\n{bullets}\n"
    )


def _write_sections(planning_dir: Path, sections: list[str]) -> None:
    sections_dir = planning_dir / "sections"
    sections_dir.mkdir()
    manifest = "\n".join(sections)
    (sections_dir / "index.md").write_text(
        f"# Sections\n\n```SECTION_MANIFEST\n{manifest}\n```\n"
    )


# ── parse_spec_items ─────────────────────────────────────────────────


class TestParseSpecItems:
    def test_extracts_under_requirements_heading(self, cc):
        text = "# Spec\n\n## Requirements\n\n- OAuth2 login\n- Refresh tokens\n"
        items = cc.parse_spec_items(text, ("Requirements",))
        assert items == ["OAuth2 login", "Refresh tokens"]

    def test_ignores_other_headings(self, cc):
        text = "## Notes\n\n- This is a note\n\n## Requirements\n\n- Real item\n"
        items = cc.parse_spec_items(text, ("Requirements",))
        assert items == ["Real item"]

    def test_case_insensitive_heading(self, cc):
        text = "## REQUIREMENTS\n\n- Item one\n"
        items = cc.parse_spec_items(text, ("Requirements",))
        assert items == ["Item one"]

    def test_multiple_headings(self, cc):
        text = "## Capabilities\n\n- C1\n\n## Acceptance Criteria\n\n- AC1\n"
        items = cc.parse_spec_items(text, ("Capabilities", "Acceptance Criteria"))
        assert "C1" in items
        assert "AC1" in items

    def test_strips_trailing_parenthetical(self, cc):
        text = "## Requirements\n\n- OAuth2 login (Google + GitHub only)\n"
        items = cc.parse_spec_items(text, ("Requirements",))
        assert items == ["OAuth2 login"]

    def test_drops_TODO_notes(self, cc):
        text = "## Requirements\n\n- Real item\n- TODO: figure this out\n"
        items = cc.parse_spec_items(text, ("Requirements",))
        assert items == ["Real item"]


# ── item_matches_section ─────────────────────────────────────────────


class TestItemMatchesSection:
    def test_token_overlap_matches(self, cc):
        # 2 tokens in common (oauth2, login) clears the multi-token threshold
        assert cc.item_matches_section("OAuth2 login flow", "auth-oauth2-login-section")

    def test_no_overlap_doesnt_match(self, cc):
        assert not cc.item_matches_section("OAuth2 login flow", "database-migrations")

    def test_section_body_helps_match(self, cc):
        body = "Implements OAuth2 grant code flow including login redirects."
        assert cc.item_matches_section("login flow", "section-04-auth", body)

    def test_stopwords_dont_count(self, cc):
        # "The system must support users" — all tokens are stopwords; no match expected
        assert not cc.item_matches_section("The system must support users", "data-pipeline")


# ── check_coverage end-to-end ────────────────────────────────────────


class TestCheckCoverage:
    def test_full_coverage_passes(self, cc, planning_dir):
        _write_spec(planning_dir, ["OAuth2 login", "Token refresh"])
        _write_sections(planning_dir, ["section-01-oauth2-login", "section-02-token-refresh"])
        result = cc.check_coverage(planning_dir)
        assert result["passed"] is True
        assert result["missing"] == []
        assert result["total_items"] == 2

    def test_missing_item_fails(self, cc, planning_dir):
        _write_spec(planning_dir, ["OAuth2 login", "Token refresh", "Rate limiting"])
        _write_sections(planning_dir, ["section-01-oauth2-login", "section-02-token-refresh"])
        result = cc.check_coverage(planning_dir)
        assert result["passed"] is False
        assert "Rate limiting" in result["missing"]

    def test_missing_spec_returns_error(self, cc, planning_dir):
        _write_sections(planning_dir, ["section-01"])
        result = cc.check_coverage(planning_dir)
        assert result["passed"] is False
        assert "Spec not found" in result["error"]

    def test_missing_index_returns_error(self, cc, planning_dir):
        _write_spec(planning_dir, ["Item"])
        result = cc.check_coverage(planning_dir)
        assert result["passed"] is False
        assert "Section index not found" in result["error"]

    def test_section_body_used_for_matching(self, cc, planning_dir):
        _write_spec(planning_dir, ["Rate limiting middleware"])
        sections_dir = planning_dir / "sections"
        sections_dir.mkdir()
        (sections_dir / "index.md").write_text(
            "```SECTION_MANIFEST\nsection-03-middleware\n```\n"
        )
        (sections_dir / "section-03-middleware.md").write_text(
            "# Section 3\n\nImplements rate limiting per IP."
        )
        result = cc.check_coverage(planning_dir)
        assert result["passed"] is True

    def test_covered_includes_matched_sections(self, cc, planning_dir):
        _write_spec(planning_dir, ["OAuth2 login"])
        _write_sections(planning_dir, ["section-01-oauth2-login"])
        result = cc.check_coverage(planning_dir)
        assert result["covered"][0]["matched_in"] == ["section-01-oauth2-login"]

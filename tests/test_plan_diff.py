"""Tests for plan-vs-diff alignment.

The property worth defending: it refuses to produce a score it cannot justify.
Real section files largely ignore the `**File:**` convention and mention paths
inline instead, and a mentioned path is not a promise to edit it. A confident
alignment percentage computed from hints is worse than no measurement, because
someone would act on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.plan_diff import (
    MIN_DECLARATION_COVERAGE,
    SectionPaths,
    alignment,
    extract_paths,
    read_sections,
)


def declared_section(*paths: str) -> str:
    return "\n".join(f"**File:** `{p}`\n\nSome prose." for p in paths)


class TestExtraction:
    def test_declared_file_lines(self):
        result = extract_paths("**File:** `src/a.py`\n\n**File:** `src/b.py`")
        assert result.declared == ("src/a.py", "src/b.py")

    def test_deduplicates(self):
        assert extract_paths("**File:** `src/a.py`\n**File:** `src/a.py`").declared == (
            "src/a.py",
        )

    def test_mentioned_paths_from_backticks(self):
        result = extract_paths("Edit `src/orchestrate/trader.py` carefully.")
        assert result.mentioned == ("src/orchestrate/trader.py",)

    def test_mentioned_excludes_prose_and_symbols(self):
        result = extract_paths("Call `build_gate()` with `--quality=legacy` now.")
        assert result.mentioned == ()

    def test_mentioned_excludes_bare_words(self):
        assert extract_paths("The `tracker` object.").mentioned == ()

    def test_mentioned_requires_a_known_suffix(self):
        assert extract_paths("See `src/thing.bin` here.").mentioned == ()

    def test_declared_paths_also_appear_as_mentioned(self):
        """They are backticked, so both extractors see them. Callers use one
        basis or the other, never a union."""
        result = extract_paths("**File:** `src/a.py`")
        assert "src/a.py" in result.mentioned


class TestReadSections:
    def test_skips_the_index(self, tmp_path):
        sections = tmp_path / "sections"
        sections.mkdir()
        (sections / "index.md").write_text("**File:** `src/ignored.py`")
        (sections / "section-01.md").write_text(declared_section("src/a.py"))
        assert [s.section for s in read_sections(sections)] == ["section-01"]

    def test_missing_dir_is_empty(self, tmp_path):
        assert read_sections(tmp_path / "nope") == []


class TestAlignmentScoring:
    def _declared(self, n_declaring: int, n_total: int) -> list[SectionPaths]:
        sections = [
            SectionPaths(section=f"s{i}", declared=(f"src/f{i}.py",))
            for i in range(n_declaring)
        ]
        sections += [
            SectionPaths(section=f"m{i}", mentioned=(f"src/m{i}.py",))
            for i in range(n_total - n_declaring)
        ]
        return sections

    def test_scores_when_declaration_coverage_is_high(self):
        result = alignment(self._declared(4, 4), ["src/f0.py", "src/f1.py"])
        assert result.scored is True
        assert result.basis == "declared"

    def test_refuses_to_score_on_mentions_alone(self):
        """The real-world case: sections mention paths but declare none."""
        result = alignment(self._declared(0, 5), ["src/m0.py"])
        assert result.scored is False
        assert result.score is None
        assert result.basis == "mentioned"

    def test_refusal_explains_itself(self):
        result = alignment(self._declared(1, 5), ["src/m0.py"])
        assert "declare files" in result.note
        assert "hints, not" in result.note

    def test_refusal_still_reports_unplanned(self):
        """The percentage is withheld; the useful list is not."""
        result = alignment(self._declared(0, 3), ["src/surprise.py"])
        assert "src/surprise.py" in result.unplanned

    def test_threshold_boundary_scores(self):
        total = 4
        declaring = int(total * MIN_DECLARATION_COVERAGE)
        assert alignment(self._declared(declaring, total), ["src/f0.py"]).scored is True

    def test_score_is_matched_over_changed(self):
        sections = [SectionPaths(section="s", declared=("a.py", "b.py"))]
        result = alignment(sections, ["a.py", "c.py"])
        assert result.score == 0.5

    def test_identifies_untouched_planned_files(self):
        sections = [SectionPaths(section="s", declared=("a.py", "b.py"))]
        assert alignment(sections, ["a.py"]).untouched == ("b.py",)

    def test_identifies_unplanned_changes(self):
        sections = [SectionPaths(section="s", declared=("a.py",))]
        assert alignment(sections, ["a.py", "sneaky.py"]).unplanned == ("sneaky.py",)

    def test_no_sections_is_not_scored(self):
        result = alignment([], ["a.py"])
        assert result.scored is False and "nothing to compare" in result.note

    def test_no_changes_is_handled(self):
        result = alignment([SectionPaths(section="s", declared=("a.py",))], [])
        assert result.score is None
        assert "No changes detected" in result.note


class TestSerialization:
    def test_to_dict_rounds_coverage(self):
        payload = alignment(
            [SectionPaths(section="s", declared=("a.py",))], ["a.py"]
        ).to_dict()
        assert payload["declaration_coverage"] == 1.0
        assert payload["basis"] == "declared"

"""Tests for the REVIEW.md per-repo policy overlay.

The property that matters most: the nit cap trims what is SHOWN, never what is
FOUND. The panel's exhaustiveness is what makes the verifier's precision math
meaningful and the report file a real audit artifact; capping detection would
trade that away for a formatting preference.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.review_policy import (
    DEFAULT_NIT_CAP,
    DEFAULT_POLICY,
    ReviewPolicy,
    externalize,
    filter_findings,
    is_excluded_path,
    is_excluded_rule,
    load,
    parse,
)


def finding(severity="nit", file="src/a.py", rule_id="ENG-001", **extra):
    return {"severity": severity, "file": file, "rule_id": rule_id, **extra}


class TestParsing:
    def test_exclusions(self):
        policy = parse("## Exclusions\n\n- `**/generated/**`\n- `vendor/**`\n")
        assert policy.excluded_paths == ("**/generated/**", "vendor/**")

    def test_excluded_rules_are_upper_cased(self):
        assert parse("## Excluded rules\n\n- `eng-004`\n").excluded_rules == ("ENG-004",)

    def test_nit_cap_number(self):
        assert parse("## Nit cap\n\n3\n").nit_cap == 3

    def test_nit_cap_none_disables(self):
        assert parse("## Nit cap\n\nnone\n").nit_cap is None

    def test_default_cap_when_absent(self):
        assert parse("## Exclusions\n\n- `a/**`\n").nit_cap == DEFAULT_NIT_CAP

    def test_headings_are_case_insensitive(self):
        assert parse("## EXCLUSIONS\n\n- `a/**`\n").excluded_paths == ("a/**",)

    def test_template_placeholders_are_skipped(self):
        assert parse("## Exclusions\n\n- <your path here>\n").excluded_paths == ()

    def test_empty_document_is_the_default_policy(self):
        policy = parse("")
        assert policy.excluded_paths == () and policy.nit_cap == DEFAULT_NIT_CAP

    def test_unknown_sections_are_ignored(self):
        """Forgiving on purpose: this is hand-edited by a tech lead, and a
        parser that rejects it on a typo just gets the feature switched off."""
        assert parse("## Something Else\n\n- `x`\n").excluded_paths == ()


class TestLoad:
    def test_missing_file_yields_default(self, tmp_path):
        assert load(tmp_path) == DEFAULT_POLICY

    def test_reads_review_md(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text("## Nit cap\n\n2\n")
        assert load(tmp_path).nit_cap == 2

    def test_records_its_source(self, tmp_path):
        (tmp_path / "REVIEW.md").write_text("## Nit cap\n\n2\n")
        assert "REVIEW.md" in load(tmp_path).source


class TestPathExclusion:
    @pytest.mark.parametrize(
        "path,pattern,excluded",
        [
            ("src/generated/api.py", "**/generated/**", True),
            ("generated/api.py", "**/generated/**", True),
            ("src/app.py", "**/generated/**", False),
            ("vendor/lib/x.go", "vendor/**", True),
            ("vendors/lib/x.go", "vendor/**", False),
            ("api.pb.go", "**/*.pb.go", True),
        ],
    )
    def test_matching(self, path, pattern, excluded):
        policy = ReviewPolicy(excluded_paths=(pattern,))
        assert is_excluded_path(path, policy) is excluded


class TestFiltering:
    def test_drops_excluded_paths(self):
        policy = ReviewPolicy(excluded_paths=("**/generated/**",))
        findings = [finding(file="src/generated/a.py"), finding(file="src/b.py")]
        assert [f["file"] for f in filter_findings(findings, policy)] == ["src/b.py"]

    def test_drops_excluded_rules(self):
        policy = ReviewPolicy(excluded_rules=("ENG-004",))
        findings = [finding(rule_id="ENG-004"), finding(rule_id="SEC-001")]
        assert [f["rule_id"] for f in filter_findings(findings, policy)] == ["SEC-001"]

    def test_rule_matching_is_case_insensitive(self):
        policy = ReviewPolicy(excluded_rules=("ENG-004",))
        assert is_excluded_rule("eng-004", policy) is True

    def test_keeps_everything_by_default(self):
        findings = [finding(), finding(file="x.py")]
        assert len(filter_findings(findings, DEFAULT_POLICY)) == 2


class TestExternalization:
    def test_caps_nits(self):
        result = externalize([finding() for _ in range(9)], ReviewPolicy(nit_cap=3))
        assert len(result.shown) == 3
        assert result.withheld == 6

    def test_never_caps_blocking_or_important(self):
        """Volume drowns signal for nits. A withheld blocking finding is a bug
        report nobody reads."""
        findings = [finding(severity="blocking") for _ in range(4)]
        findings += [finding(severity="important") for _ in range(4)]
        result = externalize(findings, ReviewPolicy(nit_cap=1))
        assert len(result.shown) == 8
        assert result.withheld == 0

    def test_mixed_severities_keep_all_non_nits(self):
        findings = [finding(severity="blocking"), *[finding() for _ in range(5)]]
        result = externalize(findings, ReviewPolicy(nit_cap=2))
        severities = [f["severity"] for f in result.shown]
        assert severities.count("blocking") == 1
        assert severities.count("nit") == 2

    def test_note_points_at_the_full_report(self):
        result = externalize([finding() for _ in range(7)], ReviewPolicy(nit_cap=2))
        assert "full report" in result.note

    def test_no_note_when_nothing_withheld(self):
        assert externalize([finding()], ReviewPolicy(nit_cap=5)).note == ""

    def test_cap_of_none_shows_everything(self):
        findings = [finding() for _ in range(20)]
        assert len(externalize(findings, ReviewPolicy(nit_cap=None)).shown) == 20

    def test_detection_is_never_reduced(self):
        """externalize must not mutate or shrink the caller's list — the report
        file keeps every finding."""
        findings = [finding() for _ in range(9)]
        externalize(findings, ReviewPolicy(nit_cap=2))
        assert len(findings) == 9

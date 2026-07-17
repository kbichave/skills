"""Tests for scripts/lib/comment_markers — deterministic marker insertion."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from lib.comment_markers import Marker, comment_wrap, insert_markers  # noqa: E402


class TestCommentWrap:
    def test_python_hash(self):
        assert comment_wrap(".py", "hi") == "# hi"

    def test_c_family_slashes(self):
        assert comment_wrap(".ts", "hi") == "// hi"
        assert comment_wrap(".go", "hi") == "// hi"

    def test_sql_dashes(self):
        assert comment_wrap(".sql", "hi") == "-- hi"

    def test_block_html_md(self):
        assert comment_wrap(".html", "hi") == "<!-- hi -->"
        assert comment_wrap(".md", "hi") == "<!-- hi -->"

    def test_unknown_extension_falls_back_to_hash(self):
        assert comment_wrap(".xyz", "hi") == "# hi"


class TestInsertMarkers:
    def test_inserts_above_line(self):
        text = "a = 1\nb = 2\nc = 3"
        out = insert_markers(text, ".py", [Marker(2, "CODECHANGE", "fix b")])
        lines = out.split("\n")
        assert lines[1] == "# CODECHANGE(review): fix b"
        assert lines[2] == "b = 2"

    def test_bottom_up_no_line_drift(self):
        text = "l1\nl2\nl3\nl4"
        markers = [Marker(1, "CODECHANGE", "one"), Marker(4, "RECOMMENDATION", "four")]
        out = insert_markers(text, ".py", markers).split("\n")
        assert out[0] == "# CODECHANGE(review): one"
        assert out[1] == "l1"
        # l4 still correctly annotated despite the earlier insert above l1
        assert "# RECOMMENDATION(review): four" in out
        four_idx = out.index("# RECOMMENDATION(review): four")
        assert out[four_idx + 1] == "l4"

    def test_indentation_preserved(self):
        text = "def f():\n    x = 1"
        out = insert_markers(text, ".py", [Marker(2, "CODECHANGE", "y")]).split("\n")
        assert out[1] == "    # CODECHANGE(review): y"

    def test_idempotent_rerun(self):
        text = "a = 1\nb = 2"
        m = [Marker(2, "CODECHANGE", "fix")]
        once = insert_markers(text, ".py", m)
        twice = insert_markers(once, ".py", [Marker(3, "CODECHANGE", "fix")])
        # second run targets the now-shifted real line; the already-marked line
        # is not double-annotated
        assert twice.count("CODECHANGE(review): fix") == 1

    def test_out_of_range_ignored(self):
        text = "a = 1"
        out = insert_markers(text, ".py", [Marker(99, "CODECHANGE", "x")])
        assert out == text

    def test_duplicate_lines_dedup(self):
        text = "a\nb\nc"
        markers = [Marker(2, "CODECHANGE", "first"), Marker(2, "CODECHANGE", "second")]
        out = insert_markers(text, ".py", markers)
        assert out.count("CODECHANGE(review)") == 1
        assert "first" in out and "second" not in out

    def test_go_and_sql_syntax_end_to_end(self):
        go = insert_markers("package main", ".go", [Marker(1, "RECOMMENDATION", "z")])
        assert go.split("\n")[0] == "// RECOMMENDATION(review): z"
        sql = insert_markers("SELECT 1", ".sql", [Marker(1, "CODECHANGE", "z")])
        assert sql.split("\n")[0] == "-- CODECHANGE(review): z"

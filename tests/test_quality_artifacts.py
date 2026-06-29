"""Tests for quality artifact generation + freshness (build step 8)."""

from __future__ import annotations

from pathlib import Path

from lib import quality_artifacts as qa

REAL_PACKS = Path(__file__).parent.parent / "references" / "quality"


def test_fingerprint_is_stable():
    assert qa.packs_fingerprint(REAL_PACKS) == qa.packs_fingerprint(REAL_PACKS)


def test_fingerprint_changes_with_content(tmp_path):
    (tmp_path / "core").mkdir()
    idx = tmp_path / "core" / "index.md"
    idx.write_text("a", encoding="utf-8")
    before = qa.packs_fingerprint(tmp_path)
    idx.write_text("b", encoding="utf-8")
    assert qa.packs_fingerprint(tmp_path) != before


def test_freshness_roundtrip(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "index.md").write_text("x", encoding="utf-8")
    assert qa.is_fresh(tmp_path) is False  # no marker yet
    qa.write_fingerprint(tmp_path)
    assert qa.is_fresh(tmp_path) is True
    (tmp_path / "core" / "index.md").write_text("y", encoding="utf-8")
    assert qa.is_fresh(tmp_path) is False  # content drifted


def test_fingerprint_ignores_marker_file(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "index.md").write_text("x", encoding="utf-8")
    fp1 = qa.packs_fingerprint(tmp_path)
    qa.write_fingerprint(tmp_path)
    # writing the marker must not change the fingerprint
    assert qa.packs_fingerprint(tmp_path) == fp1


def test_best_practices_includes_active_family_content():
    out = qa.generate_best_practices(["core"], REAL_PACKS)
    assert "ENG-001" in out
    assert "SEC-001" in out
    # inactive pack content absent
    assert "A11Y-001" not in out


def test_best_practices_excludes_inactive_packs():
    out = qa.generate_best_practices(["core"], REAL_PACKS)
    assert "API-001" not in out

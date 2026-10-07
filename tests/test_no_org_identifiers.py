"""Shipped files never name the organization whose warehouse patterns they carry.

The denylist is hashed so this test does not leak what it guards. Maintainers
add local-only terms with DEEP_LEAK_TERMS="term one,term two".
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from lib import leak_guard

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_shipped_files_have_no_org_identifiers():
    hits = leak_guard.scan_repo(ROOT)
    assert not hits, "organization identifiers found:\n" + "\n".join(
        f"{h.path}:{h.line}: {h.text}" for h in hits
    )


class TestScanner:
    def test_planted_local_term_is_found(self, monkeypatch):
        monkeypatch.setenv("DEEP_LEAK_TERMS", "Acme Fuel Co")
        hits = leak_guard.scan_text("x\nsold by ACME-fuel co. today\n", "f.md",
                                    leak_guard.denylist())
        assert [(h.path, h.line) for h in hits] == [("f.md", 2)]

    def test_longer_word_is_not_a_hit(self, monkeypatch):
        monkeypatch.setenv("DEEP_LEAK_TERMS", "acme fuel")
        hits = leak_guard.scan_text("acme fuels and acmefuel\n", "f.md",
                                    leak_guard.denylist())
        assert hits == []

    def test_denylist_entries_are_sha256(self):
        assert all(len(h) == 64 for h in leak_guard.DENYLIST_SHA256)

"""Tests for spec-time policy projection.

The structural property that keeps this honest: it must never become a second
resolver. `resolve_spec_context` has to agree with `resolve_packs` on the active
set, because two resolvers drift and then nobody knows which one is right.

The product property: a bounded number of answerable questions. The spec phase
is already the longest step, and an interrogation is how /deep plan stops being
used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import pack_router
from lib.policy_router import (
    CONCERN_NORM,
    MAX_OBLIGATIONS,
    derive_question,
    obligations_for_pack,
    resolve_spec_context,
)

REAL_PACKS = Path(__file__).resolve().parent.parent / "references" / "quality"


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    directory = tmp_path / "core"
    directory.mkdir()
    (directory / "index.md").write_text("# core\nAlways-on.\n")
    (directory / "err.md").write_text(
        "### ERR-001: No swallowed exceptions\n"
        "- **Required behavior:** handle, re-raise, or log with context.\n"
        "- **Severity:** BLOCK\n"
        "- **Enforcer:** linter\n"
        "\n"
        "### ERR-002: Fail closed\n"
        "- **Required behavior:** on error, deny rather than silently continue.\n"
        "- **Severity:** BLOCK\n"
        "- **Enforcer:** reviewer + test\n"
        "\n"
        "### ERR-003: Actionable messages\n"
        "- **Required behavior:** say what failed and what to do.\n"
        "- **Severity:** ADVISE\n"
        "- **Enforcer:** reviewer\n"
    )
    return directory


class TestSelection:
    def test_keeps_reviewer_enforced_rules(self, pack):
        ids = [o.rule_id for o in obligations_for_pack(pack, "core")]
        assert "ERR-002" in ids

    def test_drops_linter_enforced_rules(self, pack):
        """Asking a spec author to promise ruff will pass is noise; the gate
        already answers that at Phase 6."""
        assert "ERR-001" not in [o.rule_id for o in obligations_for_pack(pack, "core")]

    def test_drops_advise_severity(self, pack):
        assert "ERR-003" not in [o.rule_id for o in obligations_for_pack(pack, "core")]

    def test_skips_the_index(self, pack):
        assert all(o.rule_id.startswith("ERR") for o in obligations_for_pack(pack, "core"))

    def test_missing_pack_dir_is_empty(self, tmp_path):
        assert obligations_for_pack(tmp_path / "nope", "nope") == []


class TestQuestionDerivation:
    def test_uses_explicit_spec_question_when_present(self):
        question = derive_question("x", {"spec_question": "Which store holds sessions?"})
        assert question == "Which store holds sessions?"

    def test_derives_from_required_behavior(self):
        question = derive_question("Fail closed", {"required behavior": "deny on error."})
        assert "deny on error" in question and question.endswith("?")

    def test_falls_back_to_the_title(self):
        """A missing annotation must not break anything, so the corpus needs no
        up-front annotation pass."""
        assert derive_question("Fail closed", {}) == "How does the design address fail closed?"

    def test_accepts_british_spelling(self):
        question = derive_question("x", {"required behaviour": "deny on error."})
        assert "deny on error" in question


class TestResolveSpecContext:
    def test_agrees_with_pack_router_on_active_packs(self, tmp_path):
        """The structural guard against a second resolver."""
        spec = "A dbt model in Snowflake with incremental loads."
        signals = pack_router.detect_signals(tmp_path, spec_text=spec)
        expected = pack_router.resolve_packs(signals, REAL_PACKS).active_packs

        context = resolve_spec_context(tmp_path, REAL_PACKS, spec_text=spec)
        assert context.active_packs == expected

    def test_produces_obligations_from_the_real_corpus(self, tmp_path):
        context = resolve_spec_context(tmp_path, REAL_PACKS, spec_text="a python service")
        assert context.obligations, "core is always on and has reviewer-enforced rules"

    def test_respects_the_cap(self, tmp_path):
        context = resolve_spec_context(tmp_path, REAL_PACKS, spec_text="a python api service")
        assert len(context.obligations) <= MAX_OBLIGATIONS

    def test_flags_truncation(self, tmp_path):
        context = resolve_spec_context(tmp_path, REAL_PACKS, spec_text="a python api service")
        if context.truncated:
            assert len(context.obligations) == MAX_OBLIGATIONS

    def test_block_rules_survive_truncation(self, tmp_path):
        """If the cap bites, what remains must be what matters."""
        context = resolve_spec_context(tmp_path, REAL_PACKS, spec_text="a python api service")
        severities = [o.severity for o in context.obligations]
        assert severities == sorted(severities, key=lambda s: s != "BLOCK")

    def test_defaults_to_advise_mode(self, tmp_path):
        """Ships advising, not gating, for one release — the plugin's own
        stated rollout convention for new BLOCKs."""
        assert resolve_spec_context(tmp_path, REAL_PACKS).mode == "advise"

    def test_serializes(self, tmp_path):
        payload = resolve_spec_context(tmp_path, REAL_PACKS).to_dict()
        assert payload["concern_norm"] == CONCERN_NORM
        assert payload["max_obligations"] == MAX_OBLIGATIONS
        assert isinstance(payload["obligations"], list)

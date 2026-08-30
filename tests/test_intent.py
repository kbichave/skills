"""Tests for intent.md — Playbook Stage 1 artifact.

Two properties these protect, both governance rather than mechanics:
  1. A decision always carries a name. An unattributed decision record looks
     like an audit trail without being one, which is worse than none.
  2. Terminal statuses are terminal. Re-deciding an accepted intent would
     rewrite history silently.
"""

from __future__ import annotations

import pytest

from lib.intent import (
    INTENT_SOURCES,
    INTENT_STATUSES,
    REQUIRED_SECTIONS,
    Intent,
    IntentError,
    default_template,
    new_intent_id,
    parse,
    render,
    set_decision,
    set_spec,
    slugify,
    validate,
)

CREATED = "2026-08-30T14:02:11+00:00"
TITLE = "Retail fuel price updates lag the rack by 40 minutes"


def filled_body() -> str:
    return "\n".join(
        [
            f"# {TITLE}",
            "",
            "## Problem",
            "The board is always behind the rack.",
            "",
            "## Who is affected",
            "Retail Fuel pricing and 340 store managers.",
            "",
            "## Desired outcome",
            "The board matches the rack within a few minutes.",
            "",
            "## Constraints",
            "PDI cannot change.",
            "",
            "## Success metrics",
            "Lag under 5 minutes, from 40 today.",
            "",
            "## Out of scope",
            "Wholesale pricing.",
            "",
            "## Open questions",
            "Is the delay in ingest or refresh cadence?",
            "",
        ]
    )


def an_intent(**overrides) -> Intent:
    base = dict(
        id=new_intent_id(TITLE, CREATED),
        title=TITLE,
        author="dev@example.com",
        created=CREATED,
        status="proposed",
        source="human",
        body=filled_body(),
    )
    base.update(overrides)
    return Intent(**base)


class TestIdentifiers:
    def test_id_is_date_plus_slug(self):
        assert new_intent_id("Price board lags", CREATED) == "2026-08-30-price-board-lags"

    def test_id_is_deterministic(self):
        assert new_intent_id(TITLE, CREATED) == new_intent_id(TITLE, CREATED)

    def test_slug_is_capped(self):
        assert len(slugify("word " * 40)) <= 48

    def test_slug_drops_punctuation(self):
        assert slugify("Price board: 40% behind!") == "price-board-40-behind"

    def test_slug_has_no_trailing_separator(self):
        assert not slugify("Price board -- ").endswith("-")


class TestRoundTrip:
    def test_render_parse_round_trips(self):
        original = an_intent()
        restored = parse(render(original))
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.status == original.status
        assert restored.body.strip() == original.body.strip()

    def test_none_fields_round_trip_as_none(self):
        restored = parse(render(an_intent()))
        assert restored.spec is None
        assert restored.decided_by is None

    def test_tags_round_trip(self):
        restored = parse(render(an_intent(tags=("retail-fuel", "pricing"))))
        assert restored.tags == ("retail-fuel", "pricing")

    def test_title_with_colon_round_trips(self):
        """Colons are the classic hand-rolled-frontmatter bug."""
        restored = parse(render(an_intent(title="Pricing: the board lags")))
        assert restored.title == "Pricing: the board lags"


class TestParse:
    def test_missing_frontmatter_raises(self):
        with pytest.raises(IntentError, match="front-matter"):
            parse("# Just a heading\n")

    def test_missing_required_key_raises(self):
        with pytest.raises(IntentError, match="missing required"):
            parse("---\nid: x\ntitle: y\n---\nbody")

    def test_empty_input_raises(self):
        with pytest.raises(IntentError):
            parse("")


class TestTemplate:
    def test_contains_every_required_section(self):
        text = default_template(title=TITLE, author="dev@example.com", created=CREATED)
        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in text

    def test_starts_as_draft(self):
        text = default_template(title=TITLE, author="dev@example.com", created=CREATED)
        assert parse(text).status == "draft"

    def test_template_is_not_yet_valid(self):
        """The template is placeholders; it must not pass validation, or an
        unfilled intent could be published."""
        text = default_template(title=TITLE, author="dev@example.com", created=CREATED)
        assert validate(text).passed is False


class TestValidate:
    def test_filled_intent_passes_clean(self):
        result = validate(render(an_intent()))
        assert result.passed and result.errors == [] and result.warnings == []

    def test_never_raises_on_garbage(self):
        assert validate("not an intent at all").passed is False

    def test_unknown_status_is_an_error(self):
        result = validate(render(an_intent(status="maybe")))
        assert any("unknown status" in e for e in result.errors)

    def test_unknown_source_is_an_error(self):
        result = validate(render(an_intent(source="robot")))
        assert any("unknown source" in e for e in result.errors)

    def test_non_iso_created_is_an_error(self):
        result = validate(render(an_intent(created="last tuesday")))
        assert any("ISO 8601" in e for e in result.errors)

    def test_missing_section_is_an_error(self):
        body = filled_body().replace("## Out of scope", "## Scope")
        result = validate(render(an_intent(body=body)))
        assert any("Out of scope" in e for e in result.errors)

    def test_empty_problem_is_an_error(self):
        body = filled_body().replace("The board is always behind the rack.", "")
        result = validate(render(an_intent(body=body)))
        assert any("Problem is empty" in e for e in result.errors)

    def test_success_metric_without_a_number_warns(self):
        body = filled_body().replace("Lag under 5 minutes, from 40 today.", "Much faster.")
        result = validate(render(an_intent(body=body)))
        assert result.passed, "a vague metric is a warning, not a blocker"
        assert any("no number" in w for w in result.warnings)

    def test_id_title_mismatch_warns_but_passes(self):
        result = validate(render(an_intent(id="2026-08-30-something-else")))
        assert result.passed
        assert any("does not match" in w for w in result.warnings)

    def test_short_body_warns(self):
        body = "# T\n\n" + "\n\n".join(f"## {s}\nx" for s in REQUIRED_SECTIONS)
        result = validate(render(an_intent(body=body)))
        assert any("under 200 characters" in w for w in result.warnings)


class TestDecision:
    def test_accept_records_who_and_when(self):
        decided = set_decision(
            an_intent(), status="accepted", decided_by="lead@example.com", reason="urgent"
        )
        assert decided.status == "accepted"
        assert decided.decided_by == "lead@example.com"
        assert decided.decided_at is not None
        assert decided.decision_reason == "urgent"

    def test_original_is_unchanged(self):
        """The file is the source of truth; the object must not drift."""
        original = an_intent()
        set_decision(original, status="accepted", decided_by="lead", reason="r")
        assert original.status == "proposed"
        assert original.decided_by is None

    def test_unattributed_decision_is_refused(self):
        with pytest.raises(IntentError, match="decided_by is required"):
            set_decision(an_intent(), status="accepted", decided_by="   ", reason="r")

    def test_terminal_status_cannot_be_redecided(self):
        accepted = set_decision(
            an_intent(), status="accepted", decided_by="lead", reason="r"
        )
        with pytest.raises(IntentError, match="already accepted"):
            set_decision(accepted, status="rejected", decided_by="lead", reason="oops")

    def test_non_terminal_status_is_not_a_decision(self):
        with pytest.raises(IntentError, match="not a decision"):
            set_decision(an_intent(), status="draft", decided_by="lead", reason="r")

    def test_unknown_status_refused(self):
        with pytest.raises(IntentError, match="unknown status"):
            set_decision(an_intent(), status="banana", decided_by="lead", reason="r")

    def test_empty_reason_becomes_none_not_empty_string(self):
        decided = set_decision(an_intent(), status="rejected", decided_by="lead", reason="")
        assert decided.decision_reason is None


class TestSpecLink:
    def test_set_spec_records_the_path(self):
        assert set_spec(an_intent(), "docs/spec/a.md").spec == "docs/spec/a.md"

    def test_set_spec_returns_a_copy(self):
        original = an_intent()
        set_spec(original, "docs/spec/a.md")
        assert original.spec is None


class TestSchemaConstants:
    def test_agent_source_exists_for_stage_six(self):
        """Stage 6 raises intents from breached control bands. The schema has
        to carry that from day one or the loop cannot close later."""
        assert "agent" in INTENT_SOURCES

    def test_statuses_cover_the_documented_lifecycle(self):
        assert INTENT_STATUSES == {
            "draft",
            "proposed",
            "accepted",
            "rejected",
            "superseded",
        }

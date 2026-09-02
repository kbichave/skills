"""Expected-information-gain scoring for clarifying questions.

The numbers in these tests are not arbitrary — each one is the closed-form
answer for its case, so a regression in the probability model shows up as a
wrong constant rather than as a plausible-looking drift:

- an even two-way split of n hypotheses resolves exactly 1 bit
- a question with one answer per hypothesis resolves exactly log2(n)
- a question no answer discriminates on resolves exactly 0
"""

from __future__ import annotations

import json
import subprocess
import sys
from math import log2
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib import eig

CHECKS = Path(__file__).resolve().parent.parent / "scripts" / "checks"


def hyps(n: int) -> list[eig.Hypothesis]:
    return [eig.Hypothesis(id=f"H{i}", label=f"plan {i}") for i in range(1, n + 1)]


def question(qid: str, *answers, **kwargs) -> eig.Candidate:
    """`answers` are iterables of eliminated hypothesis ids."""
    return eig.Candidate(
        id=qid,
        text=kwargs.pop("text", qid),
        answers=tuple(
            eig.Answer(label=f"a{i}", eliminates=tuple(a))
            for i, a in enumerate(answers, start=1)
        ),
        **kwargs,
    )


def split(n: int) -> eig.Candidate:
    """A question that halves n hypotheses."""
    half = n // 2
    lower = [f"H{i}" for i in range(1, half + 1)]
    upper = [f"H{i}" for i in range(half + 1, n + 1)]
    return question("split", upper, lower)


def full_discriminator(n: int) -> eig.Candidate:
    return question(
        "full",
        *[[f"H{j}" for j in range(1, n + 1) if j != i] for i in range(1, n + 1)],
    )


class TestEntropy:
    def test_uniform_is_log2_n(self):
        assert eig.entropy([1] * 8) == pytest.approx(3.0)

    def test_certainty_is_zero(self):
        assert eig.entropy([1]) == 0.0
        assert eig.entropy([5, 0, 0]) == 0.0

    def test_empty_and_massless_are_zero_not_an_error(self):
        # Reached whenever an answer rules out every remaining hypothesis.
        assert eig.entropy([]) == 0.0
        assert eig.entropy([0, 0]) == 0.0

    def test_weights_need_not_be_probabilities(self):
        assert eig.entropy([2, 2]) == eig.entropy([0.5, 0.5]) == 1.0


class TestExpectedInformationGain:
    @pytest.mark.parametrize("n", [2, 4, 8, 16])
    def test_even_split_resolves_exactly_one_bit(self, n):
        assert eig.expected_information_gain(split(n), hyps(n)) == pytest.approx(1.0)

    @pytest.mark.parametrize("n", [2, 3, 5, 8])
    def test_full_discriminator_resolves_all_the_uncertainty(self, n):
        gain = eig.expected_information_gain(full_discriminator(n), hyps(n))
        assert gain == pytest.approx(log2(n))

    def test_question_that_eliminates_nothing_is_worth_nothing(self):
        naming = question("name", [], [])
        assert eig.expected_information_gain(naming, hyps(4)) == 0.0

    def test_lopsided_split_beats_nothing_but_loses_to_even(self):
        one_of_four = question("lopsided", ["H2", "H3", "H4"], ["H1"])
        gain = eig.expected_information_gain(one_of_four, hyps(4))
        assert 0 < gain < 1.0
        assert gain == pytest.approx(0.8113, abs=1e-4)

    def test_single_answer_teaches_nothing(self):
        assert eig.expected_information_gain(question("q", ["H1"]), hyps(3)) == 0.0

    def test_self_answerable_scores_zero_however_discriminating(self):
        # The most informative question available, and still not the user's to
        # answer: the repo settles it.
        candidate = eig.Candidate(
            id="Q",
            text="which warehouse?",
            answers=full_discriminator(4).answers,
            self_answerable=True,
        )
        assert eig.expected_information_gain(candidate, hyps(4)) == 0.0

    def test_gain_never_exceeds_the_prior_uncertainty(self):
        for n in (2, 3, 6):
            prior = log2(n)
            for candidate in (split(n) if n % 2 == 0 else full_discriminator(n),):
                assert eig.expected_information_gain(candidate, hyps(n)) <= prior + 1e-9

    def test_a_skewed_prior_shrinks_what_there_is_to_learn(self):
        peaked = [
            eig.Hypothesis(id="H1", weight=100.0),
            eig.Hypothesis(id="H2", weight=1.0),
        ]
        assert eig.expected_information_gain(split(2), peaked) < 0.1


class TestJointGain:
    def test_asking_the_same_question_twice_gains_what_asking_it_once_gains(self):
        once = split(4)
        twice = eig.Candidate(id="again", text="reworded", answers=once.answers)
        assert eig.joint_information_gain([once, twice], hyps(4)) == pytest.approx(1.0)

    def test_two_orthogonal_splits_compose(self):
        # Halve on parity, halve again on magnitude: together they isolate one
        # of four, which is 2 bits.
        parity = question("parity", ["H2", "H4"], ["H1", "H3"])
        magnitude = question("magnitude", ["H3", "H4"], ["H1", "H2"])
        assert eig.joint_information_gain(
            [parity, magnitude], hyps(4)
        ) == pytest.approx(2.0)

    def test_joint_gain_is_never_worse_than_its_best_member(self):
        parity = question("parity", ["H2", "H4"], ["H1", "H3"])
        weak = question("weak", ["H4"], ["H1"])
        joint = eig.joint_information_gain([parity, weak], hyps(4))
        assert joint >= eig.expected_information_gain(parity, hyps(4)) - 1e-9

    def test_no_scorable_questions_is_no_gain(self):
        assert eig.joint_information_gain([], hyps(4)) == 0.0
        assert eig.joint_information_gain([question("q", ["H1"])], hyps(4)) == 0.0


class TestSelection:
    def test_the_first_question_asked_is_the_most_informative_one(self):
        selection = eig.select_questions(
            [question("weak", ["H4"], ["H1"]), full_discriminator(4)], hyps(4)
        )
        assert selection.asked[0].id == "full"

    def test_a_reworded_duplicate_is_named_as_such(self):
        once = split(4)
        twice = eig.Candidate(id="Q2", text="reworded", answers=once.answers)
        selection = eig.select_questions([once, twice], hyps(4))
        dropped = next(s for s in selection.scores if s.id == "Q2")
        assert dropped.decision == eig.DROP
        assert "same question as split" in dropped.reason

    def test_self_answerable_and_undiscriminating_are_dropped_with_distinct_reasons(self):
        selection = eig.select_questions(
            [
                eig.Candidate(
                    id="self",
                    text="which warehouse?",
                    answers=split(4).answers,
                    self_answerable=True,
                ),
                question("naming", [], []),
                split(4),
            ],
            hyps(4),
        )
        reasons = {s.id: s.reason for s in selection.scores if s.decision == eig.DROP}
        assert "go look" in reasons["self"]
        assert "rules out" in reasons["naming"]
        assert [s.id for s in selection.asked] == ["split"]

    def test_budget_is_a_ceiling_and_the_overflow_says_so(self):
        candidates = [
            question(
                f"q{i}", [f"H{j}" for j in range(1, 9) if j != i], [f"H{i}"]
            )
            for i in range(1, 9)
        ]
        selection = eig.select_questions(
            candidates, hyps(8), eig.Policy(budget=2, marginal_ratio=0.0)
        )
        assert len(selection.asked) == 2
        overflow = [s for s in selection.scores if s.decision == eig.DROP]
        assert overflow and all("larger budget" in s.reason for s in overflow)

    def test_nothing_is_asked_once_one_hypothesis_is_left(self):
        # A perfectly well-formed question, asked when there is nothing left
        # to distinguish. Zero prior uncertainty, so zero warrant.
        selection = eig.select_questions(
            [question("q", ["H1"], [])], [eig.Hypothesis(id="H1")]
        )
        assert selection.asked == ()
        assert selection.prior_bits == 0.0
        assert "before asking anything" in selection.scores[0].reason

    def test_the_floor_silences_a_question_that_barely_moves_the_needle(self):
        barely = question("barely", ["H16"], [])
        selection = eig.select_questions(
            [barely], hyps(16), eig.Policy(floor_bits=0.5)
        )
        assert selection.asked == ()
        assert "floor" in selection.scores[0].reason

    def test_residual_uncertainty_is_reported_not_hidden(self):
        selection = eig.select_questions([split(8)], hyps(8), eig.Policy(budget=1))
        assert selection.prior_bits == pytest.approx(3.0)
        assert selection.joint_bits == pytest.approx(1.0)
        assert selection.residual_bits == pytest.approx(2.0)

    def test_marginal_collapse_stops_a_round_that_has_learned_enough(self):
        strong = full_discriminator(8)
        weak = question("weak", ["H8"], [])
        selection = eig.select_questions(
            [strong, weak], hyps(8), eig.Policy(marginal_ratio=0.5, floor_bits=0.0)
        )
        assert [s.id for s in selection.asked] == ["full"]
        assert "already resolved" in next(
            s.reason for s in selection.scores if s.id == "weak"
        )

    def test_an_undeclared_hypothesis_costs_that_question_not_the_round(self):
        selection = eig.select_questions(
            [question("typo", ["H99"], ["H1"]), split(4)], hyps(4)
        )
        assert [s.id for s in selection.asked] == ["split"]
        assert "H99" in next(s.reason for s in selection.scores if s.id == "typo")
        assert selection.warnings

    def test_every_candidate_comes_back_with_a_verdict(self):
        candidates = [split(4), question("naming", [], []), full_discriminator(4)]
        selection = eig.select_questions(candidates, hyps(4))
        assert {s.id for s in selection.scores} == {c.id for c in candidates}


class TestPayloadErrors:
    def test_no_hypotheses_is_a_hard_error(self):
        with pytest.raises(eig.EIGError, match="no hypotheses"):
            eig.select_questions([split(4)], [])

    def test_duplicate_hypothesis_ids_are_rejected(self):
        with pytest.raises(eig.EIGError, match="duplicate"):
            eig.select_questions(
                [split(2)], [eig.Hypothesis(id="H1"), eig.Hypothesis(id="H1")]
            )

    def test_zero_total_weight_is_rejected(self):
        with pytest.raises(eig.EIGError, match="zero"):
            eig.select_questions([split(2)], [eig.Hypothesis(id="H1", weight=0)])

    def test_parse_payload_reads_the_documented_shape(self):
        candidates, hypotheses, policy = eig.parse_payload(
            {
                "hypotheses": [{"id": "H1"}, "H2"],
                "questions": [
                    {
                        "id": "Q1",
                        "text": "sync?",
                        "answers": [
                            {"label": "yes", "eliminates": "H2"},
                            {"label": "no", "eliminates": ["H1"]},
                        ],
                    }
                ],
                "policy": {"budget": 2, "floor_bits": 0.3},
            }
        )
        assert [h.id for h in hypotheses] == ["H1", "H2"]
        assert candidates[0].answers[0].eliminates == ("H2",)
        assert (policy.budget, policy.floor_bits) == (2, 0.3)

    def test_parse_payload_defaults_question_ids(self):
        candidates, _, _ = eig.parse_payload(
            {"hypotheses": ["H1"], "questions": [{"text": "unlabelled"}]}
        )
        assert candidates[0].id == "Q1"

    def test_parse_payload_rejects_a_non_object(self):
        with pytest.raises(eig.EIGError, match="JSON object"):
            eig.parse_payload([])


class TestPickQuestionsCLI:
    def run(self, payload, *args):
        return subprocess.run(
            [sys.executable, str(CHECKS / "pick-questions.py"), *args],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )

    def payload(self):
        return {
            "hypotheses": ["H1", "H2", "H3", "H4"],
            "questions": [
                {"id": "Q1", "text": "sync or async?", "answers": [
                    {"label": "sync", "eliminates": ["H3", "H4"]},
                    {"label": "async", "eliminates": ["H1", "H2"]},
                ]},
                {"id": "Q2", "text": "what warehouse?", "self_answerable": True,
                 "answers": [{"label": "a", "eliminates": ["H1"]},
                             {"label": "b", "eliminates": ["H2"]}]},
            ],
        }

    def test_json_output_ranks_the_asks(self):
        result = self.run(self.payload())
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert [q["id"] for q in data["ask"]] == ["Q1"]
        assert data["ask"][0]["bits"] == 1.0
        assert data["prior_bits"] == 2.0
        assert [q["id"] for q in data["drop"]] == ["Q2"]

    def test_markdown_output_is_a_table_with_a_residual_line(self):
        result = self.run(self.payload(), "--format", "markdown")
        assert result.returncode == 0
        assert "| **ASK** |" in result.stdout
        assert "leaves 1.00 unresolved" in result.stdout

    def test_budget_flag_overrides_the_payload(self):
        payload = self.payload()
        payload["policy"] = {"budget": 4}
        data = json.loads(self.run(payload, "--budget", "0").stdout)
        assert data["ask"] == []

    def test_floor_flag_can_silence_the_round(self):
        data = json.loads(self.run(self.payload(), "--floor-bits", "1.5").stdout)
        assert data["ask"] == []

    def test_unusable_payload_exits_two_with_a_reason(self):
        result = self.run({"questions": []})
        assert result.returncode == 2
        assert json.loads(result.stdout)["success"] is False

    def test_malformed_json_exits_two(self):
        result = subprocess.run(
            [sys.executable, str(CHECKS / "pick-questions.py")],
            input="{not json",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "not valid JSON" in json.loads(result.stdout)["error"]

    def test_empty_stdin_is_a_usage_error_not_a_crash(self):
        result = subprocess.run(
            [sys.executable, str(CHECKS / "pick-questions.py")],
            input="",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "no input" in json.loads(result.stdout)["error"]

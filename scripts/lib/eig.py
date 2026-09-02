"""Which questions are worth asking, measured in bits.

An agent that asks the user everything is as useless as one that asks nothing.
The interview protocols in this plugin cap question *count* (`at most 6`), which
is a proxy for the thing that actually matters: whether an answer would change
what gets built. A cap lets six worthless questions through and blocks the
seventh that mattered.

So score instead of cap. The measure is expected information gain over the set
of *live hypotheses* — the distinct plans still consistent with what is known:

    EIG(Q) = H(hypotheses) - E_answer[ H(hypotheses | answer) ]

with entropy in bits, so a question that halves the hypothesis set scores 1.00
and a question whose every answer leaves the same set standing scores 0.00.
This is the inference-time form of the objective two lines of research
optimise by training:

- arXiv 2406.17453, *Learning to Ask Informative Questions*: EIG as
  `H_prior - H_posterior` with `H_prior = log2(n)` over uniform candidates, an
  even split scoring 1.0. That is `expected_information_gain` below.
- arXiv 2606.03135, *Uncertainty-Aware Clarification in LLM Agents with
  Information Gain*: the same objective as a reward, and the observation that
  matters most here — declining to ask yields exactly zero, so a question
  must earn its place against silence rather than against the other questions.

The division of labour is the repo's usual one. The model enumerates the
hypotheses, the candidate questions, and which hypotheses each answer would
rule out. This module does the arithmetic, because arithmetic done in prose is
arithmetic done wrong.

Two properties are worth knowing before reading the code:

- **Selection is greedy over the joint distribution, not a sort by score.**
  Two questions can each score 1.00 bit and be the same question in different
  words; ranking them independently asks both. Scoring a candidate against the
  answers already selected gives the second one a marginal gain near zero,
  which is the truth about it.
- **A question the codebase can answer scores zero by fiat.** Not because it
  is uninformative — it may be the most informative question available — but
  because the agent is not entitled to spend a person's attention on something
  `grep` settles.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from math import log2

# Decisions a candidate can receive.
ASK = "ask"
DROP = "drop"

# Why a candidate was dropped. Small vocabulary on purpose — see handoff.REASONS
# for the same reasoning about taxonomies nobody can remember.
SELF_ANSWERABLE = "self_answerable"
NOT_DISCRIMINATING = "not_discriminating"
BELOW_FLOOR = "below_floor"
REDUNDANT = "redundant"
BUDGET_SPENT = "budget_spent"
MARGINAL_COLLAPSE = "marginal_collapse"
ALREADY_CERTAIN = "already_certain"

# Guards against a pathological payload turning selection into a combinatorial
# explosion: the joint distribution over k selected questions has
# prod(len(answers)) outcomes.
MAX_JOINT_OUTCOMES = 8192

_EPSILON = 1e-9


class EIGError(ValueError):
    """Raised for a payload that cannot be scored at all."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Hypothesis:
    """One live possibility for what gets built.

    `weight` is a prior, not a probability: it is normalised at use. Leave it
    at 1.0 unless there is a real reason to believe one branch is likelier,
    since an invented prior quietly decides which question looks best.
    """

    id: str
    label: str = ""
    weight: float = 1.0


@dataclass(frozen=True, slots=True, kw_only=True)
class Answer:
    """One answer a user could give, and what it rules out.

    `eliminates` holds hypothesis ids that could no longer be true if the user
    answered this way. An answer that eliminates nothing is the signature of a
    question not worth asking.
    """

    label: str
    eliminates: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidate:
    """A question the agent is considering asking."""

    id: str
    text: str
    answers: tuple[Answer, ...] = ()
    self_answerable: bool = False
    note: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    """Where the ask/act line sits.

    `floor_bits` at 0.15 means a question must expect to resolve about a tenth
    of a binary choice before it is worth a person's time. `marginal_ratio`
    stops a round once each further question adds less than a quarter of what
    the first one added, which is where question lists stop being interviews
    and start being interrogations.
    """

    budget: int = 4
    floor_bits: float = 0.15
    marginal_ratio: float = 0.25
    max_joint_outcomes: int = MAX_JOINT_OUTCOMES


@dataclass(frozen=True, slots=True, kw_only=True)
class Score:
    """What became of one candidate."""

    id: str
    text: str
    bits: float
    marginal_bits: float
    decision: str
    reason: str = ""
    rank: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "bits": round(self.bits, 4),
            "marginal_bits": round(self.marginal_bits, 4),
            "decision": self.decision,
            "reason": self.reason,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class Selection:
    """The round's outcome: what to ask, in what order, and what is left over."""

    prior_bits: float
    hypotheses: int
    scores: tuple[Score, ...]
    joint_bits: float
    residual_bits: float
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def asked(self) -> tuple[Score, ...]:
        return tuple(s for s in self.scores if s.decision == ASK)

    def to_dict(self) -> dict:
        return {
            "prior_bits": round(self.prior_bits, 4),
            "hypotheses": self.hypotheses,
            "joint_bits": round(self.joint_bits, 4),
            "residual_bits": round(self.residual_bits, 4),
            "ask": [s.to_dict() for s in self.asked],
            "drop": [s.to_dict() for s in self.scores if s.decision == DROP],
            "warnings": list(self.warnings),
        }


def entropy(weights) -> float:
    """Shannon entropy in bits of the distribution these weights normalise to.

    An empty or non-positive-mass set has no uncertainty left in it, which is
    0.0 — not an error. That case is reached whenever an answer would rule out
    every remaining hypothesis, and the caller wants a number, not a raise.
    """
    positive = [float(w) for w in weights if float(w) > 0]
    total = sum(positive)
    if total <= 0:
        return 0.0
    result = 0.0
    for weight in positive:
        p = weight / total
        result -= p * log2(p)
    return result


def _weight_map(hypotheses) -> dict[str, float]:
    """Hypothesis id → prior weight, rejecting the two payloads that cannot be
    scored: no hypotheses at all, and duplicate ids (which would silently
    double one branch's prior)."""
    weights: dict[str, float] = {}
    for hypothesis in hypotheses:
        if hypothesis.id in weights:
            raise EIGError(f"duplicate hypothesis id: {hypothesis.id}")
        weights[hypothesis.id] = max(0.0, float(hypothesis.weight))
    if not weights:
        raise EIGError("no hypotheses given — nothing to gain information about")
    if sum(weights.values()) <= 0:
        raise EIGError("all hypothesis weights are zero")
    return weights


def unknown_hypotheses(candidates, hypotheses) -> tuple[str, ...]:
    """Hypothesis ids referenced by an answer but never declared.

    Reported rather than raised: a typo in one `eliminates` entry should cost
    that question its score, not abort the whole round.
    """
    known = {h.id for h in hypotheses}
    missing = {
        ref
        for candidate in candidates
        for answer in candidate.answers
        for ref in answer.eliminates
        if ref not in known
    }
    return tuple(sorted(missing))


def _likelihoods(candidate, weights: dict[str, float]) -> dict[str, tuple[float, ...]]:
    """P(answer | hypothesis) for one question.

    A hypothesis is consistent with every answer that does not eliminate it,
    and — absent any reason to think otherwise — equally likely to produce
    each. So the likelihood is uniform over the surviving answers.

    Doing it this way rather than by surviving mass is what makes the joint
    distribution honest. Under the mass reading, two answer sets that overlap
    let an incoherent answer *pair* be excluded, which concentrates
    probability and credits a question with information it never carried.

    A hypothesis eliminated by every answer is an annotation mistake: the
    question cannot rule out everything. It is treated as saying nothing about
    that hypothesis rather than as evidence against it.
    """
    width = len(candidate.answers)
    table: dict[str, tuple[float, ...]] = {}
    for hid in weights:
        alive = [0.0 if hid in answer.eliminates else 1.0 for answer in candidate.answers]
        live = sum(alive)
        table[hid] = (
            tuple(1.0 / width for _ in range(width))
            if live == 0
            else tuple(value / live for value in alive)
        )
    return table


def _posterior_entropy(candidates, weights: dict[str, float]) -> float:
    """Expected entropy in bits after hearing an answer to each question.

    The sum runs over every combination of answers, so one question and a
    batch of them share this code. Each hypothesis contributes
    `P(h) * prod_q P(a_q | h)` to its combination, assuming the answers are
    independent given the hypothesis — which is the assumption that makes a
    batch scorable at all.
    """
    tables = [_likelihoods(candidate, weights) for candidate in candidates]
    total = sum(weights.values())
    ranges = [range(len(candidate.answers)) for candidate in candidates]
    result = 0.0
    for combination in itertools.product(*ranges):
        posterior: list[float] = []
        for hid, weight in weights.items():
            mass = weight
            for table, index in zip(tables, combination):
                mass *= table[hid][index]
            if mass > 0:
                posterior.append(mass)
        outcome = sum(posterior)
        if outcome <= 0:
            continue
        result += (outcome / total) * entropy(posterior)
    return result


def answer_signature(candidate) -> frozenset[frozenset[str]]:
    """What this question actually asks, stripped of its wording.

    Two questions with the same signature partition the hypotheses the same
    way, so they are the same question. Comparing signatures catches the
    reworded duplicate that greedy scoring alone can let through when the
    annotation is loose.
    """
    return frozenset(frozenset(answer.eliminates) for answer in candidate.answers)


def joint_information_gain(candidates, hypotheses) -> float:
    """Bits these questions expect to resolve *together*.

    Sub-additive by construction, which is the whole point: asking the same
    question twice in different words gains what asking it once gains.
    """
    weights = _weight_map(hypotheses)
    prior = entropy(weights.values())
    usable = [c for c in candidates if len(c.answers) >= 2]
    if not usable:
        return 0.0
    gain = prior - _posterior_entropy(usable, weights)
    return 0.0 if gain < _EPSILON else gain


def expected_information_gain(candidate, hypotheses) -> float:
    """Bits one question expects to resolve on its own.

    Zero for a question with fewer than two answers — there is nothing to
    learn from an answer that was never in doubt — and zero for one the
    codebase can settle, by the rule stated in the module docstring.
    """
    if candidate.self_answerable or len(candidate.answers) < 2:
        return 0.0
    return joint_information_gain([candidate], hypotheses)


def _disqualify(candidate, missing: frozenset[str]) -> tuple[str, str] | None:
    """Reason this candidate never reaches the greedy round, or None.

    These are the cheap tests. Running them first keeps the expensive joint
    scoring off questions that could never have earned a slot.
    """
    if candidate.self_answerable:
        return SELF_ANSWERABLE, "the codebase or the docs settle this — go look"
    if len(candidate.answers) < 2:
        return NOT_DISCRIMINATING, "fewer than two answers, so no answer is news"
    bad = sorted(
        {
            ref
            for answer in candidate.answers
            for ref in answer.eliminates
            if ref in missing
        }
    )
    if bad:
        return NOT_DISCRIMINATING, f"eliminates undeclared hypotheses: {', '.join(bad)}"
    if not any(answer.eliminates for answer in candidate.answers):
        return NOT_DISCRIMINATING, "no answer rules out any hypothesis"
    return None


def _outcome_count(chosen, candidate) -> int:
    count = len(candidate.answers)
    for picked in chosen:
        count *= len(picked.answers)
    return count


def _best_marginal(pool, chosen, hypotheses, policy):
    """The candidate adding the most bits to what is already selected.

    Marginal rather than standalone gain is what separates a genuinely new
    question from a rephrasing of one already on the list.
    """
    baseline = joint_information_gain(chosen, hypotheses) if chosen else 0.0
    best = None
    skipped: list[str] = []
    for candidate in pool:
        if _outcome_count(chosen, candidate) > policy.max_joint_outcomes:
            skipped.append(candidate.id)
            continue
        marginal = joint_information_gain([*chosen, candidate], hypotheses) - baseline
        if best is None or marginal > best[1]:
            best = (candidate, max(0.0, marginal))
    return best, tuple(skipped)


def _greedy(pool, hypotheses, policy):
    """Pick questions one at a time until the next one stops paying.

    Two stop conditions, and they mean different things. `below_floor` says no
    remaining question is worth asking at all. `marginal_collapse` says the
    round has already learned most of what it was going to — the questions
    left are real, just not worth this conversation.
    """
    chosen: list[Candidate] = []
    marginals: list[float] = []
    stops: dict[str, str] = {}
    warnings: list[str] = []
    remaining = list(pool)

    while remaining and len(chosen) < policy.budget:
        best, skipped = _best_marginal(remaining, chosen, hypotheses, policy)
        if skipped:
            warnings.append(
                f"joint scoring skipped {len(skipped)} candidate(s) at "
                f"{policy.max_joint_outcomes} outcomes: {', '.join(skipped)}"
            )
        if best is None:
            break
        candidate, marginal = best
        if marginal < policy.floor_bits:
            stops = {c.id: BELOW_FLOOR for c in remaining}
            break
        if marginals and marginal < policy.marginal_ratio * marginals[0]:
            stops = {c.id: MARGINAL_COLLAPSE for c in remaining}
            break
        chosen.append(candidate)
        marginals.append(marginal)
        remaining.remove(candidate)

    for candidate in remaining:
        stops.setdefault(candidate.id, BUDGET_SPENT)
    return chosen, marginals, stops, tuple(warnings)


_DROP_TEXT = {
    BELOW_FLOOR: "expected gain below the floor — decide it yourself and say so",
    REDUNDANT: "informative alone, but the selected questions already cover it",
    BUDGET_SPENT: "would have been asked with a larger budget",
    MARGINAL_COLLAPSE: "the round had already resolved most of the uncertainty",
    ALREADY_CERTAIN: "uncertainty was below the floor before asking anything",
}


def _drop_score(candidate, hypotheses, reason: str, detail: str = "") -> Score:
    """A dropped candidate still gets its standalone score.

    Recording the bits it *would* have contributed is what makes a dropped
    question auditable: `0.00` justifies itself, `0.90` behind a spent budget
    is a prompt to raise the budget.
    """
    return Score(
        id=candidate.id,
        text=candidate.text,
        bits=expected_information_gain(candidate, hypotheses),
        marginal_bits=0.0,
        decision=DROP,
        reason=detail or _DROP_TEXT.get(reason, reason),
    )


def select_questions(candidates, hypotheses, policy: Policy | None = None) -> Selection:
    """Decide which of these questions to ask, and in what order.

    Returns every candidate with a decision attached, asked ones ranked. The
    ordering matters: the first question is the one that most reduces
    uncertainty, so a user who answers only one has answered the right one.
    """
    policy = policy or Policy()
    weights = _weight_map(hypotheses)
    prior = entropy(weights.values())
    missing = frozenset(unknown_hypotheses(candidates, hypotheses))
    warnings = [f"undeclared hypotheses referenced: {', '.join(sorted(missing))}"] if missing else []

    scores: list[Score] = []
    pool: list[Candidate] = []
    seen: dict[frozenset[frozenset[str]], str] = {}
    for candidate in candidates:
        verdict = _disqualify(candidate, missing)
        if verdict is None:
            twin = seen.setdefault(answer_signature(candidate), candidate.id)
            if twin != candidate.id:
                verdict = (REDUNDANT, f"the same question as {twin}, reworded")
        if verdict:
            scores.append(_drop_score(candidate, hypotheses, verdict[0], verdict[1]))
        else:
            pool.append(candidate)

    if prior <= policy.floor_bits:
        # One hypothesis standing, or a prior so peaked that no answer changes
        # the plan. Asking now is theatre.
        scores.extend(_drop_score(c, hypotheses, ALREADY_CERTAIN) for c in pool)
        return Selection(
            prior_bits=prior,
            hypotheses=len(weights),
            scores=tuple(scores),
            joint_bits=0.0,
            residual_bits=prior,
            warnings=tuple(warnings),
        )

    chosen, marginals, stops, greedy_warnings = _greedy(pool, hypotheses, policy)
    warnings.extend(greedy_warnings)
    by_id = {c.id: c for c in chosen}

    for rank, (candidate, marginal) in enumerate(zip(chosen, marginals), start=1):
        scores.append(
            Score(
                id=candidate.id,
                text=candidate.text,
                bits=expected_information_gain(candidate, hypotheses),
                marginal_bits=marginal,
                decision=ASK,
                rank=rank,
            )
        )
    for candidate in pool:
        if candidate.id in by_id:
            continue
        reason = stops.get(candidate.id, BUDGET_SPENT)
        if reason == BELOW_FLOOR and expected_information_gain(
            candidate, hypotheses
        ) >= policy.floor_bits:
            reason = REDUNDANT
        scores.append(_drop_score(candidate, hypotheses, reason))

    joint = joint_information_gain(chosen, hypotheses)
    return Selection(
        prior_bits=prior,
        hypotheses=len(weights),
        scores=tuple(scores),
        joint_bits=joint,
        residual_bits=max(0.0, prior - joint),
        warnings=tuple(warnings),
    )


def _parse_answers(raw, candidate_id: str) -> tuple[Answer, ...]:
    answers: list[Answer] = []
    for entry in raw or ():
        if isinstance(entry, str):
            answers.append(Answer(label=entry))
            continue
        if not isinstance(entry, dict):
            raise EIGError(f"{candidate_id}: each answer must be a string or object")
        eliminates = entry.get("eliminates") or ()
        if isinstance(eliminates, str):
            eliminates = [eliminates]
        answers.append(
            Answer(
                label=str(entry.get("label", "")),
                eliminates=tuple(str(e) for e in eliminates),
            )
        )
    return tuple(answers)


def parse_payload(data: dict) -> tuple[list[Candidate], list[Hypothesis], Policy]:
    """Build the inputs from the JSON the model hands over.

    Deliberately strict about the two fields that carry the meaning
    (`hypotheses`, `questions`) and forgiving about everything else, so a
    payload written by hand mid-interview still scores.
    """
    if not isinstance(data, dict):
        raise EIGError("payload must be a JSON object")

    hypotheses = [
        Hypothesis(
            id=str(h["id"]),
            label=str(h.get("label", "")),
            weight=float(h.get("weight", 1.0)),
        )
        if isinstance(h, dict)
        else Hypothesis(id=str(h))
        for h in data.get("hypotheses") or ()
    ]

    candidates: list[Candidate] = []
    for index, raw in enumerate(data.get("questions") or (), start=1):
        if not isinstance(raw, dict):
            raise EIGError(f"question {index} must be an object")
        cid = str(raw.get("id") or f"Q{index}")
        candidates.append(
            Candidate(
                id=cid,
                text=str(raw.get("text", "")),
                answers=_parse_answers(raw.get("answers"), cid),
                self_answerable=bool(raw.get("self_answerable", False)),
                note=str(raw.get("note", "")),
            )
        )

    raw_policy = data.get("policy") or {}
    defaults = Policy()
    policy = Policy(
        budget=int(raw_policy.get("budget", defaults.budget)),
        floor_bits=float(raw_policy.get("floor_bits", defaults.floor_bits)),
        marginal_ratio=float(raw_policy.get("marginal_ratio", defaults.marginal_ratio)),
        max_joint_outcomes=int(
            raw_policy.get("max_joint_outcomes", defaults.max_joint_outcomes)
        ),
    )
    return candidates, hypotheses, policy

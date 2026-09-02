# Question Selection

Load before any round of `AskUserQuestion` in `plan` (interview), `discovery`
(stakeholder interview), `intent`, or `goalloop` (slicing).

Every existing protocol here caps question *count*: "at most 6", "one at a
time". A cap is a proxy for the thing that matters — whether the answer would
change what gets built — and it fails in both directions. Six worthless
questions pass the cap. The seventh, the one that would have prevented the
rework, does not.

Score instead. The measure is expected information gain over the **live
hypotheses**: the distinct plans still consistent with what you already know.

```
EIG(Q) = H(hypotheses) − E_answer[ H(hypotheses | answer) ]
```

In bits, with a uniform prior over `n` hypotheses: `H = log2(n)`. A question
that halves the set scores `1.00`. A question every answer leaves standing
scores `0.00`. Declining to ask scores exactly `0.00` too — which is the rule
that does the work here. **A question competes against silence, not against
the other questions.** Four mediocre questions do not become worth asking by
being the best four available.

Sources: arXiv 2406.17453 (EIG question selection), arXiv 2606.03135
(information-gain reward, and the zero-for-abstaining property).

---

## Protocol

### 1. Enumerate the live hypotheses

Before writing any question, write down the distinct things that could still
get built. Not requirements — *plans*. Each hypothesis is a coherent
implementation someone could ship.

```
H1  sync write inside the caller's transaction
H2  async write via an outbox table, poller drains it
H3  nightly batch rebuild
H4  CDC stream off the source table
H5  dual write, reconciled daily
H6  read-through cache, no write path at all
```

Rules:

- **Three or fewer hypotheses means you are nearly done deciding.** Score the
  round anyway; it will usually tell you to ask nothing and proceed.
- **A hypothesis you would never ship does not belong on the list.** Padding
  the set inflates every question's score.
- Leave weights at 1.0 unless you have real evidence one branch is likelier.
  An invented prior quietly decides which question looks best.

### 2. Resolve everything the repo can answer

For each question you were about to ask, ask first: could `grep`, the docs, a
migration file, `git log`, or a command settle this? If yes, it is
`self_answerable` — go find out. It scores zero no matter how discriminating
it is, because you are not entitled to spend a person's attention on something
the codebase already states.

This is the single highest-yield step. Most bad interview questions are
lookups in disguise.

### 3. Annotate each candidate

For every candidate question, list the answers a user could actually give,
and for each answer the hypotheses that could no longer be true if they
answered that way.

```json
{
  "hypotheses": [
    {"id": "H1", "label": "sync write in the caller's transaction"},
    {"id": "H2", "label": "async write via outbox"},
    {"id": "H3", "label": "nightly batch"}
  ],
  "questions": [
    {"id": "Q1",
     "text": "Must a rack change show on the board before the next read?",
     "answers": [
       {"label": "yes, same request",  "eliminates": ["H2", "H3"]},
       {"label": "within a minute",    "eliminates": ["H3"]},
       {"label": "next morning",       "eliminates": ["H1"]}
     ]},
    {"id": "Q2", "text": "Which warehouse?", "self_answerable": true,
     "answers": [{"label": "snowflake", "eliminates": ["H1"]},
                 {"label": "postgres",  "eliminates": ["H2"]}]}
  ],
  "policy": {"budget": 4}
}
```

An answer that eliminates nothing is the signature of a question not worth
asking. If every answer of every question eliminates nothing, the problem is
step 1: you have not written down real hypotheses.

### 4. Score it

```bash
python3 ${DEEP_PLUGIN_ROOT}/scripts/checks/pick-questions.py \
  --in "${planning_dir}/questions.json" --format markdown
```

Or pipe the JSON on stdin. `--budget N` and `--floor-bits F` override the
payload. Exit 2 means the payload is unusable; exit 0 means scored, whether or
not anything is worth asking.

Do not do this arithmetic by hand. Comparing `H(x) − E[H(x|a)]` across nine
questions in your head produces a decision to ask all nine.

### 5. Ask what it returns, in the order it returns

The `ask` list is ranked by marginal contribution, so a user who answers only
the first question has answered the right one. Pass them to
`AskUserQuestion` in that order.

Everything in `drop` is settled without the user:

| Verdict | What you do |
|---|---|
| `self_answerable` | Go read the code. Then proceed. |
| `no answer rules out any hypothesis` | Decide it yourself. It does not matter to the plan. |
| `the same question as X, reworded` | Already asked. |
| `below the floor` | Decide it yourself and record the assumption. |
| `informative alone, but already covered` | The answers you are getting imply it. |
| `would have been asked with a larger budget` | Raise the budget only if `residual_bits` is large. |

### 6. Say what is left unresolved

`residual_bits` is the uncertainty you are proceeding under. It is yours to
absorb, not to hand back:

> Proceeding on H2 (outbox). Residual 1.09 bits — mainly whether Finance or
> Retail Fuel owns the cutover window. Assuming Retail Fuel; say so if not.

State the assumption in the spec, the intent, or the increment. An
unstated assumption is the failure this whole protocol exists to prevent.

---

## Policy

| Knob | Default | Meaning |
|---|---|---|
| `budget` | 4 | Most questions to ask in one round |
| `floor_bits` | 0.15 | Below this, decide it yourself |
| `marginal_ratio` | 0.25 | Stop once a question adds under a quarter of what the first one added |

`0.15` bits is roughly a tenth of a binary choice. `marginal_ratio` is what
keeps a round from turning an interview into an interrogation: by the fourth
question the user is answering to be polite, not because you learned anything.

Interactive `plan` and `discovery` may use the full budget. `goalloop` and
other unattended modes should run `budget: 2` — an autonomous run that stops
to ask twice per iteration is not autonomous.

---

## What this does not replace

- **The Premise Challenge** (`interview-protocol.md`). Scoring assumes the
  hypothesis set is right. Challenging the framing is what makes it right, and
  it happens first.
- **`Skill(grilling)`**. Grilling tests whether a stated answer holds up.
  Scoring decides which questions to put to a person at all. Score first, then
  grill the answers you get.
- **One question at a time.** Ranked order exists so a sequential walk asks
  the right question first, not so you can batch four at once when the
  protocol says walk.

#!/usr/bin/env python3
"""Score candidate clarifying questions and say which ones to ask.

The model supplies the judgement — what plans are still live, and which of them
each answer would rule out. This scores that judgement in bits and applies the
ask/act line, because a model asked to compare `H(x) - E[H(x|a)]` across nine
questions in its head will instead ask all nine.

Input is JSON, on stdin or in a file:

    {
      "hypotheses": [
        {"id": "H1", "label": "sync write, same transaction"},
        {"id": "H2", "label": "async write, outbox table"},
        {"id": "H3", "label": "batch nightly"}
      ],
      "questions": [
        {"id": "Q1",
         "text": "Must the price board reflect a rack change before the next read?",
         "answers": [
           {"label": "yes, same request",      "eliminates": ["H2", "H3"]},
           {"label": "within a minute",        "eliminates": ["H3"]},
           {"label": "next morning is fine",   "eliminates": ["H1"]}
         ]},
        {"id": "Q2", "text": "Which warehouse?", "self_answerable": true,
         "answers": [{"label": "snowflake", "eliminates": ["H1"]},
                     {"label": "postgres",  "eliminates": ["H2"]}]}
      ],
      "policy": {"budget": 4, "floor_bits": 0.15}
    }

Set `self_answerable` on anything the repo, the docs, or a command can settle.
It scores zero regardless of how discriminating it is, and the agent is
expected to go find out instead.

Usage:
    pick-questions.py --in candidates.json [--format json|markdown]
    ... | pick-questions.py [--budget N] [--floor-bits F]

Exit codes:
  0 — scored (whether or not anything is worth asking)
  2 — unusable payload
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.eig import ASK, EIGError, parse_payload, select_questions


def _render_markdown(selection) -> str:
    lines = [
        (
            f"**{selection.hypotheses} live hypotheses · "
            f"{selection.prior_bits:.2f} bits of uncertainty**"
        ),
        "",
        "| | Question | Bits | Marginal | Verdict |",
        "|---|---|---|---|---|",
    ]
    for score in selection.scores:
        rank = str(score.rank) if score.rank else "—"
        verdict = "**ASK**" if score.decision == ASK else f"drop — {score.reason}"
        lines.append(
            f"| {rank} | {score.text or score.id} | {score.bits:.2f} "
            f"| {score.marginal_bits:.2f} | {verdict} |"
        )
    lines += [
        "",
        (
            f"Asking these resolves {selection.joint_bits:.2f} bits and leaves "
            f"{selection.residual_bits:.2f} unresolved."
        ),
    ]
    if selection.residual_bits > 0:
        lines.append(
            "Residual uncertainty is yours to decide and state as an "
            "assumption, not to hand back to the user."
        )
    lines.extend(f"- warning: {w}" for w in selection.warnings)
    return "\n".join(lines)


def _load(source: str | None) -> dict:
    text = Path(source).read_text() if source else sys.stdin.read()
    if not text.strip():
        raise EIGError("no input — pass --in FILE or pipe JSON on stdin")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise EIGError(f"input is not valid JSON: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--in", dest="source", help="JSON payload (default: stdin)")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--budget", type=int, help="Maximum questions to ask")
    parser.add_argument(
        "--floor-bits",
        type=float,
        help="Minimum expected gain worth a person's attention (default 0.15)",
    )
    args = parser.parse_args()

    try:
        candidates, hypotheses, policy = parse_payload(_load(args.source))
        if args.budget is not None:
            policy = replace(policy, budget=args.budget)
        if args.floor_bits is not None:
            policy = replace(policy, floor_bits=args.floor_bits)
        selection = select_questions(candidates, hypotheses, policy)
    except (EIGError, KeyError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 2

    if args.format == "markdown":
        print(_render_markdown(selection))
    else:
        print(json.dumps({"success": True, **selection.to_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

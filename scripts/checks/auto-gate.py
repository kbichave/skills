#!/usr/bin/env python3
"""Decide whether an autonomous run may close a human checkpoint.

Replaces the unconditional auto-close. `/deep auto` used to close `user-review`
with the reason "Auto mode: skipped" every time, regardless of whether anything
had gone wrong, so it advanced past phases it should have stopped at.

The rule, borrowed from a model that works: **advance automatically only on
green.** A `passed` phase is not prompted for; anything else halts and says why.
Same autonomy when the work is clean, an actual stop when it is not.

Subcommands:
  check    --planning-dir D [--expected-sections N]
  status   --planning-dir D            full verification detail
  record   --planning-dir D --section S --gates-passed BOOL [...]
  handoff  --planning-dir D            the needs-human queue as markdown

Exit codes:
  0 — advance (check), or command succeeded
  1 — halt; a human is needed
  2 — usage or I/O error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import handoff
from lib.verification import (
    GAPS_FOUND,
    HUMAN_NEEDED,
    phase_status,
    record as record_result,
)

# Which handoff reason a non-passing status maps to.
_HANDOFF_REASON = {GAPS_FOUND: "gate_failed", HUMAN_NEEDED: "three_strikes"}


def cmd_check(args: argparse.Namespace) -> int:
    status = phase_status(args.planning_dir, expected_sections=args.expected_sections)
    payload = status.to_dict()

    if status.can_advance:
        payload["close_reason"] = "Auto mode: advanced on green"
    else:
        causes = ", ".join(f"{k} ({v})" for k, v in sorted(status.reasons.items()))
        payload["close_reason"] = f"Auto mode: halted — {causes}"
        payload["guidance"] = (
            "Do NOT close the checkpoint. Report the failing sections and stop "
            "this phase. The needs-human queue records what to pick up."
        )

    print(json.dumps(payload, indent=2))
    return 0 if status.can_advance else 1


def cmd_status(args: argparse.Namespace) -> int:
    status = phase_status(args.planning_dir, expected_sections=args.expected_sections)
    print(json.dumps(status.to_dict(), indent=2))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    result = record_result(
        args.planning_dir,
        section=args.section,
        gates_passed=args.gates_passed,
        blocking_findings=args.blocking_findings,
        strikes=args.strikes,
        detail=args.detail,
    )

    # A non-passing section goes straight into the handoff queue, so an
    # autonomous run cannot finish while quietly holding a failure.
    if result.status != "passed":
        handoff.record(
            args.planning_dir,
            section=args.section,
            reason=_HANDOFF_REASON.get(result.status, "other"),
            detail=args.detail or result.status,
            attempts=args.strikes,
        )

    print(json.dumps(result.to_dict(), indent=2))
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    print(handoff.summary(args.planning_dir))
    return 0


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planning-dir", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("--expected-sections", type=int, default=0)
    p_check.set_defaults(func=cmd_check)

    p_status = sub.add_parser("status")
    p_status.add_argument("--expected-sections", type=int, default=0)
    p_status.set_defaults(func=cmd_status)

    p_record = sub.add_parser("record")
    p_record.add_argument("--section", required=True)
    p_record.add_argument("--gates-passed", type=_bool, required=True)
    p_record.add_argument("--blocking-findings", type=int, default=0)
    p_record.add_argument("--strikes", type=int, default=0)
    p_record.add_argument("--detail", default="")
    p_record.set_defaults(func=cmd_record)

    sub.add_parser("handoff").set_defaults(func=cmd_handoff)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except OSError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Test-file lock CLI — open, widen, status, override, close.

Playbook Stage 4. The lock is opened once the tests for a section exist and
before the implementation does, so a later "all tests pass" cannot have been
achieved by editing the test.

Subcommands:
  open      --section S --protected P [P ...] [--reason R]
  add       --protected P [P ...]        widen the lock (Phase 9, strike >= 1)
  status
  override  --reason R                   human escape hatch, recorded
  close

Exit codes:
  0 — ok
  2 — usage or I/O error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.fix_lock import (
    add_protected,
    close_lock,
    is_test_path,
    open_lock,
    override,
    read_lock,
)


def cmd_open(args: argparse.Namespace) -> int:
    non_tests = [p for p in args.protected if not is_test_path(p)]
    lock = open_lock(
        args.planning_dir,
        section_id=args.section,
        protected=args.protected,
        reason=args.reason,
    )
    payload = {"ok": True, **lock.to_dict()}
    if non_tests:
        # Not fatal: naming conventions vary. But locking a non-test is almost
        # always a mistake, and a silent one.
        payload["warning"] = (
            f"these do not look like test files: {', '.join(non_tests)}"
        )
    print(json.dumps(payload, indent=2))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    print(json.dumps({"ok": True, **add_protected(args.planning_dir, args.protected).to_dict()}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print(json.dumps(read_lock(args.planning_dir).to_dict(), indent=2))
    return 0


def cmd_override(args: argparse.Namespace) -> int:
    lock = override(args.planning_dir, args.reason)
    print(json.dumps({"ok": True, "released": True, **lock.to_dict()}, indent=2))
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    close_lock(args.planning_dir)
    print(json.dumps({"ok": True, "active": False}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("planning_dir", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open")
    p_open.add_argument("--section", required=True)
    p_open.add_argument("--protected", nargs="+", required=True)
    p_open.add_argument("--reason", default="")
    p_open.set_defaults(func=cmd_open)

    p_add = sub.add_parser("add")
    p_add.add_argument("--protected", nargs="+", required=True)
    p_add.set_defaults(func=cmd_add)

    sub.add_parser("status").set_defaults(func=cmd_status)

    p_override = sub.add_parser("override")
    p_override.add_argument(
        "--reason", required=True, help="recorded in the lock file, so it is not silent"
    )
    p_override.set_defaults(func=cmd_override)

    sub.add_parser("close").set_defaults(func=cmd_close)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except OSError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Session metrics CLI — record, finalize, report.

`MetricsCollector` writes `.deepstate/metrics.json`. `setup-session.py` opens
the file at session start; this is how the rest of a run reaches it.

Subcommands:
  record <key> <value>  — set one metric (int, bool or string, inferred)
  increment <key> [n]   — add to an integer metric
  finalize              — stamp completed_at + wall_clock_seconds, print dashboard
  report                — print the dashboard without finalizing

Exit codes:
  0 — ok
  2 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.deepstate import MetricsCollector


def _coerce(raw: str) -> int | str | bool:
    """Infer the value type from the CLI string.

    Metrics are counters, flags and short labels, so bool-then-int-then-str
    covers the space. A quoted "true" that meant the string is not worth
    supporting.
    """
    lowered = raw.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(raw)
    except ValueError:
        return raw


def _collector(planning_dir: Path) -> MetricsCollector:
    return MetricsCollector(state_dir=planning_dir / ".deepstate")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("planning_dir", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record")
    p_record.add_argument("key")
    p_record.add_argument("value")

    p_incr = sub.add_parser("increment")
    p_incr.add_argument("key")
    p_incr.add_argument("amount", nargs="?", type=int, default=1)

    sub.add_parser("finalize")
    sub.add_parser("report")

    args = parser.parse_args()

    try:
        collector = _collector(args.planning_dir)

        if args.command == "record":
            collector.record(args.key, _coerce(args.value))
        elif args.command == "increment":
            collector.increment(args.key, args.amount)
        elif args.command == "finalize":
            collector.finalize()

        print(collector.format_dashboard())
    except OSError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

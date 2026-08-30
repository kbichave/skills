#!/usr/bin/env python3
"""Cross-session run store CLI — report, baseline, prune.

Playbook Stage 6. Reads the append-only run log that `MetricsCollector.finalize`
writes, so the plugin can answer "is this getting better or worse" instead of
only "what happened in this session".

Deliberately does NOT open PRs, file issues, or change any config. It reports.
A human decides what to do about it.

Subcommands:
  report    [--slug S] [--mode M]      counts, modes, median wall clock
  baseline  --metric M [--slug S]      median + MAD, with a trustworthiness flag
  prune     [--max-records N] [--max-age-days D]

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

from lib.metrics_store import (
    MIN_SAMPLES_FOR_BASELINE,
    compute_baseline,
    load_runs,
    metrics_home,
    prune,
    summarize,
)


def cmd_report(args: argparse.Namespace) -> int:
    runs = load_runs(args.store, project_slug=args.slug, mode=args.mode)
    payload = {"store": str(args.store or metrics_home()), **summarize(runs)}
    if not runs:
        payload["note"] = (
            "No runs recorded yet. The store fills as /deep sessions finalize."
        )
    print(json.dumps(payload, indent=2))
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    runs = load_runs(args.store, project_slug=args.slug)
    baseline = compute_baseline(runs, args.metric)
    payload = baseline.to_dict()
    if not baseline.trustworthy:
        # Say so loudly. A median of three runs presented as a baseline is how
        # a monitoring system starts producing confident nonsense.
        payload["note"] = (
            f"n={baseline.n} is below {MIN_SAMPLES_FOR_BASELINE}; treat these "
            "numbers as raw observations, not a baseline, and do not band on them."
        )
    print(json.dumps(payload, indent=2))
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    dropped = prune(
        args.store, max_records=args.max_records, max_age_days=args.max_age_days
    )
    print(json.dumps({"dropped": dropped, "remaining": len(load_runs(args.store))}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=None, help="override the store directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report")
    p_report.add_argument("--slug", default=None)
    p_report.add_argument("--mode", default=None)
    p_report.set_defaults(func=cmd_report)

    p_baseline = sub.add_parser("baseline")
    p_baseline.add_argument("--metric", required=True)
    p_baseline.add_argument("--slug", default=None)
    p_baseline.set_defaults(func=cmd_baseline)

    p_prune = sub.add_parser("prune")
    p_prune.add_argument("--max-records", type=int, default=500)
    p_prune.add_argument("--max-age-days", type=int, default=365)
    p_prune.set_defaults(func=cmd_prune)

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

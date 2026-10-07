#!/usr/bin/env python3
"""Open or close a data-tier run for a session.

Usage:
  data-tier.py start  --session ID [--hours N]
  data-tier.py stop   --session ID
  data-tier.py status --session ID

While a run is open, `warehouse-sql-guard.py` checks every warehouse SQL call
the session makes. The marker expires on its own (default 4 hours), so a run
that crashes before `stop` cannot leave the guard on forever.

Exit codes: 0 ok (status: active), 1 status: inactive, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import sql_guard


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--session", required=True)
    parser.add_argument("--hours", type=float, default=4.0)
    args = parser.parse_args(argv)

    if not args.session.strip():
        print(json.dumps({"error": "empty --session"}))
        return 2

    if args.action == "start":
        path = sql_guard.start(args.session, timedelta(hours=args.hours))
        print(json.dumps({"active": True, "marker": str(path)}))
        return 0
    if args.action == "stop":
        print(json.dumps({"active": False, "removed": sql_guard.stop(args.session)}))
        return 0

    active = sql_guard.is_active(args.session)
    print(json.dumps({"active": active}))
    return 0 if active else 1


if __name__ == "__main__":
    sys.exit(main())

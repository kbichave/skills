#!/usr/bin/env python3
"""Print the active deployment profile as JSON.

Usage:
  deep-profile.py [--repo PATH] [--json]
  deep-profile.py --validate FILE

Prints `{"profile": null}` when no profile applies; that is the generic mode,
not an error. Exit codes: 0 resolved (or none), 2 a profile exists but is
invalid, so the caller can tell a misconfigured profile from a missing one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.deep_profile import ProfileError, load_file, resolve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="accepted; output is always JSON")
    parser.add_argument("--validate", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        profile = load_file(args.validate) if args.validate else resolve(args.repo)
    except ProfileError as exc:
        print(json.dumps({"profile": None, "error": str(exc)}))
        return 2

    print(json.dumps({"profile": profile.to_json() if profile else None}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compare the actual git diff against what the plan said it would touch.

Playbook Stage 3's "diff alignment with plan.md". Reports; does not gate.

Exit codes:
  0 — report produced (whether or not it could be scored)
  2 — usage or I/O error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.plan_diff import alignment, changed_files, read_sections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planning-dir", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", default="HEAD", help="git ref to diff against")
    args = parser.parse_args()

    try:
        sections = read_sections(args.planning_dir / "sections")
        result = alignment(sections, changed_files(args.repo, args.base))
    except OSError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

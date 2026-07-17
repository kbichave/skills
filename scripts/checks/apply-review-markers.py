#!/usr/bin/env python3
"""Insert approved review markers into source files.

Reads an approved-markers JSON payload from stdin and inserts language-aware
comment markers above each flagged line, bottom-up (no line drift) and
idempotently (lines already carrying a "(review):" marker are skipped).

Usage:
    echo '<json>' | uv run --no-project apply-review-markers.py [--dry-run]

Input (stdin, JSON):
    {
      "markers": [
        {"file": "src/api.py", "line": 42, "kind": "CODECHANGE",
         "text": "SEC-003 — parameterize this query"},
        {"file": "src/api.py", "line": 51, "kind": "RECOMMENDATION",
         "text": "collections.Counter — one tested line replaces six"}
      ]
    }

Output (stdout, JSON):
    {"inserted": 2, "skipped": 0, "files": {"src/api.py": 2}, "errors": []}

Exit codes:
    0  markers applied (or dry-run) with no errors
    1  one or more files failed
    2  usage / malformed input
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.comment_markers import Marker, MARKER_SIGNATURE, insert_markers


def _group(markers: list[dict]) -> dict[str, list[Marker]]:
    by_file: dict[str, list[Marker]] = {}
    for m in markers:
        by_file.setdefault(m["file"], []).append(
            Marker(line=int(m["line"]), kind=str(m["kind"]), text=str(m["text"]))
        )
    return by_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Insert approved review markers.")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(sys.stdin.read())
        markers = payload["markers"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(json.dumps({"error": f"malformed input: {exc}"}), file=sys.stderr)
        return 2

    result = {"inserted": 0, "skipped": 0, "files": {}, "errors": []}
    for file_str, file_markers in _group(markers).items():
        path = Path(file_str)
        if not path.is_file():
            result["errors"].append(f"not a file: {file_str}")
            continue
        original = path.read_text()
        before = original.count(MARKER_SIGNATURE)
        updated = insert_markers(original, path.suffix, file_markers)
        added = updated.count(MARKER_SIGNATURE) - before
        result["files"][file_str] = added
        result["inserted"] += added
        result["skipped"] += len(file_markers) - added
        if not args.dry_run and updated != original:
            path.write_text(updated)

    print(json.dumps(result))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

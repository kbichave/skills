"""Find organization identifiers in files this plugin ships.

The warehouse tier carries one organization's patterns, but the plugin must
not say whose. A plain denylist would itself spell the name out, so the
shipped list holds SHA-256 hashes of lowercased 1-3 word n-grams. A file is
tokenized the same way and every n-gram's hash is checked against the list.

`$DEEP_LEAK_TERMS` (comma-separated, plain text) adds local terms, such as an
account identifier or a space key, that only the maintainer's machine checks.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

DENYLIST_SHA256 = frozenset(
    {
        "424c9f63375c13c3be378452df7435ba26b1226144a26ece7696fa9d0b97ff5c",
        "26e5c763a0cf6e096ef107b43cb75d33cb611736a9e6f62662eb6fe3a94f875e",
        "7724cb7db67d20736b2a1f8ba1293588c9a62b99293c6e6061de9ba967724b2b",
        "aeb482d43d4118f72c3a56f337a605611fbaa54e6b04b95a84de3cfd55702fe3",
        "10106d9df99339e967688cfc5998603882f29085a64ac2aac7557acd7f71762c",
        "bb734623631297041f72931a32c7686b9195bf2418330baa17241bc791b0a481",
        "19b6e6e764ef910f03f87de9dd0c7376b2e64126b382e14b0e469860e3080291",
    }
)

MAX_NGRAM = 3
MAX_BYTES = 1_000_000
_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    text: str


def digest(term: str) -> str:
    return hashlib.sha256(" ".join(_TOKEN.findall(term.lower())).encode()).hexdigest()


def denylist() -> frozenset[str]:
    extra = os.environ.get("DEEP_LEAK_TERMS", "")
    local = {digest(t) for t in extra.split(",") if t.strip()}
    return DENYLIST_SHA256 | local


def ngrams(line: str) -> list[str]:
    tokens = _TOKEN.findall(line.lower())
    return [
        " ".join(tokens[i:i + n])
        for n in range(1, MAX_NGRAM + 1)
        for i in range(len(tokens) - n + 1)
    ]


def scan_text(text: str, path: str, hashes: frozenset[str]) -> list[Hit]:
    hits: list[Hit] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if any(digest(g) in hashes for g in ngrams(line)):
            hits.append(Hit(path, number, line.strip()[:120]))
    return hits


def shipped_files(root: Path) -> list[Path]:
    """Tracked plus untracked-but-not-ignored files: what the next commit can carry."""
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    )
    return [root / p for p in out.stdout.splitlines() if p]


def scan_repo(root: Path) -> list[Hit]:
    hashes = denylist()
    hits: list[Hit] = []
    for path in shipped_files(root):
        try:
            if not path.is_file() or path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits.extend(scan_text(text, str(path.relative_to(root)), hashes))
    return hits

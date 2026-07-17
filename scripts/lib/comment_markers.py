"""Deterministic insertion of review markers into source files.

The code-review skill flags findings at specific lines. Rather than have the
model do line arithmetic in prose (error-prone, and against the "script the
deterministic steps" guidance), it hands approved markers to this library,
which inserts language-appropriate comment lines above each flagged line,
bottom-up so earlier insertions never shift later line numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

# Comment style per file extension. Block-style entries carry (open, close).
_LINE_COMMENT = {
    ".py": "#", ".pyi": "#", ".sh": "#", ".bash": "#", ".zsh": "#",
    ".rb": "#", ".pl": "#", ".r": "#", ".yaml": "#", ".yml": "#", ".toml": "#",
    ".ts": "//", ".tsx": "//", ".js": "//", ".jsx": "//", ".mjs": "//", ".cjs": "//",
    ".go": "//", ".java": "//", ".c": "//", ".h": "//", ".cpp": "//", ".hpp": "//",
    ".cs": "//", ".rs": "//", ".swift": "//", ".kt": "//", ".scala": "//", ".php": "//",
    ".sql": "--", ".lua": "--", ".hs": "--",
}
_BLOCK_COMMENT = {
    ".html": ("<!--", "-->"), ".htm": ("<!--", "-->"), ".xml": ("<!--", "-->"),
    ".md": ("<!--", "-->"), ".vue": ("<!--", "-->"),
    ".css": ("/*", "*/"), ".scss": ("/*", "*/"),
}

_DEFAULT_LINE_COMMENT = "#"
MARKER_SIGNATURE = "(review):"


@dataclass
class Marker:
    """A single review marker to insert above ``line`` (1-based)."""

    line: int
    kind: str  # "CODECHANGE" or "RECOMMENDATION"
    text: str


def comment_wrap(ext: str, body: str) -> str:
    """Render ``body`` as a comment for the given file extension."""
    ext = ext.lower()
    if ext in _BLOCK_COMMENT:
        open_tok, close_tok = _BLOCK_COMMENT[ext]
        return f"{open_tok} {body} {close_tok}"
    token = _LINE_COMMENT.get(ext, _DEFAULT_LINE_COMMENT)
    return f"{token} {body}"


def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def insert_markers(text: str, ext: str, markers: list[Marker]) -> str:
    """Return ``text`` with a comment marker inserted above each marker line.

    Bottom-up insertion keeps line numbers stable. A line that already carries
    a ``(review):`` marker directly above it is skipped (idempotent re-runs).
    Out-of-range lines are ignored.
    """
    lines = text.split("\n")
    n = len(lines)
    # Deduplicate by line, keep first; sort descending so inserts don't shift.
    seen: set[int] = set()
    ordered: list[Marker] = []
    for m in sorted(markers, key=lambda x: x.line, reverse=True):
        if m.line in seen:
            continue
        seen.add(m.line)
        ordered.append(m)

    for m in ordered:
        idx = m.line - 1  # 0-based index of the flagged line
        if idx < 0 or idx >= n:
            continue
        prev = lines[idx - 1] if idx > 0 else ""
        if MARKER_SIGNATURE in prev:
            continue  # already annotated
        indent = _indent_of(lines[idx])
        body = f"{m.kind}{MARKER_SIGNATURE} {m.text}"
        lines.insert(idx, f"{indent}{comment_wrap(ext, body)}")

    return "\n".join(lines)

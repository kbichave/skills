"""Compare what a plan said it would touch against what git says changed.

Playbook Stage 3 measures "diff alignment with plan.md". Today nothing does:
`impl-progress.md` records the files Claude *says* it touched, which is a
self-report, not evidence.

The honest complication is that section files do not reliably declare their
files. `agents/section-writer.md` documents a `**File:** \\`path\\`` convention,
but real sessions largely ignore it and mention paths inline in backticks
instead — and a mentioned path is not a promise to edit it. A survey of real
plans found sections declaring ~1.2 paths while mentioning ~9.2.

So this module keeps the two apart and reports which it used:

- **declared** — from `**File:**` lines. A commitment.
- **mentioned** — backticked things that look like source paths. A hint.

When declaration coverage is too low to support a score, `alignment()` says so
instead of producing a number. A confident alignment percentage computed from
hints would be worse than no measurement, because someone would act on it.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Below this share of sections declaring at least one file, refuse to score.
MIN_DECLARATION_COVERAGE = 0.5

_DECLARED_RE = re.compile(r"^\*\*File:\*\*\s*`([^`]+)`", re.MULTILINE)
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")

# Extensions worth treating as a source path when seen in backticks.
_SOURCE_SUFFIXES = frozenset(
    {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
        ".sql", ".yml", ".yaml", ".json", ".toml", ".sh", ".md",
    }
)


@dataclass(frozen=True, slots=True)
class SectionPaths:
    section: str
    declared: tuple[str, ...] = ()
    mentioned: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Alignment:
    scored: bool
    declaration_coverage: float
    sections: int
    planned: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    matched: tuple[str, ...] = ()
    unplanned: tuple[str, ...] = ()
    untouched: tuple[str, ...] = ()
    score: float | None = None
    note: str = ""
    basis: str = "declared"

    def to_dict(self) -> dict:
        return {
            "scored": self.scored,
            "basis": self.basis,
            "declaration_coverage": round(self.declaration_coverage, 3),
            "sections": self.sections,
            "planned": list(self.planned),
            "changed": list(self.changed),
            "matched": list(self.matched),
            "unplanned": list(self.unplanned),
            "untouched": list(self.untouched),
            "score": self.score,
            "note": self.note,
        }


def _looks_like_path(token: str) -> bool:
    token = token.strip()
    if not token or " " in token or token.startswith(("-", "$", "#")):
        return False
    if "/" not in token and not token.startswith("."):
        return False
    return Path(token).suffix.lower() in _SOURCE_SUFFIXES


def extract_paths(text: str, section: str = "") -> SectionPaths:
    declared = tuple(dict.fromkeys(m.strip() for m in _DECLARED_RE.findall(text)))
    mentioned = tuple(
        dict.fromkeys(
            token.strip()
            for token in _BACKTICK_RE.findall(text)
            if _looks_like_path(token)
        )
    )
    return SectionPaths(section=section, declared=declared, mentioned=mentioned)


def read_sections(sections_dir: Path) -> list[SectionPaths]:
    if not sections_dir.is_dir():
        return []
    results: list[SectionPaths] = []
    for path in sorted(sections_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        results.append(extract_paths(text, section=path.stem))
    return results


def changed_files(repo: Path, base: str = "HEAD") -> list[str]:
    """Files changed vs `base`, including untracked. Empty on any git failure."""
    files: set[str] = set()
    for args in (
        ["diff", "--name-only", base],
        ["diff", "--name-only", "--cached"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0:
            files.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(files)


def alignment(sections: list[SectionPaths], changed: list[str]) -> Alignment:
    """Compare planned against changed, refusing to score on weak evidence."""
    total = len(sections)
    if total == 0:
        return Alignment(
            scored=False,
            declaration_coverage=0.0,
            sections=0,
            changed=tuple(changed),
            note="No section files found; nothing to compare against.",
        )

    declaring = sum(1 for s in sections if s.declared)
    coverage = declaring / total

    if coverage >= MIN_DECLARATION_COVERAGE:
        basis = "declared"
        planned = {p for s in sections for p in s.declared}
    else:
        basis = "mentioned"
        planned = {p for s in sections for p in s.mentioned}

    changed_set = set(changed)
    matched = sorted(planned & changed_set)
    unplanned = sorted(changed_set - planned)
    untouched = sorted(planned - changed_set)

    if basis == "mentioned":
        return Alignment(
            scored=False,
            basis=basis,
            declaration_coverage=coverage,
            sections=total,
            planned=tuple(sorted(planned)),
            changed=tuple(changed),
            matched=tuple(matched),
            unplanned=tuple(unplanned),
            untouched=tuple(untouched),
            note=(
                f"Only {declaring}/{total} sections declare files with a "
                "`**File:**` line, so there is no reliable planned set to score "
                "against. Paths merely mentioned in prose are hints, not "
                "commitments. The unplanned list below is still worth reading; "
                "the percentage is deliberately withheld."
            ),
        )

    score = len(matched) / len(changed_set) if changed_set else None
    return Alignment(
        scored=True,
        basis=basis,
        declaration_coverage=coverage,
        sections=total,
        planned=tuple(sorted(planned)),
        changed=tuple(changed),
        matched=tuple(matched),
        unplanned=tuple(unplanned),
        untouched=tuple(untouched),
        score=round(score, 3) if score is not None else None,
        note="" if changed_set else "No changes detected against the base ref.",
    )

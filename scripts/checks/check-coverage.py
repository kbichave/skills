#!/usr/bin/env python3
"""Spec → Sections coverage gate.

Parses claude-spec.md for capability/requirement bullets under known
headings, then asserts each is referenced by at least one section in
sections/index.md.

Blocking gate: emits JSON with `passed: false` and a list of missing
items when coverage is incomplete. Used at the end of plan workflow,
before output-summary.

Output JSON schema:
{
  "passed": bool,
  "total_items": int,
  "covered": [ {"item": "...", "matched_in": ["section-name", ...]} ],
  "missing": [ "...", "..." ],
  "spec_path": "...",
  "index_path": "..."
}

Exit codes:
  0 — passed
  1 — failed (missing items)
  2 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Headings under which bullets are treated as coverage items. Match
# case-insensitively. New headings can be added without code changes
# from a CLI flag.
DEFAULT_COVERAGE_HEADINGS = (
    "Requirements",
    "Capabilities",
    "Acceptance Criteria",
    "Goals",
    "Must Have",
    "Functional Requirements",
    "Non-functional Requirements",
)

# Tokens to drop when normalising an item before substring matching.
# These are filler words common in requirements that hurt match recall.
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "to", "of", "for", "in", "on",
    "with", "by", "as", "be", "is", "are", "must", "should", "shall",
    "can", "will", "would", "may", "have", "has", "support", "supports",
    "provide", "provides", "system", "the system", "users", "user",
})


def parse_spec_items(spec_text: str, headings: tuple[str, ...]) -> list[str]:
    """Extract bullet items under any of `headings` (case-insensitive).

    Bullets are lines starting with `-`, `*`, or `1.`-style numerals.
    Nested bullets (indented) are also captured. Headings are matched
    against any markdown level (#, ##, ###, …).
    """
    items: list[str] = []
    current_under_target = False
    heading_re = re.compile(r"^#+\s*(.+?)\s*$")
    bullet_re = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.+?)\s*$")
    headings_lower = {h.lower() for h in headings}

    for line in spec_text.splitlines():
        h = heading_re.match(line)
        if h:
            title = h.group(1).strip().lower().rstrip(":").strip()
            current_under_target = title in headings_lower
            continue
        if current_under_target:
            b = bullet_re.match(line)
            if b:
                text = b.group(1).strip()
                # Strip trailing parenthetical / inline notes — keep first sentence
                text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
                if text and not text.startswith(("Note", "TODO", "FIXME")):
                    items.append(text)
    return items


def parse_section_names(index_text: str) -> list[str]:
    """Return all section names from sections/index.md.

    Accepts SECTION_MANIFEST blocks (newline-separated section names)
    or bullet-listed sections. Liberal parse — anything that looks like
    a section identifier counts as a candidate match target.
    """
    names: list[str] = []
    in_manifest = False
    for raw in index_text.splitlines():
        line = raw.strip()
        if line.startswith("```") and "SECTION_MANIFEST" in line:
            in_manifest = True
            continue
        if in_manifest and line.startswith("```"):
            in_manifest = False
            continue
        if in_manifest and line:
            # Strip optional `depends_on:` suffix
            name = line.split(":", 1)[0].strip()
            if name:
                names.append(name)
            continue
        # Also pick up `- section-01-foo` style bullets
        m = re.match(r"^\s*(?:[-*]|\d+\.)\s+([a-z0-9][a-z0-9\-_]+)", line)
        if m:
            names.append(m.group(1))
    return names


def _tokenize(text: str) -> set[str]:
    """Lowercase + strip punctuation + drop stopwords."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}


def item_matches_section(item: str, section_name: str, section_body: str = "") -> bool:
    """True iff the item appears to be addressed by this section.

    Match heuristic: at least 2 content tokens from the item appear in
    the section name or body (token-overlap, stopwords removed). A
    1-token item must appear verbatim.
    """
    item_tokens = _tokenize(item)
    if not item_tokens:
        return False
    target = section_name.lower() + " " + section_body.lower()
    target_tokens = _tokenize(target)
    overlap = item_tokens & target_tokens
    if len(item_tokens) == 1:
        return overlap == item_tokens
    return len(overlap) >= 2


def check_coverage(
    planning_dir: Path,
    headings: tuple[str, ...] = DEFAULT_COVERAGE_HEADINGS,
) -> dict:
    """Run the coverage check. Returns JSON-serialisable result dict."""
    spec_path = planning_dir / "claude-spec.md"
    index_path = planning_dir / "sections" / "index.md"

    if not spec_path.exists():
        return {
            "passed": False,
            "error": f"Spec not found: {spec_path}",
            "spec_path": str(spec_path),
            "index_path": str(index_path),
        }
    if not index_path.exists():
        return {
            "passed": False,
            "error": f"Section index not found: {index_path}",
            "spec_path": str(spec_path),
            "index_path": str(index_path),
        }

    items = parse_spec_items(spec_path.read_text(), headings)
    section_names = parse_section_names(index_path.read_text())

    # Pre-load section bodies if available (improves match recall)
    section_bodies: dict[str, str] = {}
    sections_dir = planning_dir / "sections"
    for name in section_names:
        candidate = sections_dir / f"{name}.md"
        if candidate.exists():
            section_bodies[name] = candidate.read_text()

    covered: list[dict] = []
    missing: list[str] = []
    for item in items:
        matches = [
            name for name in section_names
            if item_matches_section(item, name, section_bodies.get(name, ""))
        ]
        if matches:
            covered.append({"item": item, "matched_in": matches})
        else:
            missing.append(item)

    return {
        "passed": len(missing) == 0,
        "total_items": len(items),
        "covered": covered,
        "missing": missing,
        "spec_path": str(spec_path),
        "index_path": str(index_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Spec → sections coverage gate. Blocks plan finalize on missing items.",
    )
    parser.add_argument(
        "--planning-dir", required=True, type=Path,
        help="Planning directory containing claude-spec.md and sections/index.md",
    )
    parser.add_argument(
        "--heading", action="append", default=None,
        help="Additional spec heading to treat as a coverage source. Repeatable. "
             f"Defaults: {', '.join(DEFAULT_COVERAGE_HEADINGS)}",
    )
    args = parser.parse_args()

    headings = tuple(args.heading) if args.heading else DEFAULT_COVERAGE_HEADINGS

    try:
        result = check_coverage(args.planning_dir, headings)
    except OSError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}))
        sys.exit(2)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("passed") else 1)


if __name__ == "__main__":
    main()

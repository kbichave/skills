"""REVIEW.md — a per-repo policy overlay on the rule packs.

The two artifacts answer different questions and must not be merged. The packs
answer *what counts as a defect*: hundreds of rules with stable IDs, severities
and a router that activates them from repo signals — plugin-owned, versioned
with the plugin, shared across every repo. `REVIEW.md` answers *how this repo
wants review conducted and reported*: what to never report, how many nits reach
a human. That is per-repo and the plugin cannot infer it.

Collapsing packs into REVIEW.md would fork the rule corpus into every repo and
destroy rule-ID stability. Skipping REVIEW.md leaves no way for a repo to say
"src/gen/** is generated" or "ruff already runs in CI, don't re-report it".

**The nit cap applies at externalization, never at detection.** The panel stays
exhaustive — that is what makes the verifier's precision math meaningful and the
report file a real audit artifact. The cap trims what reaches chat and the PR,
with the remainder summarized as a count and a pointer to the full report.
Capping detection would trade away the plugin's strongest property to satisfy a
formatting preference.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

REVIEW_FILENAME = "REVIEW.md"
DEFAULT_NIT_CAP = 5

# Severities the panel already produces. REVIEW.md renames them for display; it
# does not invent a new taxonomy.
SEVERITY_ORDER = ("blocking", "important", "nit")

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+`?([^`\n]+?)`?\s*$", re.MULTILINE)
_NUMBER_RE = re.compile(r"^\s*(\d+)\s*$")


@dataclass(frozen=True, slots=True)
class ReviewPolicy:
    excluded_paths: tuple[str, ...] = ()
    excluded_rules: tuple[str, ...] = ()
    nit_cap: int | None = DEFAULT_NIT_CAP
    source: str = "default"

    def to_dict(self) -> dict:
        return {
            "excluded_paths": list(self.excluded_paths),
            "excluded_rules": list(self.excluded_rules),
            "nit_cap": self.nit_cap,
            "source": self.source,
        }


DEFAULT_POLICY = ReviewPolicy()


def _section_body(text: str, *names: str) -> str:
    """Body under the first matching `## <name>`, case-insensitive."""
    wanted = {n.lower() for n in names}
    matches = list(_SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1).strip().lower() not in wanted:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end]
    return ""


def _bullets(body: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in _BULLET_RE.findall(body)
        if item.strip() and not item.strip().startswith("<")
    )


def parse(text: str, *, source: str = REVIEW_FILENAME) -> ReviewPolicy:
    """Parse REVIEW.md. Never raises: an unreadable policy is the default one.

    Deliberately forgiving about structure. This file is hand-edited by a tech
    lead, and a strict parser that rejects it on a heading typo would just get
    the feature switched off.
    """
    excluded_paths = _bullets(_section_body(text, "Exclusions", "Excluded paths"))
    excluded_rules = _bullets(_section_body(text, "Excluded rules", "Suppressed rules"))

    nit_cap: int | None = DEFAULT_NIT_CAP
    cap_body = _section_body(text, "Nit cap", "Nits").strip()
    if cap_body:
        first = cap_body.splitlines()[0].strip()
        if first.lower() in {"none", "unlimited", "off"}:
            nit_cap = None
        else:
            found = re.search(r"\d+", first)
            if found:
                nit_cap = int(found.group())

    return ReviewPolicy(
        excluded_paths=excluded_paths,
        excluded_rules=tuple(r.upper() for r in excluded_rules),
        nit_cap=nit_cap,
        source=source,
    )


def load(repo_root: Path) -> ReviewPolicy:
    """Read `<repo>/REVIEW.md`. Absent file yields the default policy."""
    path = Path(repo_root) / REVIEW_FILENAME
    try:
        return parse(path.read_text(), source=str(path))
    except (OSError, ValueError):
        return DEFAULT_POLICY


def is_excluded_path(rel_path: str, policy: ReviewPolicy) -> bool:
    for pattern in policy.excluded_paths:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(rel_path, pattern[3:]):
            return True
        prefix = pattern.rstrip("*").rstrip("/")
        if prefix and (rel_path == prefix or rel_path.startswith(prefix + "/")):
            return True
    return False


def is_excluded_rule(rule_id: str, policy: ReviewPolicy) -> bool:
    return rule_id.upper() in policy.excluded_rules


def filter_findings(findings: list[dict], policy: ReviewPolicy) -> list[dict]:
    """Drop findings the repo has declared out of scope.

    Applied before rendering AND passed to experts as `excluded_paths`, so
    coverage claims stay honest rather than counting files nobody will read.
    """
    kept = []
    for finding in findings:
        path = str(finding.get("file", ""))
        rule = str(finding.get("rule_id", ""))
        if path and is_excluded_path(path, policy):
            continue
        if rule and is_excluded_rule(rule, policy):
            continue
        kept.append(finding)
    return kept


@dataclass(frozen=True, slots=True)
class Externalized:
    shown: list[dict] = field(default_factory=list)
    withheld: int = 0
    note: str = ""


def externalize(findings: list[dict], policy: ReviewPolicy) -> Externalized:
    """Trim nits for chat and PR output. Detection is untouched.

    Blocking and important findings are never capped — only nits, which is the
    class where volume genuinely drowns the signal.
    """
    if policy.nit_cap is None:
        return Externalized(shown=list(findings))

    shown: list[dict] = []
    nits = 0
    withheld = 0
    for finding in findings:
        if str(finding.get("severity", "")).lower() != "nit":
            shown.append(finding)
            continue
        if nits < policy.nit_cap:
            shown.append(finding)
            nits += 1
        else:
            withheld += 1

    note = ""
    if withheld:
        note = (
            f"{withheld} further nit{'s' if withheld != 1 else ''} not shown here; "
            "all of them are in the full report."
        )
    return Externalized(shown=shown, withheld=withheld, note=note)

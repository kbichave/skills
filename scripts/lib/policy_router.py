"""Project quality rules forward into spec-time obligations.

Playbook Stage 2 wants organizational policy applied *while the spec is written*,
with concerns flagged for a human — not discovered at review time when the code
already exists.

The plugin already owns the corpus and the resolver. `pack_router.detect_signals`
already accepts `spec_text` and does greenfield inference, and
`audit-topic-enumeration.md` already performs this same projection at discovery
time. So this is a projection layer, **never a second resolver**: it imports
`pack_router` and calls it, and a test asserts it yields the same `active_packs`.
Forking the resolution logic is the failure mode to design against.

What it produces is a bounded list of questions the spec should answer, drawn
from rules a human or reviewer must judge. Rules a linter enforces are excluded:
asking a spec author to promise `ruff` will pass is noise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from lib.pack_router import detect_signals, discover_packs, resolve_packs

# Hard cap. The spec phase is already the longest step, and an interrogation is
# how /deep plan stops getting used.
MAX_OBLIGATIONS = 25

# More than this many open concerns means the model is flagging things it could
# have answered from research and the interview.
CONCERN_NORM = 5

# Only rules a human or reviewer must judge. A linter-enforced rule needs no
# promise in a spec — it either passes at Phase 6 or it does not.
SPEC_RELEVANT_ENFORCERS = ("reviewer", "human", "test")
SPEC_RELEVANT_SEVERITIES = ("BLOCK", "WARN")

_RULE_RE = re.compile(r"^###\s+([A-Z]+-\d+):\s*(.+?)\s*$", re.MULTILINE)
_FIELD_RE = re.compile(r"^-\s+\*\*(.+?):\*\*\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Obligation:
    rule_id: str
    title: str
    pack: str
    severity: str
    enforcer: str
    question: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "pack": self.pack,
            "severity": self.severity,
            "enforcer": self.enforcer,
            "question": self.question,
        }


@dataclass(frozen=True, slots=True)
class SpecContext:
    active_packs: tuple[str, ...]
    obligations: tuple[Obligation, ...]
    truncated: bool = False
    mode: str = "advise"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "active_packs": list(self.active_packs),
            "obligations": [o.to_dict() for o in self.obligations],
            "truncated": self.truncated,
            "max_obligations": MAX_OBLIGATIONS,
            "concern_norm": CONCERN_NORM,
        }


def _rule_blocks(text: str) -> list[tuple[str, str, dict[str, str]]]:
    """(rule_id, title, fields) for each `### RULE-NNN: Title` block."""
    blocks: list[tuple[str, str, dict[str, str]]] = []
    matches = list(_RULE_RE.finditer(text))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        fields = {
            key.strip().lower(): value.strip()
            for key, value in _FIELD_RE.findall(text[start:end])
        }
        blocks.append((match.group(1), match.group(2), fields))
    return blocks


def derive_question(title: str, fields: dict[str, str]) -> str:
    """Turn a rule into something a spec author can actually answer.

    Prefers an explicit `spec_question:` when a rule author wrote one, and
    otherwise derives from the required behaviour, so the corpus needs no
    up-front annotation pass and nothing breaks when the line is missing.
    """
    explicit = fields.get("spec_question")
    if explicit:
        return explicit
    behavior = fields.get("required behavior") or fields.get("required behaviour")
    if behavior:
        # First sentence only. Rule bodies often run to several clauses, and
        # splicing all of them into a question produces something that reads as
        # if it were cut off mid-thought.
        first = re.split(r"(?<=[.;])\s+", behavior.strip())[0]
        return f"How will the design satisfy: {first.rstrip('.;,')}?"
    return f"How does the design address {title.lower()}?"


def _is_spec_relevant(fields: dict[str, str]) -> bool:
    severity = fields.get("severity", "").upper()
    enforcer = fields.get("enforcer", "").lower()
    if severity not in SPEC_RELEVANT_SEVERITIES:
        return False
    return any(token in enforcer for token in SPEC_RELEVANT_ENFORCERS)


def obligations_for_pack(pack_dir: Path, pack_name: str) -> list[Obligation]:
    obligations: list[Obligation] = []
    if not pack_dir.is_dir():
        return obligations
    for rule_file in sorted(pack_dir.glob("*.md")):
        if rule_file.name == "index.md":
            continue
        try:
            text = rule_file.read_text()
        except OSError:
            continue
        for rule_id, title, fields in _rule_blocks(text):
            if not _is_spec_relevant(fields):
                continue
            obligations.append(
                Obligation(
                    rule_id=rule_id,
                    title=title,
                    pack=pack_name,
                    severity=fields.get("severity", "").upper(),
                    enforcer=fields.get("enforcer", ""),
                    question=derive_question(title, fields),
                )
            )
    return obligations


def resolve_spec_context(
    target_root: Path,
    packs_dir: Path,
    *,
    spec_text: str | None = None,
    mode: str = "advise",
) -> SpecContext:
    """Active packs plus the obligations their rules place on a spec.

    Calls `pack_router` rather than re-deriving anything. BLOCK rules are
    ordered first so that if the cap truncates, what survives is what matters.
    """
    signals = detect_signals(target_root, spec_text=spec_text)
    resolution = resolve_packs(signals, packs_dir)

    known = discover_packs(packs_dir)
    obligations: list[Obligation] = []
    for pack in resolution.active_packs:
        pack_dir = packs_dir / pack
        if pack in known or pack_dir.is_dir():
            obligations.extend(obligations_for_pack(pack_dir, pack))

    obligations.sort(key=lambda o: (o.severity != "BLOCK", o.rule_id))
    truncated = len(obligations) > MAX_OBLIGATIONS

    return SpecContext(
        active_packs=resolution.active_packs,
        obligations=tuple(obligations[:MAX_OBLIGATIONS]),
        truncated=truncated,
        mode=mode,
    )

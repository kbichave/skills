"""intent.md — the originator's problem statement, before engineering framing.

Playbook Stage 1. This is deliberately NOT the same artifact as `claude-spec.md`:
`auto-spec-synthesis.md` interprets an ask into a precise engineering goal, which
is the right thing to do at plan time and the wrong thing to do here. An intent
records the problem in the originator's own words so the spec can be traced back
to it and so a later reader can tell what was actually asked for.

Stdlib only. Front matter is parsed by hand rather than with PyYAML, which is a
dev-only dependency in pyproject.toml and must not be required at runtime.

The file is the source of truth, not the object. `Intent` is frozen and the
`set_*` helpers return copies, so nothing can drift by in-place mutation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

INTENT_STATUSES: frozenset[str] = frozenset(
    {"draft", "proposed", "accepted", "rejected", "superseded"}
)
TERMINAL_STATUSES: frozenset[str] = frozenset({"accepted", "rejected", "superseded"})
INTENT_SOURCES: frozenset[str] = frozenset({"human", "agent"})

REQUIRED_FRONTMATTER: tuple[str, ...] = (
    "id",
    "title",
    "author",
    "created",
    "status",
    "source",
)

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Problem",
    "Who is affected",
    "Desired outcome",
    "Constraints",
    "Success metrics",
    "Out of scope",
    "Open questions",
)

_SECTION_PROMPTS: dict[str, str] = {
    "Problem": "<originator's own words, minimally edited. Do not translate into engineering terms.>",
    "Who is affected": "<named roles or business units, and roughly how many>",
    "Desired outcome": "<what \"solved\" looks like, in the originator's words>",
    "Constraints": "<budget, deadline, systems that cannot change, compliance, data residency>",
    "Success metrics": "<how we will know, ideally numeric with a baseline>",
    "Out of scope": "<what this deliberately does not cover>",
    "Open questions": "<unresolved; may be empty, must not be omitted>",
}

MAX_SLUG_LEN = 48
MIN_BODY_CHARS = 200

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
_NUMERIC_RE = re.compile(r"\d")


class IntentError(Exception):
    """Raised only by parse(). validate() reports instead of raising."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Intent:
    id: str
    title: str
    author: str
    created: str
    status: str
    source: str = "human"
    body: str = ""
    supersedes: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    decision_reason: str | None = None
    spec: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(title: str, *, max_len: int = MAX_SLUG_LEN) -> str:
    slug = _SLUG_STRIP_RE.sub("-", title.strip().lower()).strip("-")
    return slug[:max_len].rstrip("-")


def new_intent_id(title: str, created: str) -> str:
    """<YYYY-MM-DD>-<slug>. Deterministic, so the same inputs reproduce it."""
    return f"{created[:10]}-{slugify(title)}"


def _scalar(value: str) -> str | None:
    """Unquote a front-matter scalar; bare `null`/empty become None."""
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_list(value: str) -> tuple[str, ...]:
    value = value.strip()
    if not value or value in {"null", "[]", "~"}:
        return ()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return tuple(
        item for item in (_scalar(p) or "" for p in value.split(",")) if item
    )


def _parse_frontmatter(block: str) -> dict[str, str]:
    """Flat `key: value` only. Intent front matter is deliberately flat, so a
    hand parser is honest here rather than a YAML subset that pretends to be
    more than it is."""
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if sep and not key.startswith((" ", "\t")):
            fields[key.strip()] = value.strip()
    return fields


def parse(text: str) -> Intent:
    """Raises IntentError when front matter is absent or unusable."""
    match = _FRONTMATTER_RE.match(text or "")
    if not match:
        raise IntentError(
            "intent.md must open with a YAML front-matter block delimited by ---"
        )
    fields = _parse_frontmatter(match.group(1))
    missing = [k for k in REQUIRED_FRONTMATTER if not fields.get(k)]
    if missing:
        raise IntentError(f"missing required front-matter keys: {', '.join(missing)}")

    return Intent(
        id=_scalar(fields["id"]) or "",
        title=_scalar(fields["title"]) or "",
        author=_scalar(fields["author"]) or "",
        created=_scalar(fields["created"]) or "",
        status=_scalar(fields["status"]) or "",
        source=_scalar(fields.get("source", "human")) or "human",
        body=match.group(2),
        supersedes=_scalar(fields.get("supersedes", "")),
        decided_by=_scalar(fields.get("decided_by", "")),
        decided_at=_scalar(fields.get("decided_at", "")),
        decision_reason=_scalar(fields.get("decision_reason", "")),
        spec=_scalar(fields.get("spec", "")),
        tags=_parse_list(fields.get("tags", "")),
    )


def _emit(key: str, value: str | None) -> str:
    if value is None:
        return f"{key}: null"
    needs_quotes = any(c in value for c in ":#") or value != value.strip()
    return f'{key}: "{value}"' if needs_quotes else f"{key}: {value}"


def render(intent: Intent) -> str:
    """Front matter + body. Round-trips with parse()."""
    tags = "[" + ", ".join(intent.tags) + "]" if intent.tags else "[]"
    lines = [
        "---",
        _emit("id", intent.id),
        _emit("title", intent.title),
        _emit("author", intent.author),
        _emit("created", intent.created),
        _emit("status", intent.status),
        _emit("source", intent.source),
        _emit("supersedes", intent.supersedes),
        _emit("decided_by", intent.decided_by),
        _emit("decided_at", intent.decided_at),
        _emit("decision_reason", intent.decision_reason),
        _emit("spec", intent.spec),
        f"tags: {tags}",
        "---",
        "",
    ]
    body = intent.body if intent.body.startswith("\n") else "\n" + intent.body
    return "\n".join(lines) + body.lstrip("\n")


def default_template(
    *, title: str, author: str, source: str = "human", created: str | None = None
) -> str:
    created = created or utc_now()
    body_parts = [f"# {title}", ""]
    for section in REQUIRED_SECTIONS:
        body_parts += [f"## {section}", _SECTION_PROMPTS[section], ""]
    return render(
        Intent(
            id=new_intent_id(title, created),
            title=title,
            author=author,
            created=created,
            status="draft",
            source=source,
            body="\n".join(body_parts),
        )
    )


def _section_text(body: str, heading: str) -> str:
    """Text under `## <heading>`, up to the next heading of any level."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^#{{1,6}}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def _is_placeholder(text: str) -> bool:
    return not text or (text.startswith("<") and text.endswith(">"))


def validate(text: str) -> ValidationResult:
    """Never raises: the CLI reports these and the agent repairs them."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        intent = parse(text)
    except IntentError as exc:
        return ValidationResult(passed=False, errors=[str(exc)])

    if intent.status not in INTENT_STATUSES:
        errors.append(
            f"unknown status {intent.status!r}; expected one of "
            f"{', '.join(sorted(INTENT_STATUSES))}"
        )
    if intent.source not in INTENT_SOURCES:
        errors.append(
            f"unknown source {intent.source!r}; expected one of "
            f"{', '.join(sorted(INTENT_SOURCES))}"
        )

    try:
        datetime.fromisoformat(intent.created)
    except ValueError:
        errors.append(f"created {intent.created!r} is not an ISO 8601 timestamp")

    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^##\s+{re.escape(section)}\s*$", intent.body, re.MULTILINE):
            errors.append(f"missing required section: ## {section}")

    if _is_placeholder(_section_text(intent.body, "Problem")):
        errors.append("## Problem is empty — an intent with no problem is not an intent")

    expected_id = new_intent_id(intent.title, intent.created)
    if intent.id != expected_id:
        warnings.append(f"id {intent.id!r} does not match title and date ({expected_id!r})")

    if not _NUMERIC_RE.search(_section_text(intent.body, "Success metrics")):
        warnings.append("## Success metrics has no number — how will anyone know it worked?")

    if intent.status == "proposed" and _is_placeholder(
        _section_text(intent.body, "Open questions")
    ):
        warnings.append("## Open questions is empty on a proposed intent")

    if len(intent.body.strip()) < MIN_BODY_CHARS:
        warnings.append(f"body is under {MIN_BODY_CHARS} characters — likely a stub")

    return ValidationResult(passed=not errors, errors=errors, warnings=warnings)


def set_decision(
    intent: Intent,
    *,
    status: str,
    decided_by: str,
    reason: str,
    decided_at: str | None = None,
) -> Intent:
    """Record an accept/reject. Returns a new Intent.

    `decided_by` is required and must be non-empty: a decision record with no
    name attached looks like an audit trail without being one.
    """
    if status not in INTENT_STATUSES:
        raise IntentError(f"unknown status {status!r}")
    if status not in TERMINAL_STATUSES:
        raise IntentError(f"{status!r} is not a decision; expected one of {', '.join(sorted(TERMINAL_STATUSES))}")
    if intent.status in TERMINAL_STATUSES:
        raise IntentError(
            f"intent {intent.id} is already {intent.status}; supersede it instead of re-deciding"
        )
    if not decided_by.strip():
        raise IntentError("decided_by is required — an unattributed decision is not a record")

    return replace(
        intent,
        status=status,
        decided_by=decided_by.strip(),
        decided_at=decided_at or utc_now(),
        decision_reason=reason.strip() or None,
    )


def set_spec(intent: Intent, spec_path: str) -> Intent:
    """Link the spec produced from this intent, which is what makes the
    intent-to-spec elapsed time measurable."""
    return replace(intent, spec=spec_path)

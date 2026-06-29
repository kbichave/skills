"""Generate quality artifacts from the active packs and detect staleness.

Build step 8 of the quality pipeline. Two concerns:

* **Fingerprint / freshness** — a content hash over the pack source
  (``references/quality/**``). Any generated artifact (the implement gate, the
  deferred Qodo exports) records the fingerprint it was built from; if the live
  fingerprint differs, the artifact is stale and must be regenerated. This is the
  "source-of-truth hash" the plan calls for: packs are the source, everything
  else is output.

* **Qodo export (deferred, flag-gated)** — concatenate the active packs' family
  files into a ``best_practices.md`` slice, capped at the model-friendly size.
  Off by default (decision Q10); the machinery lives here so the seam exists.

Stdlib only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Qodo best_practices.md should stay well under the model's effective limit.
QODO_MAX_LINES = 800


def packs_fingerprint(packs_dir: Path) -> str:
    """Stable SHA-256 over every file under ``packs_dir`` (path + content).

    Sorted by relative path so the hash is order-independent and reproducible.
    """
    packs_dir = Path(packs_dir)
    h = hashlib.sha256()
    for path in sorted(packs_dir.rglob("*")):
        if not path.is_file() or path.name.startswith(".packs-hash"):
            continue
        rel = path.relative_to(packs_dir).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _fingerprint_file(packs_dir: Path) -> Path:
    return Path(packs_dir) / ".packs-hash"


def write_fingerprint(packs_dir: Path) -> str:
    """Persist the current fingerprint; return it."""
    fp = packs_fingerprint(packs_dir)
    _fingerprint_file(packs_dir).write_text(fp + "\n", encoding="utf-8")
    return fp


def is_fresh(packs_dir: Path) -> bool:
    """True iff a stored fingerprint exists and matches the live one."""
    marker = _fingerprint_file(packs_dir)
    if not marker.exists():
        return False
    stored = marker.read_text(encoding="utf-8").strip()
    return stored == packs_fingerprint(packs_dir)


def generate_best_practices(active_packs: list[str] | tuple[str, ...], packs_dir: Path) -> str:
    """Concatenate active packs' family files into a Qodo best_practices.md slice.

    Deferred behind a flag (Q10) — provided so the export seam exists. Capped at
    :data:`QODO_MAX_LINES` lines; truncation is marked so it is never silent.
    """
    packs_dir = Path(packs_dir)
    lines: list[str] = ["# Organization best practices (generated — do not edit)", ""]
    for pack in active_packs:
        pack_dir = packs_dir / pack
        if not pack_dir.is_dir():
            continue
        for family in sorted(pack_dir.glob("*.md")):
            if family.name == "index.md":
                continue
            lines.append(family.read_text(encoding="utf-8").rstrip())
            lines.append("")
    if len(lines) > QODO_MAX_LINES:
        lines = lines[: QODO_MAX_LINES - 1]
        lines.append("<!-- truncated at QODO_MAX_LINES; split packs or raise the cap -->")
    return "\n".join(lines).rstrip() + "\n"

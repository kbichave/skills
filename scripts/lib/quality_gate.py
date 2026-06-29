"""Build the implement-phase quality gate command list.

Given the packs resolved by :mod:`lib.pack_router` and the target's detected
languages, compose the concrete lint/type/security/test commands to run at
implement Phase 6. Each language has an adapter under ``lint/<lang>/adapter.json``
mapping pack name → commands and carrying per-language thresholds (Go relaxes
size/param limits per the quality-pipeline decisions).

``--quality=legacy`` (see :func:`lib.pack_router.resolve_quality_mode`) bypasses
pack composition and returns the pre-quality fixed Python gate, so existing
``/deep`` users can opt out during rollout.

Stdlib only. Commands are returned as strings (with a ``{paths}`` placeholder
the caller substitutes); this module composes, it does not execute.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


# Language detected → adapter directory name under lint/.
_LANG_DIR = {
    "python": "python",
    "typescript": "ts",
    "javascript": "ts",
    "go": "go",
}

# Pre-quality fixed gate, restored by --quality=legacy.
LEGACY_GATE = (
    "ruff check .",
    "mypy --strict scripts",
    "bandit -q -r scripts",
    "pytest --cov --cov-fail-under=85",
)


@dataclass(frozen=True)
class GatePlan:
    """Composed gate: ordered commands + the coverage floor that applies."""

    commands: tuple[str, ...]
    diff_coverage_min: int = 85
    mode: str = "active"


def _load_adapter(lang: str, adapters_dir: Path) -> dict[str, object]:
    sub = _LANG_DIR.get(lang)
    if sub is None:
        return {}
    path = adapters_dir / sub / "adapter.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _adapter_packs(adapter: dict[str, object]) -> dict[str, list[str]]:
    packs = adapter.get("packs", {})
    if not isinstance(packs, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, cmds in packs.items():
        if isinstance(cmds, list):
            out[str(name)] = [str(c) for c in cmds]
    return out


def build_gate(
    active_packs: list[str] | tuple[str, ...],
    languages: list[str] | tuple[str, ...],
    adapters_dir: Path,
    *,
    mode: str = "active",
) -> GatePlan:
    """Compose the gate for the given active packs + languages.

    Legacy mode ignores packs/languages and returns :data:`LEGACY_GATE`.
    Otherwise, for each language adapter, emit the commands for each active pack
    that adapter defines, de-duplicated and ending with the language's test
    command.
    """
    if mode == "legacy":
        return GatePlan(commands=LEGACY_GATE, mode="legacy")

    commands: list[str] = []
    seen: set[str] = set()

    def add(cmd: str) -> None:
        if cmd not in seen:
            seen.add(cmd)
            commands.append(cmd)

    # Deterministic order: language order as given, packs with core first.
    ordered_packs = [p for p in ("core",) if p in active_packs]
    ordered_packs += [p for p in active_packs if p != "core"]

    for lang in languages:
        adapter = _load_adapter(lang, adapters_dir)
        if not adapter:
            continue
        pack_cmds = _adapter_packs(adapter)
        for pack in ordered_packs:
            for cmd in pack_cmds.get(pack, []):
                add(cmd)
        test_cmd = adapter.get("test")
        if isinstance(test_cmd, str):
            add(test_cmd)

    return GatePlan(commands=tuple(commands), mode="active")

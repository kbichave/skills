"""Golden-fixture harness for the quality pack resolver.

Build step 0 of the quality pipeline (bead ``deep-plan-enhanced-8dj``). This
pins the resolver contract via synthetic target repos before the resolver
itself is written.

Two groups:

* ``resolve_quality_mode`` tests — the ``--quality=legacy`` rollback switch.
  Self-contained, green now.
* Pack-resolution tests — assert ``resolve_packs(detect_signals(target))``
  yields the expected active set per fixture target. ``xfail`` until step 3
  (bead ``deep-plan-enhanced-jwt``) implements detection + matching, at which
  point these flip to passing and the xfail can be made ``strict``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import pack_router
from lib.pack_router import TargetSignals, resolve_quality_mode


FIXTURES = Path(__file__).parent / "fixtures" / "quality"
PACKS_DIR = FIXTURES / "packs"
TARGETS_DIR = FIXTURES / "targets"


# --- quality-mode rollback switch (green now) -----------------------------


def test_quality_mode_defaults_to_active():
    assert resolve_quality_mode(None, env={}) == "active"


def test_quality_mode_cli_overrides_env():
    assert resolve_quality_mode("legacy", env={"DEEP_QUALITY_MODE": "active"}) == "legacy"


def test_quality_mode_from_env():
    assert resolve_quality_mode(None, env={"DEEP_QUALITY_MODE": "legacy"}) == "legacy"


def test_quality_mode_blank_is_active():
    assert resolve_quality_mode("", env={}) == "active"


def test_quality_mode_invalid_raises():
    with pytest.raises(ValueError):
        resolve_quality_mode("yolo", env={})


# --- pack resolution (xfail until step 3) ---------------------------------

# target dir, spec text (used when no diff), expected active pack set
RESOLUTION_CASES = [
    pytest.param(
        "py_backend",
        "Add a refund endpoint to the payments API.",
        {"core", "service"},
        id="python-backend-api",
    ),
    pytest.param(
        "ts_frontend",
        "Fix the contrast on the primary button.",
        {"core", "frontend"},
        id="typescript-frontend-ui",
    ),
    pytest.param(
        "greenfield",
        "Build a new FastAPI backend service exposing a REST API.",
        {"core", "service"},
        id="greenfield-spec-driven",
    ),
]


@pytest.mark.parametrize("target, spec, expected", RESOLUTION_CASES)
def test_resolve_packs_for_target(target: str, spec: str, expected: set[str]):
    signals = pack_router.detect_signals(TARGETS_DIR / target, spec_text=spec)
    resolution = pack_router.resolve_packs(signals, PACKS_DIR)
    assert set(resolution.active_packs) == expected


def test_core_always_active_even_with_no_signals():
    resolution = pack_router.resolve_packs(TargetSignals(), PACKS_DIR)
    assert "core" in resolution.active_packs


# --- real authored packs (references/quality) -----------------------------

REAL_PACKS = Path(__file__).parent.parent / "references" / "quality"


def test_real_packs_all_parse():
    packs = pack_router.discover_packs(REAL_PACKS)
    names = {p["name"] for p in packs}
    assert {"core", "service", "delivery", "frontend", "library", "perf", "supply", "iac", "llm"} <= names
    for p in packs:
        assert p["name"]
        assert p["provides_rules"], f"{p['name']} has no provides_rules"


def test_real_packs_python_backend_resolves_service():
    signals = pack_router.detect_signals(
        TARGETS_DIR / "py_backend", spec_text="Add a refund endpoint to the payments API."
    )
    resolution = pack_router.resolve_packs(signals, REAL_PACKS)
    assert set(resolution.active_packs) == {"core", "service"}


def test_real_packs_ts_frontend_resolves_frontend_not_service():
    signals = pack_router.detect_signals(
        TARGETS_DIR / "ts_frontend", spec_text="Fix the contrast on the primary button."
    )
    resolution = pack_router.resolve_packs(signals, REAL_PACKS)
    assert set(resolution.active_packs) == {"core", "frontend"}

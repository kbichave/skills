"""Tests for the implement-phase quality gate composer (build step 4)."""

from __future__ import annotations

from pathlib import Path

from lib.quality_gate import LEGACY_GATE, build_gate

ADAPTERS = Path(__file__).parent.parent / "lint"


def test_legacy_mode_returns_fixed_gate():
    plan = build_gate(["core", "service"], ["python"], ADAPTERS, mode="legacy")
    assert plan.mode == "legacy"
    assert plan.commands == LEGACY_GATE


def test_python_core_emits_ruff_mypy_bandit():
    plan = build_gate(["core"], ["python"], ADAPTERS)
    joined = " ".join(plan.commands)
    assert "ruff check" in joined
    assert "mypy --strict" in joined
    assert "bandit" in joined
    assert plan.commands[-1].startswith("pytest")


def test_service_pack_adds_semgrep():
    plan = build_gate(["core", "service"], ["python"], ADAPTERS)
    assert any("semgrep" in c for c in plan.commands)


def test_frontend_pack_adds_a11y_for_ts():
    plan = build_gate(["core", "frontend"], ["typescript"], ADAPTERS)
    assert any("jsx-a11y" in c for c in plan.commands)
    # service-only tools must not appear for a frontend resolution
    assert not any("go test" in c for c in plan.commands)


def test_go_uses_relaxed_complexity_threshold():
    plan = build_gate(["core"], ["go"], ADAPTERS)
    assert any("gocyclo -over 15" in c for c in plan.commands)


def test_commands_deduplicated():
    plan = build_gate(["core", "llm"], ["python"], ADAPTERS)
    assert len(plan.commands) == len(set(plan.commands))


def test_core_runs_first():
    plan = build_gate(["service", "core"], ["python"], ADAPTERS)
    assert plan.commands[0].startswith("ruff")


def test_unknown_language_yields_empty_gate():
    plan = build_gate(["core"], ["rust"], ADAPTERS)
    assert plan.commands == ()

"""Tests for ``scripts/lib/context_metrics.py``."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lib import context_metrics as cm
from lib.context_metrics import (
    BridgeState,
    bridge_path,
    classify_level,
    compute_used_input_tokens,
    compute_used_percentage,
    format_warning,
    is_stale,
    load_user_overrides,
    read_bridge,
    resolve_context_size,
    should_emit,
    write_bridge,
    build_envelope,
)


def make_state(**overrides) -> BridgeState:
    defaults = dict(
        session_id="s1",
        model_id="claude-opus-4-7",
        model_display="Opus 4.7",
        context_window_size=1_000_000,
        used_input_tokens=0,
        used_percentage=0.0,
        level="normal",
        current_step_id=None,
        current_step_title=None,
        planning_dir=None,
        mode=None,
        last_emitted_level=None,
        tool_calls_since_emit=0,
        ts=time.time(),
    )
    defaults.update(overrides)
    return BridgeState(**defaults)


class TestResolveContextSize:
    def test_stdin_size_wins(self) -> None:
        assert resolve_context_size("claude-opus-4-7", 500_000, {}) == 500_000

    def test_overrides_used_when_stdin_missing(self) -> None:
        assert resolve_context_size("custom-model", None, {"custom-model": 42}) == 42

    def test_fallback_table_haiku(self) -> None:
        assert resolve_context_size("claude-haiku-4-5-20251001", None, {}) == 200_000

    def test_fallback_table_opus(self) -> None:
        assert resolve_context_size("claude-opus-4-7", None, {}) == 1_000_000

    def test_default_when_unknown(self) -> None:
        assert resolve_context_size("mystery-model", None, {}) == cm.DEFAULT_CONTEXT_SIZE

    def test_zero_stdin_ignored(self) -> None:
        assert resolve_context_size("claude-opus-4-7", 0, {}) == 1_000_000


class TestUsedTokens:
    def test_sum_all_input_buckets(self) -> None:
        usage = {
            "input_tokens": 100,
            "cache_creation_input_tokens": 50,
            "cache_read_input_tokens": 25,
            "output_tokens": 999,
        }
        assert compute_used_input_tokens(usage) == 175

    def test_missing_buckets_default_zero(self) -> None:
        assert compute_used_input_tokens({"input_tokens": 10}) == 10

    def test_none_returns_zero(self) -> None:
        assert compute_used_input_tokens(None) == 0

    def test_empty_returns_zero(self) -> None:
        assert compute_used_input_tokens({}) == 0


class TestUsedPercentage:
    def test_simple_ratio(self) -> None:
        assert compute_used_percentage(50_000, 200_000) == 25.0

    def test_clamp_above_100(self) -> None:
        assert compute_used_percentage(300_000, 200_000) == 100.0

    def test_clamp_below_zero(self) -> None:
        assert compute_used_percentage(-1, 200_000) == 0.0

    def test_zero_context_size_safe(self) -> None:
        assert compute_used_percentage(100, 0) == 0.0


class TestClassifyLevel:
    @pytest.mark.parametrize(
        "pct,expected",
        [
            (0.0, "normal"),
            (50.0, "normal"),
            (64.9, "normal"),
            (65.0, "warning"),
            (74.9, "warning"),
            (75.0, "critical"),
            (99.9, "critical"),
            (100.0, "critical"),
        ],
    )
    def test_boundaries(self, pct: float, expected: str) -> None:
        assert classify_level(pct) == expected


class TestShouldEmit:
    def test_normal_never_emits(self) -> None:
        assert should_emit("normal", None, 100) is False
        assert should_emit("normal", "warning", 100) is False

    def test_first_warning_emits(self) -> None:
        assert should_emit("warning", None, 0) is True

    def test_repeat_same_level_debounced(self) -> None:
        assert should_emit("warning", "warning", 0) is False
        assert should_emit("warning", "warning", cm.DEBOUNCE_TOOL_CALLS - 1) is False
        assert should_emit("warning", "warning", cm.DEBOUNCE_TOOL_CALLS) is True

    def test_escalation_bypasses_debounce(self) -> None:
        assert should_emit("critical", "warning", 0) is True

    def test_decay_emits(self) -> None:
        # Decay warning→… well, warning is still emitted, but a level CHANGE
        # always emits (here warning after a prior critical, e.g. after a /compact).
        assert should_emit("warning", "critical", 0) is True


class TestBridgeIO:
    def test_roundtrip(self, tmp_path: Path) -> None:
        state = make_state(
            used_percentage=72.5,
            level="warning",
            current_step_id="execute-research",
            current_step_title="Execute Research",
            planning_dir="/tmp/pd",
            mode="plan",
            last_emitted_level="warning",
            tool_calls_since_emit=3,
        )
        path = tmp_path / "bridge.json"
        write_bridge(state, path)
        loaded = read_bridge(path)
        assert loaded is not None
        assert loaded.used_percentage == 72.5
        assert loaded.level == "warning"
        assert loaded.current_step_id == "execute-research"
        assert loaded.tool_calls_since_emit == 3

    def test_atomic_write_no_partial(self, tmp_path: Path) -> None:
        state = make_state()
        path = tmp_path / "bridge.json"
        write_bridge(state, path)
        # No leftover tmp files in the directory
        leftovers = [
            p for p in tmp_path.iterdir() if p.name.startswith("bridge.json.")
        ]
        assert leftovers == []

    def test_missing_returns_none(self, tmp_path: Path) -> None:
        assert read_bridge(tmp_path / "missing.json") is None

    def test_corrupt_returns_none(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.json"
        path.write_text("not json {{")
        assert read_bridge(path) is None

    def test_bridge_path_default(self, tmp_path: Path) -> None:
        p = bridge_path("abc-123", tmp_dir=tmp_path)
        assert p == tmp_path / "deep-ctx-abc-123.json"


class TestStaleness:
    def test_fresh_not_stale(self) -> None:
        s = make_state(ts=time.time())
        assert is_stale(s) is False

    def test_old_is_stale(self) -> None:
        s = make_state(ts=time.time() - 120)
        assert is_stale(s) is True

    def test_custom_max_age(self) -> None:
        s = make_state(ts=time.time() - 10)
        assert is_stale(s, max_age_seconds=5) is True
        assert is_stale(s, max_age_seconds=60) is False


class TestUserOverrides:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_user_overrides(tmp_path / "nope.json") == {}

    def test_loaded(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        path.write_text(json.dumps({"claude-foo": 123456, "bad": "not-int"}))
        result = load_user_overrides(path)
        assert result == {"claude-foo": 123456}

    def test_corrupt_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        path.write_text("not json")
        assert load_user_overrides(path) == {}


class TestFormatWarning:
    def test_normal_returns_empty(self) -> None:
        s = make_state(level="normal", used_percentage=10.0)
        assert format_warning(s) == ""

    def test_warning_mentions_step(self) -> None:
        s = make_state(
            level="warning",
            used_percentage=68.0,
            used_input_tokens=680_000,
            current_step_id="detailed-interview",
            current_step_title="Detailed Interview",
            mode="plan",
        )
        msg = format_warning(s)
        assert "WARNING" in msg
        assert "68.0%" in msg
        assert "detailed-interview" in msg
        assert "Detailed Interview" in msg
        assert "plan mode" in msg

    def test_critical_mentions_prime(self) -> None:
        s = make_state(level="critical", used_percentage=82.0)
        msg = format_warning(s)
        assert "CRITICAL" in msg
        assert "prime" in msg
        assert "/clear" in msg

    def test_caps_message_length(self) -> None:
        s = make_state(
            level="critical",
            used_percentage=80.0,
            current_step_title="X" * 5000,
        )
        msg = format_warning(s)
        assert len(msg) <= 1500


class TestEnvelope:
    def test_shape(self) -> None:
        env = build_envelope("hi")
        assert env == {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "hi",
            }
        }

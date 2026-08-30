"""Tests for the PreToolUse guardrail layer.

Two things these tests exist to protect:
  1. The guard fails open. A crash, a malformed config or a weird payload must
     never block an edit — that is the failure mode that gets a safety feature
     ripped out.
  2. The zero-config default blocks nothing except credentials. Protected paths
     are opt-in per repo; secrets are universal.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lib.guard import (
    ALLOW,
    Decision,
    GuardConfig,
    ProtectedRule,
    SecretRule,
    decide,
    extract_target,
    formatter_for,
    is_secret_exempt,
    load_guard_config,
    match_protected,
    relativize,
    render_pre_output,
    resolve_config_paths,
    scan_secrets,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GH_TOKEN = "ghp_" + "a" * 36


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    return tmp_path


def write_repo_config(repo: Path, data: dict) -> None:
    (repo / ".claude" / "deep-guard.json").write_text(json.dumps(data))


def defaults_config(repo: Path) -> GuardConfig:
    return load_guard_config(repo, plugin_root=PLUGIN_ROOT)


class TestConfigResolution:
    def test_defaults_layer_comes_first(self, repo):
        paths = resolve_config_paths(repo, None, PLUGIN_ROOT)
        assert paths[0] == PLUGIN_ROOT / "guard-defaults.json"

    def test_repo_config_overrides_defaults(self, repo):
        write_repo_config(repo, {"enabled": False})
        assert defaults_config(repo).enabled is False

    def test_repo_protected_paths_are_added(self, repo):
        write_repo_config(
            repo, {"protected_paths": [{"glob": "migrations/**", "reason": "immutable"}]}
        )
        cfg = defaults_config(repo)
        assert any(r.glob == "migrations/**" for r in cfg.protected)

    def test_inherit_false_resets_accumulated_lists(self, repo):
        write_repo_config(repo, {"inherit": False, "secret_patterns": []})
        assert defaults_config(repo).secrets == ()

    def test_malformed_config_is_skipped_not_raised(self, repo):
        (repo / ".claude" / "deep-guard.json").write_text("{not json")
        cfg = defaults_config(repo)
        assert cfg.secrets, "defaults should survive a broken repo layer"

    def test_missing_config_is_not_an_error(self, tmp_path):
        assert load_guard_config(tmp_path, plugin_root=PLUGIN_ROOT).enabled is True

    def test_action_defaults_to_ask_and_rejects_junk(self, repo):
        write_repo_config(
            repo,
            {
                "protected_paths": [
                    {"glob": "a/**", "reason": "r"},
                    {"glob": "b/**", "reason": "r", "action": "explode"},
                ]
            },
        )
        cfg = defaults_config(repo)
        assert [r.action for r in cfg.protected] == ["ask", "ask"]


class TestShippedDefaults:
    """The plugin baseline must be zero-false-positive."""

    def test_protected_paths_ship_empty(self):
        assert load_guard_config(Path("/nonexistent"), plugin_root=PLUGIN_ROOT).protected == ()

    def test_formatters_ship_empty(self):
        assert load_guard_config(Path("/nonexistent"), plugin_root=PLUGIN_ROOT).formatters == ()

    def test_secret_patterns_ship_populated(self):
        assert len(load_guard_config(Path("/nonexistent"), plugin_root=PLUGIN_ROOT).secrets) >= 8

    def test_no_generic_password_pattern(self):
        """A bare `password=` regex is the single largest source of false
        positives, and bandit/semgrep already cover it at Phase 6."""
        cfg = load_guard_config(Path("/nonexistent"), plugin_root=PLUGIN_ROOT)
        for rule in cfg.secrets:
            lowered = rule.regex.lower()
            assert "password" not in lowered or "://" in lowered


class TestExtractTarget:
    def test_write(self):
        path, content = extract_target("Write", {"file_path": "/r/a.py", "content": "x"})
        assert (path.as_posix(), content) == ("/r/a.py", "x")

    def test_edit_uses_new_string(self):
        _, content = extract_target("Edit", {"file_path": "/r/a.py", "new_string": "y"})
        assert content == "y"

    def test_multiedit_concatenates(self):
        _, content = extract_target(
            "MultiEdit",
            {"file_path": "/r/a.py", "edits": [{"new_string": "a"}, {"new_string": "b"}]},
        )
        assert content == "a\nb"

    def test_notebook_edit(self):
        path, content = extract_target(
            "NotebookEdit", {"notebook_path": "/r/n.ipynb", "new_source": "z"}
        )
        assert (path.as_posix(), content) == ("/r/n.ipynb", "z")

    def test_unknown_tool_yields_nothing(self):
        assert extract_target("Bash", {"command": "ls"}) == (None, "")

    def test_missing_path_yields_none(self):
        assert extract_target("Write", {"content": "x"})[0] is None


class TestGlobMatching:
    @pytest.mark.parametrize(
        "rel_path,glob,expected",
        [
            ("src/generated/a.py", "src/generated/**", True),
            ("src/generated/a/b/c.py", "src/generated/**", True),
            ("src/generated", "src/generated/**", True),
            ("src/hand/a.py", "src/generated/**", False),
            # A leading **/ has to mean "at any depth, including none".
            ("README.md", "**/*.md", True),
            ("docs/a/b.md", "**/*.md", True),
            ("a.py", "**/*.md", False),
            ("tests/fixtures/x.pem", "**/tests/fixtures/**", True),
        ],
    )
    def test_match(self, rel_path, glob, expected):
        cfg = GuardConfig(protected=(ProtectedRule(glob=glob, reason="r"),))
        assert bool(match_protected(rel_path, cfg)) is expected


class TestSecretScanning:
    def test_detects_aws_key(self, repo):
        hits = scan_secrets(f'K = "{AWS_KEY}"', "conf.py", defaults_config(repo))
        assert [r.id for r, _ in hits] == ["SEC-AWS"]

    def test_reports_line_number(self, repo):
        hits = scan_secrets(f'a\nb\nK="{AWS_KEY}"', "conf.py", defaults_config(repo))
        assert hits[0][1] == 3

    def test_markdown_is_exempt(self, repo):
        assert scan_secrets(GH_TOKEN, "docs/guide.md", defaults_config(repo)) == []

    def test_fixtures_are_exempt(self, repo):
        assert scan_secrets(GH_TOKEN, "tests/fixtures/creds.py", defaults_config(repo)) == []

    def test_ordinary_source_is_not_exempt(self, repo):
        assert not is_secret_exempt("src/app.py", defaults_config(repo))

    def test_clean_content_yields_nothing(self, repo):
        assert scan_secrets("x = 1", "src/app.py", defaults_config(repo)) == []

    def test_scan_is_capped(self):
        cfg = GuardConfig(
            secrets=(SecretRule("T", "NEEDLE", "test"),), max_scan_bytes=10
        )
        assert scan_secrets("x" * 5000 + "NEEDLE", "a.py", cfg) == []

    def test_bad_regex_disables_only_that_rule(self):
        cfg = GuardConfig(
            secrets=(SecretRule("BAD", "([", "broken"), SecretRule("OK", "NEEDLE", "ok"))
        )
        assert [r.id for r, _ in scan_secrets("NEEDLE", "a.py", cfg)] == ["OK"]


class TestDecide:
    def test_clean_write_is_allowed(self, repo):
        d = decide("Write", {"file_path": str(repo / "a.py"), "content": "x=1"}, repo, defaults_config(repo))
        assert d == ALLOW

    def test_secret_is_denied(self, repo):
        d = decide(
            "Write",
            {"file_path": str(repo / "a.py"), "content": f'K="{AWS_KEY}"'},
            repo,
            defaults_config(repo),
        )
        assert d.action == "deny"
        assert d.rule_id == "SEC-AWS"

    def test_protected_path_asks_by_default(self, repo):
        write_repo_config(repo, {"protected_paths": [{"glob": "gen/**", "reason": "generated"}]})
        d = decide("Edit", {"file_path": str(repo / "gen" / "a.py"), "new_string": "x"}, repo, defaults_config(repo))
        assert d.action == "ask"

    def test_protected_path_can_opt_into_deny(self, repo):
        write_repo_config(
            repo,
            {"protected_paths": [{"glob": "gen/**", "reason": "generated", "action": "deny"}]},
        )
        d = decide("Edit", {"file_path": str(repo / "gen" / "a.py"), "new_string": "x"}, repo, defaults_config(repo))
        assert d.action == "deny"

    def test_secrets_outrank_protected_paths(self, repo):
        """A protected path is sometimes a legitimate override. A credential
        never is, so the deny has to win."""
        write_repo_config(repo, {"protected_paths": [{"glob": "gen/**", "reason": "generated"}]})
        d = decide(
            "Write",
            {"file_path": str(repo / "gen" / "a.py"), "content": f'K="{AWS_KEY}"'},
            repo,
            defaults_config(repo),
        )
        assert d.action == "deny"
        assert d.rule_id == "SEC-AWS"

    def test_disabled_config_allows_everything(self, repo):
        write_repo_config(repo, {"enabled": False})
        d = decide(
            "Write",
            {"file_path": str(repo / "a.py"), "content": f'K="{AWS_KEY}"'},
            repo,
            defaults_config(repo),
        )
        assert d == ALLOW

    def test_env_kill_switch_allows_everything(self, repo, monkeypatch):
        monkeypatch.setenv("DEEP_GUARD", "off")
        d = decide(
            "Write",
            {"file_path": str(repo / "a.py"), "content": f'K="{AWS_KEY}"'},
            repo,
            defaults_config(repo),
        )
        assert d == ALLOW

    def test_non_write_tool_is_allowed(self, repo):
        assert decide("Bash", {"command": "ls"}, repo, defaults_config(repo)) == ALLOW

    def test_empty_ruleset_short_circuits(self, repo):
        empty = GuardConfig(protected=(), secrets=())
        assert decide("Write", {"file_path": "a.py", "content": AWS_KEY}, repo, empty) == ALLOW


class TestRenderPreOutput:
    def test_allow_renders_nothing(self):
        assert render_pre_output(ALLOW) is None

    def test_uses_modern_envelope_not_deprecated_shape(self):
        """The two orphaned pre-tool-use scripts used {"decision": "allow"},
        which Claude Code no longer honours."""
        out = render_pre_output(Decision("deny", "nope", "SEC-AWS"))
        assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "decision" not in out

    def test_ask_is_distinguishable_from_deny(self):
        out = render_pre_output(Decision("ask", "hmm", "gen/**"))
        assert out["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_reason_names_the_config_and_the_escape_hatch(self, repo):
        """A block message that does not say how to unblock is a bad block."""
        d = decide(
            "Write",
            {"file_path": str(repo / "a.py"), "content": f'K="{AWS_KEY}"'},
            repo,
            defaults_config(repo),
        )
        assert "deep-guard.json" in d.reason
        assert "DEEP_GUARD=off" in d.reason
        assert "SEC-AWS" in d.reason


class TestRelativize:
    def test_inside_repo(self, tmp_path):
        assert relativize(tmp_path / "src" / "a.py", tmp_path) == "src/a.py"

    def test_outside_repo_falls_back_to_absolute(self, tmp_path):
        assert relativize(Path("/etc/passwd"), tmp_path) == "/etc/passwd"


class TestFormatters:
    def test_none_by_default(self, repo):
        assert formatter_for("a.py", defaults_config(repo)) is None

    def test_configured_formatter_matches(self, repo):
        write_repo_config(
            repo, {"format_on_edit": [{"glob": "**/*.py", "command": "ruff format {file}"}]}
        )
        rule = formatter_for("src/a.py", defaults_config(repo))
        assert rule is not None and "{file}" in rule.command


class TestScanCost:
    """The hook runs on every Write/Edit, so the decision path is on the hot
    path. On an M-series mac with the 8 shipped patterns: 1 KB is 0.1 ms, 50 KB
    is 1.8 ms, the 256 KB cap is 9.4 ms. A CI runner measured 31 ms for the same
    cap case.

    That spread is why there are no absolute wall-clock assertions here. An
    absolute threshold either flakes on a slow runner or is set so high it
    asserts nothing. What actually needs protecting is that scanning stays
    roughly linear in input size — a catastrophically backtracking regex is the
    realistic regression, and it shows up as superlinear growth on any machine.
    """

    def _mean_ms(self, repo, cfg, content: str, runs: int = 5) -> float:
        payload = {"file_path": str(repo / "big.py"), "content": content}
        start = time.perf_counter()
        for _ in range(runs):
            decide("Write", payload, repo, cfg)
        return (time.perf_counter() - start) / runs * 1000

    def test_scaling_stays_roughly_linear(self, repo):
        """32x the input should cost far less than 32x-squared the time.

        Machine-independent because it compares the implementation against
        itself. The bound is loose on purpose: it is a blowup detector, not a
        benchmark.
        """
        cfg = defaults_config(repo)
        small = self._mean_ms(repo, cfg, "x = 1\n" * 1400)      # ~8 KB
        large = self._mean_ms(repo, cfg, "x = 1\n" * 45000)     # at the 256 KB cap

        if small <= 0:  # clock resolution on a very fast machine
            pytest.skip("timer resolution too coarse to compare")

        # Linear would be ~32x. Allow generous headroom for noise and fixed
        # overhead; catastrophic backtracking lands orders of magnitude above.
        assert (large / small) < 200

    def test_scan_stops_at_the_cap(self, repo):
        """The deterministic half of the same guarantee: content past
        max_scan_bytes is never examined, so cost is bounded regardless of how
        large the payload gets."""
        cfg = defaults_config(repo)
        beyond_cap = "x = 1\n" * 60000 + AWS_KEY
        assert scan_secrets(beyond_cap, "src/a.py", cfg) == []

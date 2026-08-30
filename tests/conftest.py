"""Shared pytest fixtures for deep-plan tests."""

import sys
from pathlib import Path

import pytest
import json

# Add scripts directory to Python path so lib imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture(autouse=True)
def isolated_sessions_root(tmp_path_factory, monkeypatch):
    """Keep session state out of the developer's real ~/.claude.

    Autouse and unconditional. Without it the suite creates a session directory
    per test per run under the user's home; when pytest recycles a tmp path the
    slug hashes to an existing directory, so a "new session" test resumes
    instead and fails. That flake only appears on a machine that has run the
    suite before, never in CI where home is fresh — the worst combination,
    because CI stays green while the dev sees failures.
    """
    root = tmp_path_factory.mktemp("deep-sessions")

    # Covers subprocess invocations and any not-yet-imported module.
    monkeypatch.setenv("DEEP_SESSIONS_ROOT", str(root))

    # Session markers too. These are read back by later tests, so a marker
    # written by one test could otherwise decide another test's answer.
    monkeypatch.setenv("DEEP_STATE_HOME", str(tmp_path_factory.mktemp("claude-home")))

    # setup-session.py binds SESSIONS_ROOT at import time, so a module already
    # loaded by an earlier test needs the attribute patched directly.
    for module in list(sys.modules.values()):
        if module is not None and hasattr(module, "SESSIONS_ROOT"):
            monkeypatch.setattr(module, "SESSIONS_ROOT", root, raising=False)

    return root


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_config(fixtures_dir):
    """Load sample config for testing."""
    config_path = fixtures_dir / "sample_config.json"
    return json.loads(config_path.read_text())


@pytest.fixture
def sample_prompts_dir(fixtures_dir):
    """Return path to sample prompts directory."""
    return fixtures_dir / "sample_prompts"


@pytest.fixture
def sample_plan_content(fixtures_dir):
    """Load sample plan content for testing."""
    plan_path = fixtures_dir / "sample_plan.md"
    return plan_path.read_text()


@pytest.fixture
def mock_env(monkeypatch):
    """Factory fixture to set environment variables."""
    def _set_env(**kwargs):
        for key, value in kwargs.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
    return _set_env

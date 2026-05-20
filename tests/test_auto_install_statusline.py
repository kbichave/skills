"""Tests for ``scripts/hooks/auto-install-statusline.py``."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "scripts" / "hooks" / "auto-install-statusline.py"


@pytest.fixture
def hook_module():
    spec = importlib.util.spec_from_file_location("auto_install_statusline", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def isolated(monkeypatch, tmp_path: Path, hook_module):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(hook_module, "SETTINGS_PATH", settings)
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    monkeypatch.delenv("DEEP_DISABLE_STATUSLINE_INSTALL", raising=False)
    return settings


def test_skips_when_already_installed(isolated, hook_module, monkeypatch, capsys) -> None:
    isolated.write_text(
        json.dumps(
            {"statusLine": {"type": "command", "command": "x", "deepInstalledBy": hook_module.DEEP_MARKER}}
        )
    )
    spawn = MagicMock()
    monkeypatch.setattr(hook_module.subprocess, "run", spawn)
    rc = hook_module.main()
    assert rc == 0
    spawn.assert_not_called()
    assert capsys.readouterr().out == ""


def test_skips_when_disabled(isolated, hook_module, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DEEP_DISABLE_STATUSLINE_INSTALL", "1")
    spawn = MagicMock()
    monkeypatch.setattr(hook_module.subprocess, "run", spawn)
    rc = hook_module.main()
    assert rc == 0
    spawn.assert_not_called()
    assert capsys.readouterr().out == ""


def test_runs_installer_and_emits_notice(isolated, hook_module, monkeypatch, capsys) -> None:
    spawn = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(hook_module.subprocess, "run", spawn)
    rc = hook_module.main()
    assert rc == 0
    spawn.assert_called_once()
    args = spawn.call_args[0][0]
    assert args[0] == "uv"
    assert args[1] == "run"
    assert args[2].endswith("install-statusline.py")
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "statusLine" in payload["hookSpecificOutput"]["additionalContext"]


def test_installer_failure_silent(isolated, hook_module, monkeypatch, capsys) -> None:
    spawn = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="boom"))
    monkeypatch.setattr(hook_module.subprocess, "run", spawn)
    rc = hook_module.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_installer_missing_silent(isolated, hook_module, monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "nowhere"))
    spawn = MagicMock()
    monkeypatch.setattr(hook_module.subprocess, "run", spawn)
    rc = hook_module.main()
    assert rc == 0
    spawn.assert_not_called()
    assert capsys.readouterr().out == ""

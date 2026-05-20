"""Tests for ``scripts/checks/install-statusline.py``."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PATH = REPO_ROOT / "scripts" / "checks" / "install-statusline.py"


@pytest.fixture
def install_module():
    spec = importlib.util.spec_from_file_location("install_statusline", INSTALL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch, install_module):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(install_module, "SETTINGS_PATH", settings)
    return settings


def test_install_creates_file(isolated_settings, install_module, capsys) -> None:
    rc = install_module.main([])
    assert rc == 0
    assert isolated_settings.exists()
    data = json.loads(isolated_settings.read_text())
    sl = data["statusLine"]
    assert sl["type"] == "command"
    assert "deep-statusline.py" in sl["command"]
    assert sl["deepInstalledBy"] == install_module.DEEP_MARKER


def test_install_backs_up_existing(isolated_settings, install_module) -> None:
    isolated_settings.write_text(
        json.dumps({"statusLine": {"type": "command", "command": "my-bar"}})
    )
    rc = install_module.main([])
    assert rc == 0
    backups = list(isolated_settings.parent.glob("settings.json.deep-backup-*"))
    assert len(backups) == 1
    backup_data = json.loads(backups[0].read_text())
    assert backup_data["statusLine"]["command"] == "my-bar"
    new = json.loads(isolated_settings.read_text())
    assert new["statusLine"]["deepInstalledBy"] == install_module.DEEP_MARKER


def test_install_idempotent(isolated_settings, install_module) -> None:
    install_module.main([])
    install_module.main([])
    backups = list(isolated_settings.parent.glob("settings.json.deep-backup-*"))
    assert backups == []  # already-installed path skips backup


def test_check_exits_0_when_installed(isolated_settings, install_module) -> None:
    install_module.main([])
    assert install_module.main(["--check"]) == 0


def test_check_exits_1_when_absent(isolated_settings, install_module) -> None:
    assert install_module.main(["--check"]) == 1


def test_check_exits_1_when_other_present(isolated_settings, install_module) -> None:
    isolated_settings.write_text(
        json.dumps({"statusLine": {"type": "command", "command": "their-bar"}})
    )
    assert install_module.main(["--check"]) == 1


def test_uninstall_restores_backup(isolated_settings, install_module) -> None:
    isolated_settings.write_text(
        json.dumps({"statusLine": {"type": "command", "command": "my-bar"}})
    )
    install_module.main([])
    install_module.main(["--uninstall"])
    data = json.loads(isolated_settings.read_text())
    assert data["statusLine"]["command"] == "my-bar"


def test_uninstall_with_no_prior_removes_entry(
    isolated_settings, install_module
) -> None:
    install_module.main([])
    install_module.main(["--uninstall"])
    data = json.loads(isolated_settings.read_text())
    assert "statusLine" not in data


def test_uninstall_when_not_installed_is_noop(
    isolated_settings, install_module
) -> None:
    isolated_settings.write_text(
        json.dumps({"statusLine": {"type": "command", "command": "their-bar"}})
    )
    install_module.main(["--uninstall"])
    data = json.loads(isolated_settings.read_text())
    assert data["statusLine"]["command"] == "their-bar"

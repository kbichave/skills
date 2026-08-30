"""The four places a version is declared must agree.

`marketplace.json` sat at 5.4.1 through the 5.5.0, 5.6.0, 5.6.1 and 5.7.0-5.14.0
releases. It is the manifest the installer reads, so the published version
silently lagged the code by ten releases while every other file looked correct.

Nothing catches that by eye — the files are far apart and only one of them
matters at install time. Hence a test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = ROOT / ".claude-plugin" / "marketplace.json"
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def plugin_version() -> str:
    return json.loads(PLUGIN_JSON.read_text())["version"]


def marketplace_versions() -> tuple[str, str]:
    data = json.loads(MARKETPLACE_JSON.read_text())
    deep = next(p for p in data["plugins"] if p["name"] == "deep")
    return data["version"], deep["version"]


def pyproject_version() -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(), re.MULTILINE)
    assert match, "pyproject.toml has no version"
    return match.group(1)


def latest_changelog_version() -> str:
    match = re.search(r"^##\s*\[(\d+\.\d+\.\d+)\]", CHANGELOG.read_text(), re.MULTILINE)
    assert match, "CHANGELOG.md has no versioned heading"
    return match.group(1)


class TestVersionConsistency:
    def test_all_declarations_agree(self):
        market_top, market_plugin = marketplace_versions()
        assert {
            plugin_version(),
            market_top,
            market_plugin,
            pyproject_version(),
        } == {plugin_version()}, (
            "plugin.json, marketplace.json (both fields) and pyproject.toml "
            "must declare the same version"
        )

    def test_marketplace_matches_plugin(self):
        """The specific drift that happened: marketplace.json is what the
        installer reads, so a stale value ships an old version silently."""
        _, market_plugin = marketplace_versions()
        assert market_plugin == plugin_version()

    def test_changelog_documents_the_current_version(self):
        assert latest_changelog_version() == plugin_version(), (
            "the top CHANGELOG entry should be the version being shipped"
        )

    @pytest.mark.parametrize(
        "getter",
        [plugin_version, pyproject_version, lambda: marketplace_versions()[1]],
    )
    def test_versions_are_semver(self, getter):
        assert _SEMVER.match(getter())

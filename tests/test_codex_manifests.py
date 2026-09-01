"""The Codex manifests must stay in step with the Claude Code ones.

Two manifests maintained by hand in parallel is precisely how
`.claude-plugin/marketplace.json` sat at 5.4.1 through ten releases while every
other file moved on. The Codex pair is generated from the Claude pair, and this
is the guard that keeps them generated.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SYNC = ROOT / "scripts" / "checks" / "sync-codex-manifests.py"

CLAUDE_PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
CODEX_PLUGIN = ROOT / ".codex-plugin" / "plugin.json"
CODEX_MARKET = ROOT / ".agents" / "plugins" / "marketplace.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


class TestGeneratedFilesAreCurrent:
    def test_check_reports_no_drift(self):
        """Run the generator in --check mode; a non-zero exit means someone
        edited a Claude manifest without regenerating."""
        result = subprocess.run(
            [sys.executable, str(SYNC), "--check"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        assert result.returncode == 0, (
            "Codex manifests are stale. Run "
            "`uv run scripts/checks/sync-codex-manifests.py`.\n" + result.stdout
        )

    def test_both_files_exist(self):
        assert CODEX_PLUGIN.exists()
        assert CODEX_MARKET.exists()

    def test_marked_as_generated(self):
        """A hand-edit is a mistake, so the file has to say so."""
        for path in (CODEX_PLUGIN, CODEX_MARKET):
            assert "Do not edit by hand" in load(path)["_generated"]


class TestCodexPluginShape:
    def test_version_matches_claude(self):
        assert load(CODEX_PLUGIN)["version"] == load(CLAUDE_PLUGIN)["version"]

    def test_name_matches_claude(self):
        assert load(CODEX_PLUGIN)["name"] == load(CLAUDE_PLUGIN)["name"]

    def test_points_at_the_shared_skills_tree(self):
        """One skills/ directory serves both hosts; that is the whole reason
        the port is cheap."""
        assert load(CODEX_PLUGIN)["skills"] == "./skills/"

    def test_skills_directory_actually_exists(self):
        assert (ROOT / "skills").is_dir()


class TestCodexMarketplaceShape:
    def test_declares_the_deep_plugin(self):
        names = [p["name"] for p in load(CODEX_MARKET)["plugins"]]
        assert "deep" in names

    def test_source_uses_the_nested_codex_form(self):
        """Codex nests source as an object; Claude Code uses a bare string.
        Getting this wrong makes the plugin silently un-installable."""
        source = load(CODEX_MARKET)["plugins"][0]["source"]
        assert isinstance(source, dict)
        assert source["source"] == "local"


class TestSharedSkillFormat:
    @pytest.mark.parametrize(
        "skill", ["deep", "code-review", "humanizer", "no-op-remover"]
    )
    def test_frontmatter_has_the_keys_both_hosts_require(self, skill):
        """Both Claude Code and Codex trigger a skill from `name` +
        `description`, so the same file works on both — provided both keys are
        present."""
        text = (ROOT / "skills" / skill / "SKILL.md").read_text()
        assert text.startswith("---"), f"{skill} has no frontmatter"
        block = text.split("---", 2)[1]
        assert "name:" in block
        assert "description:" in block

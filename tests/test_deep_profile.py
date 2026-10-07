"""Deployment profile resolution and validation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from lib import deep_profile

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "references" / "profiles" / "example.toml"
CLI = ROOT / "scripts" / "checks" / "deep-profile.py"


@pytest.fixture(autouse=True)
def no_env_profile(monkeypatch):
    monkeypatch.delenv("DEEP_PROFILE", raising=False)


def _write(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.toml"
    path.write_text(body)
    return path


class TestExample:
    def test_example_validates(self):
        profile = deep_profile.load_file(EXAMPLE)
        assert profile.name == "example"
        assert profile.data["ci_schema_pattern"]
        assert {s["type"] for s in profile.data["knowledge_sources"]} <= deep_profile.KNOWLEDGE_TYPES

    def test_example_keeps_top_level_keys_top_level(self):
        data = deep_profile.load_file(EXAMPLE).data
        for key in ("check_systems", "business_units", "pii_column_patterns"):
            assert key in data, f"{key} got nested under a table"


class TestValidate:
    def test_key_after_table_header_is_flagged(self, tmp_path):
        path = _write(tmp_path, "p", '[warehouse]\ntool = ""\ncheck_systems = ["x"]\n')
        with pytest.raises(deep_profile.ProfileError, match="nested under"):
            deep_profile.load_file(path)

    def test_unknown_key(self, tmp_path):
        path = _write(tmp_path, "p", 'nmae = "typo"\n')
        with pytest.raises(deep_profile.ProfileError, match="unknown key"):
            deep_profile.load_file(path)

    def test_bad_knowledge_type(self, tmp_path):
        path = _write(tmp_path, "p", '[[knowledge_sources]]\ntype = "wiki"\n')
        with pytest.raises(deep_profile.ProfileError, match="knowledge_sources"):
            deep_profile.load_file(path)

    def test_bad_toml(self, tmp_path):
        path = _write(tmp_path, "p", "name = \n")
        with pytest.raises(deep_profile.ProfileError):
            deep_profile.load_file(path)


class TestResolve:
    def test_none_without_profiles(self, tmp_path):
        assert deep_profile.resolve(tmp_path) is None

    def test_env_by_name(self, monkeypatch):
        _write(deep_profile.profiles_dir(), "acme", 'name = "acme"\n')
        monkeypatch.setenv("DEEP_PROFILE", "acme")
        assert deep_profile.resolve().name == "acme"

    def test_env_by_path(self, monkeypatch):
        monkeypatch.setenv("DEEP_PROFILE", str(EXAMPLE))
        assert deep_profile.resolve().name == "example"

    def test_env_missing_file_raises(self, monkeypatch):
        monkeypatch.setenv("DEEP_PROFILE", "nope")
        with pytest.raises(deep_profile.ProfileError):
            deep_profile.resolve()

    def test_match_by_remote(self, tmp_path, monkeypatch):
        _write(deep_profile.profiles_dir(), "acme",
               'name = "acme"\nmatch_remotes = ["github.com/acme-org/"]\n')
        monkeypatch.setattr(deep_profile, "origin_url",
                            lambda repo: "git@github.com:acme-org/dw.git")
        assert deep_profile.resolve(tmp_path).name == "acme"
        monkeypatch.setattr(deep_profile, "origin_url",
                            lambda repo: "https://github.com/acme-org/dw.git")
        assert deep_profile.resolve(tmp_path).name == "acme"
        monkeypatch.setattr(deep_profile, "origin_url",
                            lambda repo: "https://github.com/other-org/dw.git")
        assert deep_profile.resolve(tmp_path) is None

    @pytest.mark.parametrize(
        "url",
        ["git@github.com:acme-org/dw.git", "https://github.com/acme-org/dw.git",
         "https://user@github.com/acme-org/dw.git", "ssh://git@github.com/acme-org/dw.git"],
    )
    def test_normalize_remote(self, url):
        assert deep_profile.normalize_remote(url) == "github.com/acme-org/dw.git"


class TestCli:
    def _cli(self, *args: str) -> subprocess.CompletedProcess:
        full_env = {k: v for k, v in os.environ.items() if k != "DEEP_PROFILE"}
        return subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                              text=True, env=full_env, timeout=10, cwd=ROOT, check=False)

    def test_validate_example(self):
        result = self._cli("--validate", str(EXAMPLE))
        assert result.returncode == 0
        assert json.loads(result.stdout)["profile"]["name"] == "example"

    def test_invalid_profile_exits_2(self, tmp_path):
        bad = _write(tmp_path, "bad", "nmae = 1\n")
        result = self._cli("--validate", str(bad))
        assert result.returncode == 2
        assert json.loads(result.stdout)["profile"] is None

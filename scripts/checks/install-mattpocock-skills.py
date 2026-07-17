#!/usr/bin/env python3
"""Install mattpocock skills directly from GitHub into ~/.claude/skills.

One-time setup script. Shallow-clones https://github.com/mattpocock/skills,
copies the requested skill directories verbatim (upstream names, no renames),
and records provenance + content hashes in ~/.claude/skills/skills-lock.json.

Usage:
    uv run scripts/checks/install-mattpocock-skills.py [skill ...]

With no arguments installs the default set the /deep flows depend on:
grill-me, grilling, handoff. Re-running updates existing installs to the
current upstream content.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

UPSTREAM = "https://github.com/mattpocock/skills"
DEFAULT_SKILLS = ["grill-me", "grilling", "handoff"]
SKILLS_DIR = Path.home() / ".claude" / "skills"
LOCK_FILE = SKILLS_DIR / "skills-lock.json"


def clone_upstream(dest: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--depth", "1", UPSTREAM, str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    return dest


def find_skill_dir(repo: Path, name: str) -> Path | None:
    matches = [p.parent for p in repo.glob(f"skills/**/{name}/SKILL.md")]
    return matches[0] if matches else None


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lock() -> dict:
    if LOCK_FILE.exists():
        return json.loads(LOCK_FILE.read_text())
    return {"version": 1, "skills": {}}


def main(argv: list[str]) -> int:
    names = argv or DEFAULT_SKILLS
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    lock = load_lock()

    with tempfile.TemporaryDirectory() as tmp:
        repo = clone_upstream(Path(tmp) / "mattpocock-skills")
        failed = []
        for name in names:
            src = find_skill_dir(repo, name)
            if src is None:
                print(f"  ✗ {name}: not found in {UPSTREAM}", file=sys.stderr)
                failed.append(name)
                continue
            dest = SKILLS_DIR / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
            lock["skills"][name] = {
                "source": "mattpocock/skills",
                "sourceType": "github",
                "skillPath": f"{src.relative_to(repo)}/SKILL.md",
                "computedHash": sha256_of(dest / "SKILL.md"),
            }
            print(f"  ✓ {name} ← {src.relative_to(repo)}")

    LOCK_FILE.write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Lock file updated: {LOCK_FILE}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

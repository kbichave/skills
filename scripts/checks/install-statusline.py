#!/usr/bin/env python3
"""Install / uninstall the deep-statusline entry in ``~/.claude/settings.json``.

Plugins cannot ship a top-level ``statusLine`` config — Claude Code only
honors ``agent`` and ``subagentStatusLine`` keys in a plugin's ``settings.json``.
This helper writes the user-level entry safely:

- Backs up any existing ``statusLine`` block before overwriting.
- Marks our entry with a ``deepInstalledBy`` field so uninstall can identify it.
- ``--uninstall`` restores the most recent backup (or removes the entry if none).
- ``--check`` prints whether the entry is installed; exits 0 if installed, 1 otherwise.

Usage:

    uv run scripts/checks/install-statusline.py             # install
    uv run scripts/checks/install-statusline.py --check     # status check
    uv run scripts/checks/install-statusline.py --uninstall # remove + restore backup
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
DEEP_MARKER = "deep-plan-enhanced"


def script_command(plugin_root: Path) -> str:
    """Absolute uv-run command for the statusline script."""
    return f"uv run {plugin_root / 'scripts' / 'hooks' / 'deep-statusline.py'}"


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def make_backup(path: Path, existing_statusline: dict) -> Path:
    ts = int(time.time())
    backup_path = path.with_name(f"{path.name}.deep-backup-{ts}")
    payload = {"statusLine": existing_statusline}
    with backup_path.open("w") as f:
        json.dump(payload, f, indent=2)
    return backup_path


def find_latest_backup(path: Path) -> Path | None:
    parent = path.parent
    if not parent.exists():
        return None
    candidates = sorted(
        parent.glob(f"{path.name}.deep-backup-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def is_deep_entry(entry: dict | None) -> bool:
    return isinstance(entry, dict) and entry.get("deepInstalledBy") == DEEP_MARKER


def cmd_install(args: argparse.Namespace, plugin_root: Path) -> int:
    settings = load_settings(SETTINGS_PATH)
    existing = settings.get("statusLine")

    if is_deep_entry(existing) and not args.force:
        print(f"deep-statusline already installed at {SETTINGS_PATH}")
        return 0

    backup_path: Path | None = None
    if existing and not is_deep_entry(existing):
        backup_path = make_backup(SETTINGS_PATH, existing)
        print(f"Existing statusLine backed up to {backup_path}")

    new_entry = {
        "type": "command",
        "command": script_command(plugin_root),
        "padding": 2,
        "refreshInterval": 5,
        "deepInstalledBy": DEEP_MARKER,
    }
    settings["statusLine"] = new_entry
    save_settings(SETTINGS_PATH, settings)
    print(f"Installed deep-statusline → {SETTINGS_PATH}")
    if backup_path is not None:
        print(
            "Restore previous statusLine with:\n"
            f"  uv run {Path(__file__).resolve()} --uninstall"
        )
    return 0


def cmd_uninstall(args: argparse.Namespace, plugin_root: Path) -> int:
    settings = load_settings(SETTINGS_PATH)
    current = settings.get("statusLine")
    if not is_deep_entry(current):
        print("deep-statusline not installed; nothing to do.")
        return 0

    backup = find_latest_backup(SETTINGS_PATH)
    if backup is not None:
        try:
            with backup.open() as f:
                backup_data = json.load(f)
            restored = backup_data.get("statusLine")
            if restored is not None:
                settings["statusLine"] = restored
                save_settings(SETTINGS_PATH, settings)
                # Keep backup file around for safety; do not delete.
                print(f"Restored previous statusLine from {backup}")
                return 0
        except (json.JSONDecodeError, OSError):
            print(f"Backup {backup} unreadable; removing deep entry only.")

    settings.pop("statusLine", None)
    save_settings(SETTINGS_PATH, settings)
    print("Removed deep-statusline entry (no backup restored).")
    return 0


def cmd_check(args: argparse.Namespace, plugin_root: Path) -> int:
    settings = load_settings(SETTINGS_PATH)
    current = settings.get("statusLine")
    if is_deep_entry(current):
        print(f"installed: {SETTINGS_PATH}")
        return 0
    if current:
        print(f"other statusLine present (not deep): {SETTINGS_PATH}")
        return 1
    print(f"not installed: {SETTINGS_PATH}")
    return 1


def resolve_plugin_root() -> Path:
    env = os.environ.get("DEEP_PLUGIN_ROOT")
    if env:
        return Path(env)
    # scripts/checks/install-statusline.py → plugin root is two levels up.
    return Path(__file__).resolve().parent.parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--uninstall", action="store_true", help="restore previous statusLine")
    group.add_argument("--check", action="store_true", help="report install status; exit 0 if installed")
    parser.add_argument("--force", action="store_true", help="overwrite existing deep entry")
    args = parser.parse_args(argv)

    plugin_root = resolve_plugin_root()

    if args.uninstall:
        return cmd_uninstall(args, plugin_root)
    if args.check:
        return cmd_check(args, plugin_root)
    return cmd_install(args, plugin_root)


if __name__ == "__main__":
    sys.exit(main())

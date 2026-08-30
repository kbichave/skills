"""Deterministic PreToolUse guardrails for /deep implement.

Pure decision logic — no process spawning, no I/O beyond config reads. The hook
scripts are thin adapters over this module so behaviour is unit-testable without
a subprocess.

Stdlib only, and it must stay fast: the hook runs on every Write/Edit, so the
decision path is budgeted under 5 ms for a 256 KB payload. That is why config is
memoised on (path, mtime) and regexes are compiled once and cached with it.

Policy: `deny` is reserved for credentials, where no override is legitimate.
Protected paths use `ask`, so the engineer clears them with a keystroke instead
of editing JSON mid-flow.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

GUARD_OFF_ENV = "DEEP_GUARD"
GUARD_CONFIG_ENV = "DEEP_GUARD_CONFIG"

REPO_CONFIG_RELPATH = Path(".claude") / "deep-guard.json"
PLANNING_CONFIG_NAME = "deep-guard.json"
DEFAULTS_NAME = "guard-defaults.json"

DEFAULT_MAX_SCAN_BYTES = 262144

# Tools whose payload carries a file path plus new content.
_TARGET_EXTRACTORS = {
    "Write": ("file_path", "content"),
    "Edit": ("file_path", "new_string"),
    "NotebookEdit": ("notebook_path", "new_source"),
}


@dataclass(frozen=True)
class ProtectedRule:
    glob: str
    reason: str
    action: str = "ask"  # "ask" | "deny"


@dataclass(frozen=True)
class SecretRule:
    id: str
    regex: str
    reason: str


@dataclass(frozen=True)
class FormatRule:
    glob: str
    command: str  # contains a "{file}" placeholder
    timeout_ms: int = 3000


@dataclass(frozen=True)
class GuardConfig:
    enabled: bool = True
    fail_open: bool = True
    guard_bash: bool = False
    max_scan_bytes: int = DEFAULT_MAX_SCAN_BYTES
    protected: tuple[ProtectedRule, ...] = ()
    secrets: tuple[SecretRule, ...] = ()
    allow_secret_paths: tuple[str, ...] = ()
    formatters: tuple[FormatRule, ...] = ()
    source: str = "defaults"


@dataclass(frozen=True)
class Decision:
    action: str  # "allow" | "ask" | "deny"
    reason: str = ""
    rule_id: str = ""


ALLOW = Decision("allow")

# (path, st_mtime_ns) -> parsed layer dict
_layer_cache: dict[tuple[str, int], dict] = {}
# regex string -> compiled pattern
_regex_cache: dict[str, re.Pattern[str]] = {}


def _compiled(pattern: str) -> re.Pattern[str] | None:
    """Compile and cache. A bad regex in config disables that rule rather than
    taking down the hook."""
    cached = _regex_cache.get(pattern)
    if cached is not None:
        return cached
    try:
        compiled = re.compile(pattern)
    except re.error:
        return None
    _regex_cache[pattern] = compiled
    return compiled


def guard_disabled_by_env() -> bool:
    return os.environ.get(GUARD_OFF_ENV, "").strip().lower() in {"off", "0", "false"}


def resolve_config_paths(
    cwd: Path,
    planning_dir: Path | None = None,
    plugin_root: Path | None = None,
) -> list[Path]:
    """Lowest precedence first, so later layers override earlier ones."""
    paths: list[Path] = []
    if plugin_root:
        paths.append(Path(plugin_root) / DEFAULTS_NAME)
    if planning_dir:
        paths.append(Path(planning_dir) / PLANNING_CONFIG_NAME)
    paths.append(Path(cwd) / REPO_CONFIG_RELPATH)
    explicit = os.environ.get(GUARD_CONFIG_ENV)
    if explicit:
        paths.append(Path(explicit))
    return paths


def _read_layer(path: Path) -> dict | None:
    """Read and cache one config layer. Malformed layers are skipped, never
    raised — a typo in JSON must not block every edit in the repo."""
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path), stat.st_mtime_ns)
    if key in _layer_cache:
        return _layer_cache[key]
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    _layer_cache[key] = data
    return data


def _merge_layer(cfg: GuardConfig, layer: dict, path: Path) -> GuardConfig:
    """Apply one layer. Lists concatenate onto what is already accumulated
    unless the layer sets "inherit": false, which resets them."""
    inherit = layer.get("inherit", True)
    protected = () if not inherit else cfg.protected
    secrets = () if not inherit else cfg.secrets
    allow_paths = () if not inherit else cfg.allow_secret_paths
    formatters = () if not inherit else cfg.formatters

    for raw in layer.get("protected_paths", []) or []:
        if isinstance(raw, dict) and raw.get("glob"):
            action = raw.get("action", "ask")
            protected += (
                ProtectedRule(
                    glob=raw["glob"],
                    reason=raw.get("reason", "protected path"),
                    action=action if action in {"ask", "deny"} else "ask",
                ),
            )

    for raw in layer.get("secret_patterns", []) or []:
        if isinstance(raw, dict) and raw.get("regex") and raw.get("id"):
            secrets += (
                SecretRule(
                    id=raw["id"],
                    regex=raw["regex"],
                    reason=raw.get("reason", "credential material"),
                ),
            )

    allow_paths += tuple(
        p for p in (layer.get("allow_secret_paths", []) or []) if isinstance(p, str)
    )

    for raw in layer.get("format_on_edit", []) or []:
        if isinstance(raw, dict) and raw.get("glob") and raw.get("command"):
            formatters += (
                FormatRule(
                    glob=raw["glob"],
                    command=raw["command"],
                    timeout_ms=int(raw.get("timeout_ms", 3000)),
                ),
            )

    return replace(
        cfg,
        enabled=bool(layer.get("enabled", cfg.enabled)),
        fail_open=bool(layer.get("fail_open", cfg.fail_open)),
        guard_bash=bool(layer.get("guard_bash", cfg.guard_bash)),
        max_scan_bytes=int(layer.get("max_scan_bytes", cfg.max_scan_bytes)),
        protected=protected,
        secrets=secrets,
        allow_secret_paths=allow_paths,
        formatters=formatters,
        source=f"{cfg.source},{path}" if cfg.source != "defaults" else str(path),
    )


def load_guard_config(
    cwd: Path,
    *,
    planning_dir: Path | None = None,
    plugin_root: Path | None = None,
) -> GuardConfig:
    """Merge defaults <- planning_dir <- repo <- $DEEP_GUARD_CONFIG.

    Never raises. A layer that cannot be read or parsed is skipped.
    """
    cfg = GuardConfig()
    for path in resolve_config_paths(cwd, planning_dir, plugin_root):
        layer = _read_layer(path)
        if layer is not None:
            cfg = _merge_layer(cfg, layer, path)
    return cfg


def extract_target(tool_name: str, tool_input: dict) -> tuple[Path | None, str]:
    """Return (file_path, new_content) for a write-shaped tool call."""
    if tool_name == "MultiEdit":
        raw_path = tool_input.get("file_path")
        edits = tool_input.get("edits") or []
        content = "\n".join(
            str(e.get("new_string", "")) for e in edits if isinstance(e, dict)
        )
        return (Path(raw_path) if raw_path else None, content)

    fields = _TARGET_EXTRACTORS.get(tool_name)
    if not fields:
        return (None, "")
    path_key, content_key = fields
    raw_path = tool_input.get(path_key)
    return (
        Path(raw_path) if raw_path else None,
        str(tool_input.get(content_key, "") or ""),
    )


def relativize(path: Path, repo_root: Path) -> str:
    """POSIX repo-relative path, falling back to the absolute path when the
    target sits outside the repo."""
    try:
        return path.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix()


def _glob_matches(rel_path: str, glob: str) -> bool:
    """Glob match with the two conveniences people expect from gitignore-style
    patterns and `fnmatch` does not provide.

    A leading `**/` means "at any depth, including none", so `**/*.md` has to
    match a top-level `README.md`. And a trailing `/**` has to match the
    directory's whole subtree, so `src/generated/**` catches
    `src/generated/a/b.py`.
    """
    if fnmatch.fnmatch(rel_path, glob):
        return True
    if glob.startswith("**/") and fnmatch.fnmatch(rel_path, glob[3:]):
        return True
    prefix = glob.rstrip("*").rstrip("/")
    return bool(prefix) and (
        rel_path == prefix or rel_path.startswith(prefix + "/")
    )


def match_protected(rel_path: str, cfg: GuardConfig) -> ProtectedRule | None:
    """First matching rule, in config order."""
    for rule in cfg.protected:
        if _glob_matches(rel_path, rule.glob):
            return rule
    return None


def is_secret_exempt(rel_path: str, cfg: GuardConfig) -> bool:
    return any(_glob_matches(rel_path, g) for g in cfg.allow_secret_paths)


def scan_secrets(
    text: str, rel_path: str, cfg: GuardConfig
) -> list[tuple[SecretRule, int]]:
    """Return (rule, line_no) hits, capped at cfg.max_scan_bytes."""
    if not text or not cfg.secrets or is_secret_exempt(rel_path, cfg):
        return []
    window = text[: cfg.max_scan_bytes]
    hits: list[tuple[SecretRule, int]] = []
    for rule in cfg.secrets:
        pattern = _compiled(rule.regex)
        if pattern is None:
            continue
        match = pattern.search(window)
        if match:
            hits.append((rule, window.count("\n", 0, match.start()) + 1))
    return hits


def formatter_for(rel_path: str, cfg: GuardConfig) -> FormatRule | None:
    for rule in cfg.formatters:
        if _glob_matches(rel_path, rule.glob):
            return rule
    return None


def _secret_message(rule: SecretRule, rel_path: str, line: int) -> str:
    return (
        f"[deep-guard] BLOCKED by rule {rule.id}: {rule.reason} detected at "
        f"{rel_path}:{line}. Move it to an env var. To allow this path, add it "
        f"to allow_secret_paths in {REPO_CONFIG_RELPATH.as_posix()}, or set "
        f"{GUARD_OFF_ENV}=off for this session."
    )


def _protected_message(rule: ProtectedRule, rel_path: str) -> str:
    verb = "BLOCKED" if rule.action == "deny" else "PAUSED"
    return (
        f"[deep-guard] {verb} by protected path {rule.glob}: {rule.reason} "
        f"({rel_path}). To change this, edit protected_paths in "
        f"{REPO_CONFIG_RELPATH.as_posix()}, or set {GUARD_OFF_ENV}=off for "
        f"this session."
    )


def decide(
    tool_name: str, tool_input: dict, cwd: Path, cfg: GuardConfig
) -> Decision:
    """Secrets outrank protected paths: a credential is never a legitimate
    override, a protected path sometimes is."""
    if not cfg.enabled or guard_disabled_by_env():
        return ALLOW
    if not cfg.protected and not cfg.secrets:
        return ALLOW

    path, content = extract_target(tool_name, tool_input)
    if path is None:
        return ALLOW

    rel_path = relativize(path, cwd)

    for rule, line in scan_secrets(content, rel_path, cfg):
        return Decision("deny", _secret_message(rule, rel_path, line), rule.id)

    protected = match_protected(rel_path, cfg)
    if protected:
        return Decision(
            protected.action, _protected_message(protected, rel_path), protected.glob
        )

    return ALLOW


def render_pre_output(decision: Decision) -> dict | None:
    """None for allow — an exit-0 with no output is the cheapest path."""
    if decision.action == "allow":
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision.action,
            "permissionDecisionReason": decision.reason,
        }
    }

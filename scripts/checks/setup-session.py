#!/usr/bin/env python3
"""Setup planning session using DeepStateTracker.

Replaces setup-planning-session.py. Uses deepstate for state management
instead of position-based task files.

Usage:
    uv run setup-session.py --file "/path/to/spec.md" --plugin-root "/path/to/plugin"
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.config import (
    ConfigError,
    SESSION_CONFIG_FILENAME,
    get_or_create_session_config,
    save_session_config,
)
from lib.deepstate import DeepStateTracker, MetricsCollector
from lib.session_paths import active_marker, write_marker
from lib.beads_sync import BeadsSyncTracker, detect_beads
from lib.workflow import (
    create_plan_workflow,
    create_discovery_workflow,
    create_autonomous_workflow,
    create_goalloop_workflow,
)


VALID_REVIEW_MODES = {"external_llm", "opus_subagent", "sonnet_subagent", "skip"}

# All session state lives here — project working trees stay clean.
DEFAULT_SESSIONS_ROOT = (
    Path.home() / ".claude" / "marketplace" / "deep-plan-enhanced" / "sessions"
)


def sessions_root() -> Path:
    """Where session state lives. Read lazily so `$DEEP_SESSIONS_ROOT` can be
    set after import.

    The override exists so the test suite does not write into the developer's
    real home. Without it the suite accumulates a session directory per test per
    run, and once pytest recycles a tmp path the slug hashes to an existing
    directory, so a "new session" test resumes instead and fails. That flake
    only bites a machine that has run the suite before — never CI, where home is
    fresh — which is the worst combination, because CI stays green while the
    developer sees red.
    """
    return Path(os.environ.get("DEEP_SESSIONS_ROOT") or DEFAULT_SESSIONS_ROOT)


SESSIONS_ROOT = sessions_root()


def detect_discovery_artifacts(planning_dir: Path) -> Path | None:
    """Return discovery dir path if discovery artifacts exist in same or parent dir.

    Checks: interview.md + findings/ directory (minimum viable discovery output).
    """
    for d in [planning_dir, planning_dir.parent]:
        if (d / "interview.md").exists() and (d / "findings").is_dir():
            return d
    return None


def _init_goalloop_state(planning_dir: Path, file_path: Path, opts: dict) -> str | None:
    """Record the goal for a new goalloop session. Returns an error, or None.

    The goal statement comes from `--goal`, from `--goal-file`, or from
    `--file` when that is a markdown document rather than a target directory.
    Acceptance lines are required: a goal with none can never be shown to be
    met, so the loop would run until its ceiling every time.
    """
    from lib.goalloop import GoalLoopError, init

    statement = (opts.get("goal") or "").strip()
    if not statement and file_path.is_file() and file_path.suffix == ".md":
        statement = file_path.read_text().strip()
    acceptance = [line for line in opts.get("acceptance") or [] if line.strip()]

    if not statement:
        return (
            "goalloop needs a goal: pass --goal \"<end state>\", --goal-file, "
            "or point --file at a markdown document describing it"
        )
    if not acceptance:
        return (
            "goalloop needs at least one --acceptance line. Without one there "
            "is nothing for evidence to satisfy and the loop can only ever "
            "stop at its iteration ceiling."
        )

    try:
        init(
            planning_dir,
            statement=statement,
            target=str(file_path),
            acceptance=acceptance,
            max_iterations=int(opts.get("max_iters") or 0),
        )
    except GoalLoopError as exc:
        return str(exc)

    try:
        (planning_dir / "goal.md").write_text(
            f"# Goal\n\n{statement}\n\n## Acceptance\n\n"
            + "\n".join(f"- {line}" for line in acceptance)
            + "\n"
        )
    except OSError:
        pass  # goalloop.json is the source of truth; goal.md is a convenience
    return None


def project_slug(project_path: Path) -> str:
    """Deterministic, human-readable slug for a project path.

    Format: <dirname>-<6-char md5 prefix>
    Example: my-api-a3f9c1
    """
    digest = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()[:6]
    return f"{project_path.name}-{digest}"


def _update_session_index(slug: str, project_path: Path, session_prefix: str, workflow: str, initial_file: str) -> None:
    """Append a session entry to SESSIONS_ROOT/<slug>/index.json (creates if absent)."""
    index_path = sessions_root() / slug / "index.json"
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    data.setdefault("project_path", str(project_path.resolve()))
    data.setdefault("slug", slug)
    sessions = data.setdefault("sessions", [])

    # Avoid duplicates if same prefix already recorded
    if not any(s.get("prefix") == session_prefix for s in sessions):
        sessions.append({
            "prefix": session_prefix,
            "created": datetime.now(timezone.utc).isoformat(),
            "workflow": workflow,
            "initial_file": str(initial_file),
        })

    index_path.write_text(json.dumps(data, indent=2))


def _find_legacy_session(spec_parent: Path, session_id: str) -> Path | None:
    """Check for a legacy session written into the old in-project location.

    Checks by prefix match first, then scans all session configs for session_id.
    Returns the path if found, None otherwise.
    """
    sessions_dir = spec_parent / "sessions"
    if not sessions_dir.exists():
        return None

    prefix = session_id[:8]
    candidate = sessions_dir / prefix
    if candidate.exists() and (candidate / SESSION_CONFIG_FILENAME).exists():
        return candidate

    for d in sessions_dir.iterdir():
        if not d.is_dir():
            continue
        config_path = d / SESSION_CONFIG_FILENAME
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                if config.get("session_id") == session_id:
                    return d
            except (json.JSONDecodeError, OSError):
                continue
    return None


def resolve_planning_dir(project_path: Path, session_id: str | None, spec_parent: Path | None = None) -> Path:
    """Resolve the planning directory for a session.

    New sessions are created under SESSIONS_ROOT/<slug>/<prefix>/ so the
    project working tree stays clean.

    Legacy sessions that already exist inside the project directory are
    returned as-is so existing work is never lost.
    """
    # --- Legacy detection: session already exists inside the project tree ---
    # Check spec_parent (the old in-project location) for legacy markers.
    _spec_parent = spec_parent or project_path
    legacy_file_markers = [
        "claude-research.md", "claude-plan.md", "claude-spec.md",
        "claude-interview.md", "claude-plan-tdd.md",
        "claude-integration-notes.md", SESSION_CONFIG_FILENAME,
    ]
    legacy_dir_markers = ["reviews", "sections"]
    has_legacy_in_place = (
        any((_spec_parent / f).exists() for f in legacy_file_markers)
        or any((_spec_parent / d).is_dir() for d in legacy_dir_markers)
    )
    if has_legacy_in_place:
        return _spec_parent

    if session_id:
        # Check for existing legacy session by ID inside project tree
        legacy = _find_legacy_session(_spec_parent, session_id)
        if legacy:
            return legacy

    # --- New session: write to SESSIONS_ROOT ---
    slug = project_slug(project_path)
    prefix = session_id[:8] if session_id else "default"

    # Check if this session already exists in SESSIONS_ROOT (resume case)
    candidate = sessions_root() / slug / prefix
    if candidate.exists() and (candidate / SESSION_CONFIG_FILENAME).exists():
        return candidate

    # New session — create directory
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def is_legacy_config(config: dict) -> bool:
    """Check if config was created by the old task-based system."""
    return "task_list_id" in config and "deepstate_epic_id" not in config


def determine_mode(tracker: DeepStateTracker) -> tuple[str, dict]:
    """Determine session mode from deepstate.

    Returns (mode, info) where mode is 'new', 'resume', or 'complete'.
    """
    state_file = tracker.state_dir / "state.json"
    if not state_file.exists():
        return "new", {}

    try:
        state = tracker._load()
    except (json.JSONDecodeError, OSError):
        return "new", {}

    if not state.get("epic"):
        return "new", {}

    ready = tracker.ready()
    all_issues = tracker.list_issues()
    closed = [i for i in all_issues if i["status"] == "closed"]
    open_issues = [i for i in all_issues if i["status"] == "open"]

    if not all_issues:
        return "new", {}

    if ready:
        return "resume", {
            "ready_issues": [{"id": i["id"], "title": i["title"]} for i in ready],
            "closed_count": len(closed),
            "open_count": len(open_issues),
        }

    if not open_issues:
        return "complete", {
            "closed_count": len(closed),
        }

    # Open issues exist but none are ready — blocked state
    return "resume", {
        "ready_issues": [],
        "closed_count": len(closed),
        "open_count": len(open_issues),
    }


def check_partial_setup(tracker: DeepStateTracker, expected_count: int | None) -> bool:
    """Return True if deepstate exists but issue count is inconsistent."""
    state_file = tracker.state_dir / "state.json"
    if not state_file.exists():
        return False
    if expected_count is None:
        return False  # Dynamic workflow — can't validate count
    try:
        state = tracker._load()
        if not state.get("epic"):
            return True
        actual_count = len(state.get("issues", {}))
        return actual_count > 0 and actual_count != expected_count
    except (json.JSONDecodeError, OSError):
        return True


def setup_session(
    file_path: Path,
    plugin_root: Path,
    review_mode: str,
    session_id: str | None,
    workflow: str,
    force: bool,
    depth: str = "standard",
    express_source: str | None = None,
    express_kind: str | None = None,
    intent_source: str | None = None,
    goalloop_opts: dict | None = None,
) -> dict:
    """Core setup logic. Returns JSON-serializable result dict.

    `goalloop_opts` carries the goal statement, its acceptance lines and the
    iteration ceiling. Bundled rather than spread across three more keyword
    arguments, which this signature does not have room for.
    """
    is_audit = workflow == "audit"
    is_auto = workflow == "auto"
    is_goalloop = workflow == "goalloop"

    # Input validation
    if file_path.is_dir():
        if not is_audit and not is_auto and not is_goalloop:
            return {
                "success": False,
                "error": f"Expected a spec file (.md), got a directory: {file_path}. "
                         f"Use /deep-plan @path/to/spec.md or /deep-discovery for directory-based workflows.",
                "mode": "error",
            }
    elif not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}", "mode": "error"}
    elif file_path.stat().st_size == 0:
        return {"success": False, "error": f"Spec file is empty: {file_path}", "mode": "error"}

    # Derive the project root for slug computation.
    # audit: file_path IS the project directory
    # plan: file_path is a spec .md, project root is its parent
    # auto: file_path is the phases dir, project root is its parent
    if file_path.is_dir():
        project_path = file_path
    else:
        project_path = file_path.parent

    # Resolve planning directory
    if is_auto and file_path.is_dir():
        legacy_dir = file_path.parent / "auto"
        if legacy_dir.exists() and (legacy_dir / ".deepstate" / "state.json").exists():
            planning_dir = legacy_dir
        else:
            planning_dir = resolve_planning_dir(project_path, session_id)
    elif file_path.is_dir():
        # audit workflow: check legacy audit/ subdir first
        legacy_audit = file_path / "audit"
        if legacy_audit.exists() and any(
            (legacy_audit / f).exists()
            for f in ["claude-research.md", SESSION_CONFIG_FILENAME, ".deepstate"]
        ):
            spec_parent = legacy_audit
            planning_dir = resolve_planning_dir(project_path, session_id, spec_parent=spec_parent)
        else:
            planning_dir = resolve_planning_dir(project_path, session_id)
    else:
        planning_dir = resolve_planning_dir(project_path, session_id, spec_parent=file_path.parent)

    # Create or load session config
    try:
        session_config, config_created = get_or_create_session_config(
            planning_dir=planning_dir,
            plugin_root=str(plugin_root),
            initial_file=str(file_path),
        )
    except ConfigError as e:
        if "legacy" in str(e).lower():
            return {
                "success": False,
                "mode": "legacy_config",
                "error": "This session was created with the old task-based system. deepstate requires a fresh session.",
                "migration": "Start a new session with /deep-plan @spec.md. Old planning files are preserved.",
            }
        return {"success": False, "error": f"Session config error: {e}", "mode": "error"}

    # Legacy config detection
    if not config_created and is_legacy_config(session_config):
        return {
            "success": False,
            "mode": "legacy_config",
            "error": "This session was created with the old task-based system. deepstate requires a fresh session.",
            "migration": "Start a new session with /deep-plan @spec.md. Old planning files are preserved.",
        }

    # Handle review_mode
    if config_created:
        session_config["review_mode"] = review_mode
        if session_id:
            session_config["session_id"] = session_id
        save_session_config(planning_dir, session_config)
    else:
        review_mode = session_config.get("review_mode", review_mode)

    # Initialize tracker
    from lib.tasks import TASK_IDS, AUDIT_TASK_IDS, GOALLOOP_TASK_IDS
    if is_auto:
        expected_count = None  # Dynamic — depends on number of phases
    elif is_audit:
        expected_count = len(AUDIT_TASK_IDS)
    elif is_goalloop:
        expected_count = len(GOALLOOP_TASK_IDS)
    else:
        expected_count = len(TASK_IDS)

    state_dir = planning_dir / ".deepstate"
    base_tracker = DeepStateTracker(state_dir=state_dir)

    # Check for partial setup BEFORE determine_mode (corrupted state can crash ready())
    if check_partial_setup(base_tracker, expected_count):
        if not force:
            return {
                "success": False,
                "mode": "partial_setup",
                "error": "Inconsistent deepstate (partial setup detected). Use --force to reinitialize.",
                "planning_dir": str(planning_dir),
            }
        # Force: tear down and recreate
        if state_dir.exists():
            shutil.rmtree(state_dir)
        base_tracker = DeepStateTracker(state_dir=state_dir)

    # Now safe to determine mode (state is consistent or fresh)
    mode, mode_info = determine_mode(base_tracker)

    if mode == "complete":
        return {
            "success": True,
            "mode": "complete",
            "planning_dir": str(planning_dir),
            "initial_file": str(file_path),
            "plugin_root": str(plugin_root),
            "workflow": workflow,
            "review_mode": review_mode,
            "message": f"{'Audit' if is_audit else 'Planning'} workflow complete",
            **mode_info,
        }

    if mode == "resume":
        return {
            "success": True,
            "mode": "resume",
            "planning_dir": str(planning_dir),
            "initial_file": str(file_path),
            "plugin_root": str(plugin_root),
            "workflow": workflow,
            "review_mode": review_mode,
            "message": f"Resuming session in: {planning_dir}",
            **mode_info,
        }

    # New session — create workflow. Beads is required.
    if not detect_beads():
        installer = Path(plugin_root) / "scripts" / "checks" / "install-beads.sh"
        raise SystemExit(
            "bd (beads) required but not on PATH. "
            f"Install: bash {installer}  (or: brew install beads)"
        )
    tracker = BeadsSyncTracker(
        tracker=base_tracker,
        beads_available=True,
        beads_cwd=planning_dir,
    )

    context = {
        "plugin_root": str(plugin_root),
        "planning_dir": str(planning_dir),
        "initial_file": str(file_path),
        "review_mode": review_mode,
    }

    if is_audit:
        epic_title = create_discovery_workflow(
            tracker, **context, depth=depth,
        )
    elif is_auto:
        epic_title = create_autonomous_workflow(
            tracker,
            phases_dir=str(file_path),
            plugin_root=str(plugin_root),
            discovery_findings=str(file_path.parent),
        )
    elif is_goalloop:
        discovery_dir = detect_discovery_artifacts(planning_dir)
        epic_title = create_goalloop_workflow(
            tracker, **context,
            discovery_findings=str(discovery_dir) if discovery_dir else None,
        )
        goalloop_error = _init_goalloop_state(
            planning_dir, file_path, goalloop_opts or {}
        )
        if goalloop_error:
            return {"success": False, "error": goalloop_error, "mode": "error"}
    else:
        discovery_dir = detect_discovery_artifacts(planning_dir)
        epic_title = create_plan_workflow(
            tracker,
            **context,
            discovery_findings=str(discovery_dir) if discovery_dir else None,
            express_source=express_source,
            express_kind=express_kind,
            intent_source=intent_source,
        )

    # Store epic reference in config
    session_config["deepstate_epic_id"] = epic_title
    save_session_config(planning_dir, session_config)

    # Open the metrics file so the session has somewhere to record into.
    # Best-effort: metrics are diagnostics, never a reason to fail setup.
    try:
        metrics = MetricsCollector(state_dir=state_dir)
        metrics.record("workflow", workflow)
    except Exception:
        pass

    # Write active session marker
    marker_file = active_marker()
    try:
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.write_text(str(planning_dir))
    except OSError:
        pass

    # Per-session marker for the implement hooks. Nothing wrote this before, so
    # their per-session lookup could never hit and they fell through to stale
    # markers or to None — which is why impl-stop's summary gate went quiet.
    if session_id:
        write_marker(session_id, planning_dir)

    # Record session in the project index (best-effort, non-fatal)
    try:
        slug = project_slug(project_path)
        prefix = session_id[:8] if session_id else "default"
        _update_session_index(
            slug=slug,
            project_path=project_path,
            session_prefix=prefix,
            workflow=workflow,
            initial_file=str(file_path),
        )
    except Exception:
        pass  # Index is a convenience feature; never block the workflow

    return {
        "success": True,
        "mode": "new",
        "planning_dir": str(planning_dir),
        "initial_file": str(file_path),
        "plugin_root": str(plugin_root),
        "workflow": workflow,
        "review_mode": review_mode,
        "epic_id": epic_title,
        "beads_available": True,
        "sessions_root": str(sessions_root()),
        "message": f"Starting new {workflow} session in: {planning_dir}",
    }


def main():
    parser = argparse.ArgumentParser(description="Setup planning session")
    parser.add_argument("--file", required=True, help="Path to spec file")
    parser.add_argument("--plugin-root", required=True, help="Path to plugin root directory")
    parser.add_argument(
        "--review-mode", default="external_llm",
        help="Review mode: external_llm, opus_subagent, sonnet_subagent, or skip",
    )
    parser.add_argument("--force", action="store_true", help="Force overwrite of existing state")
    parser.add_argument("--session-id", help="Session ID from hook's additionalContext")
    parser.add_argument(
        "--workflow", choices=["plan", "audit", "auto", "goalloop"], default="plan",
        help="Workflow type: plan (default), audit, auto, or goalloop",
    )
    parser.add_argument(
        "--goal",
        help="Goalloop workflow: the end state, in the user's words.",
    )
    parser.add_argument(
        "--goal-file",
        help="Goalloop workflow: read the goal statement from this file instead.",
    )
    parser.add_argument(
        "--acceptance", action="append",
        help="Goalloop workflow: one acceptance line; repeat. At least one is "
             "required — it is what evidence gets checked against.",
    )
    parser.add_argument(
        "--max-iters", type=int, default=0,
        help="Goalloop workflow: iteration ceiling. 0 (default) means only the "
             "goal, a blocker, or the user stops the loop.",
    )
    parser.add_argument(
        "--depth", choices=["quick", "standard", "deep"], default="standard",
        help="Discovery depth (audit workflow only): quick (scan + topics + interview), "
             "standard (default, all steps), deep (all steps + cross-verify pass)",
    )
    parser.add_argument(
        "--from-prd",
        help="Express path (plan workflow): path to a PRD file. Skips research + interview.",
    )
    parser.add_argument(
        "--from-adr",
        help="Express path (plan workflow): path to an ADR file or directory. "
             "Skips research + interview.",
    )
    parser.add_argument(
        "--from-intent",
        help="Plan workflow: path to an accepted intent.md. NOT an express path — "
             "research and interview still run, because an intent deliberately "
             "carries no engineering content. Recorded so the spec can be traced "
             "back to it.",
    )
    args = parser.parse_args()

    if args.from_prd and args.from_adr:
        print(json.dumps({
            "success": False,
            "mode": "error",
            "error": "Cannot use --from-prd and --from-adr together. Pick one.",
        }))
        sys.exit(2)

    if args.from_intent and args.workflow != "plan":
        print(json.dumps({
            "success": False,
            "mode": "error",
            "error": f"--from-intent only valid with --workflow plan, got {args.workflow}",
        }))
        sys.exit(2)

    goalloop_flags = {
        "--goal": args.goal,
        "--goal-file": args.goal_file,
        "--acceptance": args.acceptance,
        "--max-iters": args.max_iters or None,
    }
    misplaced = sorted(f for f, v in goalloop_flags.items() if v)
    if args.workflow != "goalloop" and misplaced:
        print(json.dumps({
            "success": False,
            "mode": "error",
            "error": f"{', '.join(misplaced)} only valid with --workflow goalloop, "
                     f"got {args.workflow}",
        }))
        sys.exit(2)

    goal_statement = args.goal
    if args.goal_file:
        try:
            goal_statement = Path(args.goal_file).read_text().strip()
        except OSError as exc:
            print(json.dumps({
                "success": False, "mode": "error",
                "error": f"--goal-file unreadable: {exc}",
            }))
            sys.exit(2)

    express_source = args.from_prd or args.from_adr
    express_kind = "prd" if args.from_prd else ("adr" if args.from_adr else None)
    if express_source and args.workflow != "plan":
        print(json.dumps({
            "success": False,
            "mode": "error",
            "error": f"--from-prd / --from-adr only valid with --workflow plan, got {args.workflow}",
        }))
        sys.exit(2)

    # Normalize review_mode
    if args.review_mode not in VALID_REVIEW_MODES:
        args.review_mode = "opus_subagent"

    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    try:
        result = setup_session(
            file_path=file_path,
            plugin_root=Path(args.plugin_root),
            review_mode=args.review_mode,
            session_id=args.session_id,
            workflow=args.workflow,
            force=args.force,
            depth=args.depth,
            express_source=express_source,
            express_kind=express_kind,
            intent_source=args.from_intent,
            goalloop_opts={
                "goal": goal_statement,
                "acceptance": args.acceptance,
                "max_iters": args.max_iters,
            },
        )
    except Exception as e:
        result = {"success": False, "error": str(e), "mode": "error"}

    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())

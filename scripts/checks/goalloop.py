#!/usr/bin/env python3
"""Drive the goal-driven incremental SDLC loop.

`/deep auto` chains phases someone already enumerated. `goalloop` starts from
the end state instead and carves the phases as it goes: each iteration takes
the next increment off the ledger, writes it as an intent, plans it,
implements it, records what it learned, and goes again.

This CLI owns the parts a model should not hold in its head across a run
lasting hours — what the goal was, what has actually been delivered, which
acceptance lines have evidence, and whether any of that adds up to done.

Subcommands:
  init      --planning-dir D --goal TEXT --acceptance LINE [...]
  add       --planning-dir D --title T --acceptance A [--after ID]
  triage    --planning-dir D --kind blocker|deferrable --title T --acceptance A
  split     --planning-dir D --increment ID --slice "title :: acceptance" [...]
  begin     --planning-dir D [--dir ITERATION_DIR]
  end       --planning-dir D --outcome delivered|blocked|dropped [--detail X]
  evidence  --planning-dir D --acceptance-id A1 --source S [--detail X]
  tick      --planning-dir D          the done test
  status    --planning-dir D          full state
  ledger    --planning-dir D          the readable ledger
  handoff   --planning-dir D          end-of-run report, markdown

Exit codes:
  0 — the goal is met; stop
  3 — not met, work remains; run another iteration
  1 — stopped and a human is needed (blocked, or the iteration ceiling)
  2 — usage or I/O error

`tick` is the only one that returns 3. Everything else returns 0 on success,
so a driver can distinguish "the loop says continue" from "that command
worked" without parsing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import goalloop as gl

CONTINUE = 3


def _emit(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, indent=2))
    return code


def cmd_init(args: argparse.Namespace) -> int:
    statement = args.goal
    if args.goal_file:
        statement = Path(args.goal_file).read_text().strip()
    loop = gl.init(
        args.planning_dir,
        statement=statement or "",
        target=args.target or "",
        acceptance=list(args.acceptance or ()),
        max_iterations=args.max_iters,
    )
    return _emit({
        "success": True,
        "goal": loop.statement,
        "acceptance": [a.id for a in loop.acceptance],
        "max_iterations": loop.max_iterations,
        "state_file": str(gl.state_path(args.planning_dir)),
        "ledger_file": str(gl.ledger_path(args.planning_dir)),
    })


def cmd_add(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    increment = gl.add_increment(
        loop, title=args.title, acceptance=args.acceptance, after=args.after
    )
    gl.save(args.planning_dir, loop)
    return _emit({"success": True, "increment": increment.to_dict()})


def cmd_triage(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    increment = gl.triage(
        loop,
        kind=args.kind,
        title=args.title,
        acceptance=args.acceptance,
        because=args.because or "",
    )
    gl.save(args.planning_dir, loop)
    return _emit({
        "success": True,
        "kind": args.kind,
        "increment": increment.to_dict(),
        "action": loop.events[-1].action,
        "ledger": [i.id for i in loop.ledger if i.is_open],
    })


def _parse_slices(raw) -> list[tuple[str, str]]:
    slices: list[tuple[str, str]] = []
    for entry in raw or ():
        title, _, acceptance = entry.partition("::")
        if not acceptance.strip():
            raise gl.GoalLoopError(
                f'slice needs "title :: acceptance", got: {entry}'
            )
        slices.append((title.strip(), acceptance.strip()))
    return slices


def cmd_split(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    children = gl.split(loop, args.increment, _parse_slices(args.slice))
    gl.save(args.planning_dir, loop)
    return _emit({
        "success": True,
        "parent": args.increment,
        "children": [c.to_dict() for c in children],
    })


def cmd_begin(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    record = gl.begin_iteration(loop, directory=args.dir or "")
    gl.save(args.planning_dir, loop)
    increment = gl.find(loop, record.increment)
    return _emit({
        "success": True,
        "iteration": record.n,
        "increment": increment.to_dict(),
        "directory": record.directory,
        "goal": loop.statement,
    })


def cmd_end(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    record = gl.end_iteration(loop, outcome=args.outcome, detail=args.detail or "")
    gl.save(args.planning_dir, loop)
    return _emit({"success": True, "iteration": record.to_dict()})


def cmd_evidence(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    clause = gl.add_evidence(
        loop,
        acceptance_id=args.acceptance_id,
        source=args.source,
        detail=args.detail or "",
    )
    gl.save(args.planning_dir, loop)
    return _emit({"success": True, "acceptance": clause.to_dict()})


def cmd_tick(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    status = gl.evaluate(loop, args.planning_dir)
    payload = {"success": True, **status.to_dict()}

    if status.met:
        payload["guidance"] = (
            "Goal met. Write the summary (`handoff`) and stop. Do not start "
            "another iteration."
        )
        return _emit(payload, 0)
    if status.stop_reason == gl.MEASUREMENT_NEEDED:
        payload["guidance"] = (
            "Everything on the ledger is delivered and every gate is green. "
            "What is missing is a measurement of "
            f"{', '.join(status.unevidenced)}. Take it and record it with "
            "`evidence --source <artifact>`, or add an increment that takes "
            "it (`triage --kind blocker`). If it cannot be measured, stop and "
            "say so — do not record an argument as evidence."
        )
        return _emit(payload, CONTINUE)
    if status.should_continue:
        payload["guidance"] = (
            f"Run iteration {status.iterations_done + 1} on "
            f"{status.next_increment}. Unmet: "
            + "; ".join(f"{k} ({v})" for k, v in status.unmet.items())
        )
        return _emit(payload, CONTINUE)
    payload["guidance"] = (
        "Stop and report. The loop cannot advance on its own — see `unmet` "
        "and run `handoff` for the report."
    )
    return _emit(payload, 1)


def cmd_status(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    status = gl.evaluate(loop, args.planning_dir)
    return _emit({"success": True, **loop.to_dict(), "status": status.to_dict()})


def cmd_ledger(args: argparse.Namespace) -> int:
    print(gl.render_ledger(gl.require(args.planning_dir)))
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    loop = gl.require(args.planning_dir)
    print(gl.summary(loop, gl.evaluate(loop, args.planning_dir)))
    return 0


def _add_subcommands(subparsers) -> None:
    init = subparsers.add_parser("init", help="set the goal")
    init.add_argument("--goal", help="the end state, in the user's words")
    init.add_argument("--goal-file", help="read the goal statement from a file")
    init.add_argument(
        "--acceptance", action="append",
        help="one acceptance line; repeat. At least one is required.",
    )
    init.add_argument("--target", help="repository or directory the goal applies to")
    init.add_argument(
        "--max-iters", type=int, default=0,
        help="iteration ceiling; 0 (default) means only the goal or a blocker stops it",
    )
    init.set_defaults(func=cmd_init)

    add = subparsers.add_parser("add", help="append or insert an increment")
    add.add_argument("--title", required=True)
    add.add_argument("--acceptance", required=True, help="the increment's own done-test")
    add.add_argument("--after", help="insert behind this increment id")
    add.set_defaults(func=cmd_add)

    triage = subparsers.add_parser("triage", help="file newly-discovered work")
    triage.add_argument("--kind", required=True, choices=[gl.BLOCKER, gl.DEFERRABLE])
    triage.add_argument("--title", required=True)
    triage.add_argument("--acceptance", required=True)
    triage.add_argument("--because", help="why it is a blocker, or why it can wait")
    triage.set_defaults(func=cmd_triage)

    split = subparsers.add_parser("split", help="replace an increment with smaller ones")
    split.add_argument("--increment", required=True)
    split.add_argument(
        "--slice", action="append", required=True,
        help='"title :: acceptance"; repeat, at least twice',
    )
    split.set_defaults(func=cmd_split)

    begin = subparsers.add_parser("begin", help="start or resume an iteration")
    begin.add_argument("--dir", help="planning directory for this iteration")
    begin.set_defaults(func=cmd_begin)

    end = subparsers.add_parser("end", help="close the open iteration")
    end.add_argument(
        "--outcome", required=True, choices=[gl.DELIVERED, gl.BLOCKED, gl.DROPPED]
    )
    end.add_argument("--detail")
    end.set_defaults(func=cmd_end)

    evidence = subparsers.add_parser("evidence", help="record evidence for an acceptance line")
    evidence.add_argument("--acceptance-id", required=True)
    evidence.add_argument("--source", required=True, help="the artifact: test, report path, command")
    evidence.add_argument("--detail")
    evidence.set_defaults(func=cmd_evidence)

    for name, func, help_text in (
        ("tick", cmd_tick, "the done test"),
        ("status", cmd_status, "full state as JSON"),
        ("ledger", cmd_ledger, "the readable ledger"),
        ("handoff", cmd_handoff, "end-of-run report"),
    ):
        subparsers.add_parser(name, help=help_text).set_defaults(func=func)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--planning-dir", required=True, help="session directory holding .deepstate/"
    )
    _add_subcommands(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args()

    try:
        return args.func(args)
    except gl.GoalLoopError as exc:
        return _emit({"success": False, "error": str(exc)}, 2)
    except OSError as exc:
        return _emit({"success": False, "error": f"I/O error: {exc}"}, 2)


if __name__ == "__main__":
    sys.exit(main())

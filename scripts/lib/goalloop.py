"""Goal, ledger, and done-test for the incremental SDLC loop.

`/deep auto` chains phases that discovery already enumerated. It cannot start
from "here is the end state I want" — someone has to have written the phases
first. `goalloop` starts there instead: a durable goal, and a loop that carves
the next shippable increment out of the remaining distance to it, writes that
increment as an intent, plans it, implements it, then updates the ledger with
what the implementation taught it and goes again.

The three parts, and why each is a file rather than a paragraph:

**The goal** is the end state, in the user's words, with its acceptance lines
extracted. It does not change across iterations. Everything else is allowed to.

**The ledger** is the remaining work as increments. It is deliberately *fixed
by default* — a loop free to re-plan every iteration re-plans forever, and the
run has nothing to show for itself. New information is triaged instead:

| Kind | Test | What happens |
|---|---|---|
| blocker | the current increment cannot land until this does | `preempt` — the new increment jumps the queue, the current one goes back to pending |
| deferrable | it can wait its turn | `splice` — inserted at the right position, current work continues |

Every triage decision is recorded with its reason, so a run that quietly
reshuffled the whole ledger is visible as exactly that.

**The done test** is three clauses that must all hold, because each catches a
different way a loop lies about being finished:

1. `ledger_clear` — nothing pending, active, or blocked. Catches the run that
   declares victory with work still listed.
2. `gates_green` — every implemented section recorded `passed`, and the
   needs-human queue is empty. Catches the run that shipped code that does not
   compile. Reuses `verification.py` and `handoff.py`, and inherits their rule
   that a section which never recorded a result counts as `human_needed`.
3. `acceptance_evidenced` — every acceptance line points at a recorded
   artifact from a named iteration. Catches the run that built all the right
   parts and never checked the thing the user actually asked for.

Clause 3 is the one that needs stating plainly: an acceptance line is met by
*evidence*, never by an argument that it is met. "The board refreshes in under
two seconds" is satisfied by a recorded measurement, not by a paragraph
explaining why it should.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lib import handoff
from lib.verification import PASSED, phase_status

GOALLOOP_FILENAME = "goalloop.json"
LEDGER_FILENAME = "goal-ledger.md"

# Increment states. `blocked` is separate from `dropped` on purpose: dropped is
# a decision, blocked is a debt.
PENDING = "pending"
ACTIVE = "active"
DELIVERED = "delivered"
BLOCKED = "blocked"
DROPPED = "dropped"

STATES = (PENDING, ACTIVE, DELIVERED, BLOCKED, DROPPED)
OPEN_STATES = (PENDING, ACTIVE, BLOCKED)

# How an increment got onto the ledger.
INITIAL = "initial"
SPLICED = "spliced"
PREEMPT = "preempt"
SPLIT = "split"

ORIGINS = (INITIAL, SPLICED, PREEMPT, SPLIT)

# Triage verdicts for new information.
BLOCKER = "blocker"
DEFERRABLE = "deferrable"

# Iteration outcomes. The first three mirror increment states; `preempted`
# exists only here, because an abandoned pass says nothing about the increment
# it was working on — that one goes back to pending, unharmed.
PREEMPTED = "preempted"
OUTCOMES = (DELIVERED, BLOCKED, DROPPED, PREEMPTED)

# Why a loop stopped, or did not.
GOAL_MET = "goal_met"
ITERATIONS_EXHAUSTED = "iterations_exhausted"
BLOCKED_ON_HUMAN = "blocked_on_human"
RUNNING = "running"
# Everything built and passing, and an acceptance line nobody measured. Not a
# halt: measuring is work the loop can do, and stopping here hands back a run
# that was one command from finished.
MEASUREMENT_NEEDED = "measurement_needed"

# Verdicts under which the loop keeps working.
CONTINUING = (RUNNING, MEASUREMENT_NEEDED)


class GoalLoopError(Exception):
    """Raised for an operation the ledger cannot represent."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    """One recorded observation that bears on an acceptance line."""

    iteration: int
    source: str
    detail: str = ""
    recorded_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class Acceptance:
    """One clause of the goal, and what has been observed about it."""

    id: str
    text: str
    evidence: tuple[Evidence, ...] = ()

    @property
    def evidenced(self) -> bool:
        return bool(self.evidence)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class Increment:
    """One shippable slice of the distance to the goal.

    `acceptance` is the increment's own done-test, in one line. An increment
    without one is a wish, and the loop will deliver it by deciding it is
    delivered.
    """

    id: str
    title: str
    acceptance: str = ""
    state: str = PENDING
    origin: str = INITIAL
    iteration: int | None = None
    parent: str | None = None
    note: str = ""
    created: str = ""
    updated: str = ""

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_STATES

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class IterationRecord:
    """One pass of the loop."""

    n: int
    increment: str
    directory: str = ""
    started: str = ""
    ended: str = ""
    outcome: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class TriageEvent:
    """New information, and what the loop did about it."""

    at: str
    iteration: int
    kind: str
    summary: str
    action: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True, kw_only=True)
class GoalLoop:
    """The whole run, as one serialisable record."""

    statement: str
    target: str = ""
    created: str = ""
    max_iterations: int = 0  # 0 means unbounded — the goal or a blocker stops it
    acceptance: list[Acceptance] = field(default_factory=list)
    ledger: list[Increment] = field(default_factory=list)
    iterations: list[IterationRecord] = field(default_factory=list)
    events: list[TriageEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal": {
                "statement": self.statement,
                "target": self.target,
                "created": self.created,
                "max_iterations": self.max_iterations,
                "acceptance": [a.to_dict() for a in self.acceptance],
            },
            "ledger": [i.to_dict() for i in self.ledger],
            "iterations": [r.to_dict() for r in self.iterations],
            "events": [e.to_dict() for e in self.events],
        }


def state_path(planning_dir) -> Path:
    return Path(planning_dir) / ".deepstate" / GOALLOOP_FILENAME


def ledger_path(planning_dir) -> Path:
    return Path(planning_dir) / LEDGER_FILENAME


def _parse_acceptance(raw) -> list[Acceptance]:
    result: list[Acceptance] = []
    for index, entry in enumerate(raw or (), start=1):
        if isinstance(entry, str):
            result.append(Acceptance(id=f"A{index}", text=entry))
            continue
        if not isinstance(entry, dict) or not entry.get("text"):
            continue
        result.append(
            Acceptance(
                id=str(entry.get("id") or f"A{index}"),
                text=str(entry["text"]),
                evidence=tuple(
                    Evidence(
                        iteration=int(e.get("iteration", 0) or 0),
                        source=str(e.get("source", "")),
                        detail=str(e.get("detail", "")),
                        recorded_at=str(e.get("recorded_at", "")),
                    )
                    for e in entry.get("evidence") or ()
                    if isinstance(e, dict)
                ),
            )
        )
    return result


def _parse_ledger(raw) -> list[Increment]:
    result: list[Increment] = []
    for entry in raw or ():
        if not isinstance(entry, dict) or not entry.get("id"):
            continue
        state = str(entry.get("state", PENDING))
        origin = str(entry.get("origin", INITIAL))
        iteration = entry.get("iteration")
        result.append(
            Increment(
                id=str(entry["id"]),
                title=str(entry.get("title", "")),
                acceptance=str(entry.get("acceptance", "")),
                state=state if state in STATES else PENDING,
                origin=origin if origin in ORIGINS else INITIAL,
                iteration=int(iteration) if iteration else None,
                parent=entry.get("parent") or None,
                note=str(entry.get("note", "")),
                created=str(entry.get("created", "")),
                updated=str(entry.get("updated", "")),
            )
        )
    return result


def load(planning_dir) -> GoalLoop | None:
    """The run's record, or None if no goal has been set.

    Never raises on a malformed file. A run whose state file is corrupt has no
    goal, which halts the loop — the correct outcome, and better than a
    traceback out of a hook.
    """
    try:
        data = json.loads(state_path(planning_dir).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    goal = data.get("goal") or {}
    if not goal.get("statement"):
        return None
    return GoalLoop(
        statement=str(goal["statement"]),
        target=str(goal.get("target", "")),
        created=str(goal.get("created", "")),
        max_iterations=max(0, int(goal.get("max_iterations", 0) or 0)),
        acceptance=_parse_acceptance(goal.get("acceptance")),
        ledger=_parse_ledger(data.get("ledger")),
        iterations=[
            IterationRecord(
                n=int(r.get("n", 0) or 0),
                increment=str(r.get("increment", "")),
                directory=str(r.get("directory", "")),
                started=str(r.get("started", "")),
                ended=str(r.get("ended", "")),
                outcome=str(r.get("outcome", "")),
                detail=str(r.get("detail", "")),
            )
            for r in data.get("iterations") or ()
            if isinstance(r, dict)
        ],
        events=[
            TriageEvent(
                at=str(e.get("at", "")),
                iteration=int(e.get("iteration", 0) or 0),
                kind=str(e.get("kind", "")),
                summary=str(e.get("summary", "")),
                action=str(e.get("action", "")),
                detail=str(e.get("detail", "")),
            )
            for e in data.get("events") or ()
            if isinstance(e, dict)
        ],
    )


def save(planning_dir, loop: GoalLoop) -> None:
    """Write state, then re-render the human-readable ledger.

    Atomic: temp file plus `os.replace`, the pattern `DeepStateTracker._save`
    uses. A loop interrupted mid-write must not come back to a truncated
    ledger and conclude there is nothing left to do.
    """
    path = state_path(planning_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(loop.to_dict(), indent=2))
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise GoalLoopError(f"could not write goalloop state: {exc}") from exc
    try:
        ledger_path(planning_dir).write_text(render_ledger(loop))
    except OSError:
        # The markdown is a convenience view of state.json, never the source
        # of truth. Losing it must not fail the write that mattered.
        pass


def require(planning_dir) -> GoalLoop:
    loop = load(planning_dir)
    if loop is None:
        raise GoalLoopError(
            f"no goal set in {planning_dir} — run `goalloop.py init` first"
        )
    return loop


def next_increment_id(loop: GoalLoop) -> str:
    """`I01`, `I02`, … Ids are never reused, including by a dropped
    increment, so an iteration log always names the thing it actually ran."""
    used = {i.id for i in loop.ledger}
    n = 1
    while f"I{n:02d}" in used:
        n += 1
    return f"I{n:02d}"


def find(loop: GoalLoop, increment_id: str) -> Increment:
    for increment in loop.ledger:
        if increment.id == increment_id:
            return increment
    raise GoalLoopError(f"no such increment: {increment_id}")


def _replace(loop: GoalLoop, increment: Increment, **changes) -> Increment:
    updated = Increment(**{**increment.to_dict(), **changes, "updated": utc_now()})
    loop.ledger[loop.ledger.index(increment)] = updated
    return updated


def init(
    planning_dir,
    *,
    statement: str,
    target: str = "",
    acceptance=(),
    max_iterations: int = 0,
) -> GoalLoop:
    """Set the goal. Refuses to overwrite one that is already running.

    Replacing a live goal mid-run would orphan the ledger it produced, so it
    is a deliberate teardown, not a flag on `init`.
    """
    if not statement.strip():
        raise GoalLoopError("a goal needs a statement of the end state")
    if load(planning_dir) is not None:
        raise GoalLoopError(
            f"a goal is already set in {planning_dir}; delete "
            f"{state_path(planning_dir)} to start over"
        )
    if not acceptance:
        raise GoalLoopError(
            "a goal needs at least one acceptance line — without one there is "
            "nothing for evidence to satisfy and the loop cannot terminate"
        )
    loop = GoalLoop(
        statement=statement.strip(),
        target=str(target),
        created=utc_now(),
        max_iterations=max(0, int(max_iterations)),
        acceptance=_parse_acceptance(list(acceptance)),
    )
    save(planning_dir, loop)
    return loop


def add_increment(
    loop: GoalLoop,
    *,
    title: str,
    acceptance: str = "",
    origin: str = INITIAL,
    after: str | None = None,
    parent: str | None = None,
    state: str = PENDING,
    note: str = "",
) -> Increment:
    """Append or insert one increment.

    `after=None` appends; `after="I02"` inserts directly behind that
    increment; `after=""` puts it at the front of the queue, which is what a
    preemption needs.
    """
    if not title.strip():
        raise GoalLoopError("an increment needs a title")
    if origin not in ORIGINS:
        raise GoalLoopError(f"unknown origin: {origin}")
    if state not in STATES:
        raise GoalLoopError(f"unknown state: {state}")
    if not acceptance.strip():
        raise GoalLoopError(
            f"increment '{title}' needs a one-line acceptance test; without "
            "one the loop delivers it by deciding it is delivered"
        )
    increment = Increment(
        id=next_increment_id(loop),
        title=title.strip(),
        acceptance=acceptance.strip(),
        origin=origin,
        parent=parent,
        state=state,
        note=note,
        created=utc_now(),
        updated=utc_now(),
    )
    if after is None:
        loop.ledger.append(increment)
    elif after == "":
        loop.ledger.insert(0, increment)
    else:
        loop.ledger.insert(loop.ledger.index(find(loop, after)) + 1, increment)
    return increment


def _record_event(loop: GoalLoop, *, kind: str, summary: str, action: str, detail: str) -> None:
    loop.events.append(
        TriageEvent(
            at=utc_now(),
            iteration=len(loop.iterations),
            kind=kind,
            summary=summary,
            action=action,
            detail=detail,
        )
    )


def triage(
    loop: GoalLoop,
    *,
    kind: str,
    title: str,
    acceptance: str,
    because: str = "",
) -> Increment:
    """File newly-discovered work as either a blocker or a deferral.

    A blocker preempts: it goes to the front and whatever was active returns
    to pending, keeping a note saying what displaced it. A deferral is spliced
    in behind the active increment and waits its turn.

    The distinction is the only judgement call in the loop, so it is recorded
    with its reason. `kind` is not inferred from the text.
    """
    if kind not in (BLOCKER, DEFERRABLE):
        raise GoalLoopError(f"triage kind must be {BLOCKER} or {DEFERRABLE}, got {kind}")

    active = next((i for i in loop.ledger if i.state == ACTIVE), None)
    if kind == BLOCKER:
        increment = add_increment(
            loop, title=title, acceptance=acceptance, origin=PREEMPT, after="",
            note=because,
        )
        action = f"preempt: {increment.id} jumps the queue"
        if active is not None:
            _replace(
                loop,
                active,
                state=PENDING,
                note=f"displaced by {increment.id}: {because}".strip(": "),
            )
            action += f", {active.id} returned to pending"
            # The pass in progress was working the displaced increment, so it
            # is over. Leaving it open would make the next `begin` resume work
            # that is now blocked.
            abandoned = _close_open_record(
                loop,
                outcome=PREEMPTED,
                detail=f"displaced by {increment.id}: {because}".strip(": "),
            )
            if abandoned is not None:
                action += f", iteration {abandoned.n} abandoned"
    else:
        increment = add_increment(
            loop,
            title=title,
            acceptance=acceptance,
            origin=SPLICED,
            after=active.id if active else None,
            note=because,
        )
        action = f"splice: {increment.id} queued behind {active.id if active else 'the ledger'}"

    _record_event(loop, kind=kind, summary=title, action=action, detail=because)
    return increment


def split(loop: GoalLoop, increment_id: str, slices) -> list[Increment]:
    """Replace one increment with the smaller ones it turned out to be.

    The parent is dropped rather than deleted, and the children carry
    `parent`, so the ledger still explains why work appeared mid-run.
    """
    parent = find(loop, increment_id)
    if parent.state in (DELIVERED, DROPPED):
        raise GoalLoopError(f"{increment_id} is {parent.state} — nothing to split")
    if len(list(slices)) < 2:
        raise GoalLoopError("a split needs at least two slices")

    children: list[Increment] = []
    anchor = parent.id
    for title, acceptance in slices:
        child = add_increment(
            loop, title=title, acceptance=acceptance, origin=SPLIT,
            after=anchor, parent=parent.id,
        )
        children.append(child)
        anchor = child.id
    _replace(
        loop,
        parent,
        state=DROPPED,
        note=f"split into {', '.join(c.id for c in children)}",
    )
    _record_event(
        loop,
        kind=DEFERRABLE,
        summary=f"split {parent.id}",
        action=f"split: {parent.id} -> {', '.join(c.id for c in children)}",
        detail=parent.title,
    )
    return children


@dataclass(frozen=True, slots=True, kw_only=True)
class GoalStatus:
    """The done-test's verdict, and enough detail to act on a refusal."""

    met: bool
    stop_reason: str
    clauses: dict
    unmet: dict
    next_increment: str | None
    open_increments: tuple[str, ...]
    failing_sections: tuple[str, ...]
    needs_human: int
    unevidenced: tuple[str, ...]
    iterations_done: int
    max_iterations: int

    @property
    def should_continue(self) -> bool:
        return self.stop_reason in CONTINUING

    def to_dict(self) -> dict:
        return {
            "met": self.met,
            "stop_reason": self.stop_reason,
            "should_continue": self.should_continue,
            "clauses": dict(self.clauses),
            "unmet": dict(self.unmet),
            "next_increment": self.next_increment,
            "open_increments": list(self.open_increments),
            "failing_sections": list(self.failing_sections),
            "needs_human": self.needs_human,
            "unevidenced_acceptance": list(self.unevidenced),
            "iterations_done": self.iterations_done,
            "max_iterations": self.max_iterations,
        }


def begin_iteration(loop: GoalLoop, *, directory: str = "") -> IterationRecord:
    """Start the next pass, or resume the one already open.

    Blocked increments are never picked up automatically. A blocker the loop
    could clear on its own would have been cleared; what is left needs a
    person, and spinning on it is how an autonomous run burns an afternoon.
    """
    open_record = next((r for r in loop.iterations if not r.ended), None)
    if open_record is not None:
        if directory and not open_record.directory:
            # The nested plan session does not exist yet when an iteration
            # begins, so its directory is attached on the second call rather
            # than through a separate subcommand. Without this the loop has no
            # idea where the iteration's verification results landed, and
            # `gates_green` would never see them.
            open_record = IterationRecord(
                n=open_record.n,
                increment=open_record.increment,
                directory=str(directory),
                started=open_record.started,
            )
            loop.iterations[-1] = open_record
        return open_record

    candidate = next((i for i in loop.ledger if i.state == ACTIVE), None)
    if candidate is None:
        candidate = next((i for i in loop.ledger if i.state == PENDING), None)
    if candidate is None:
        blocked = [i.id for i in loop.ledger if i.state == BLOCKED]
        raise GoalLoopError(
            f"nothing to work on: {len(blocked)} blocked increment(s) "
            f"({', '.join(blocked)}) need a human"
            if blocked
            else "nothing to work on: the ledger has no pending increment"
        )

    number = len(loop.iterations) + 1
    _replace(loop, candidate, state=ACTIVE, iteration=number)
    record = IterationRecord(
        n=number,
        increment=candidate.id,
        directory=str(directory),
        started=utc_now(),
    )
    loop.iterations.append(record)
    return record


def _close_open_record(loop: GoalLoop, *, outcome: str, detail: str) -> IterationRecord | None:
    """Stamp the open iteration record closed. None if none was open."""
    record = next((r for r in loop.iterations if not r.ended), None)
    if record is None:
        return None
    closed = IterationRecord(
        n=record.n,
        increment=record.increment,
        directory=record.directory,
        started=record.started,
        ended=utc_now(),
        outcome=outcome,
        detail=detail,
    )
    loop.iterations[loop.iterations.index(record)] = closed
    return closed


def end_iteration(loop: GoalLoop, *, outcome: str, detail: str = "") -> IterationRecord:
    """Close the open pass and settle its increment.

    `preempted` is not accepted here — a preemption is `triage`'s business,
    because it has to move the ledger as well as close the record.
    """
    if outcome not in (DELIVERED, BLOCKED, DROPPED):
        raise GoalLoopError(
            f"outcome must be {DELIVERED}, {BLOCKED} or {DROPPED}, got {outcome}"
        )
    record = _close_open_record(loop, outcome=outcome, detail=detail)
    if record is None:
        raise GoalLoopError("no open iteration to end")
    _replace(loop, find(loop, record.increment), state=outcome, note=detail)
    return record


def add_evidence(
    loop: GoalLoop, *, acceptance_id: str, source: str, detail: str = ""
) -> Acceptance:
    """Attach a recorded observation to one acceptance line.

    `source` names where the observation lives — a test name, a report path, a
    command and its output. An acceptance line is met by evidence, never by an
    argument that it is met, so a `source` that names no artifact is refused.
    """
    if not source.strip():
        raise GoalLoopError(
            "evidence needs a source naming the artifact — a test, a report "
            "path, a command whose output was recorded"
        )
    for index, clause in enumerate(loop.acceptance):
        if clause.id != acceptance_id:
            continue
        updated = Acceptance(
            id=clause.id,
            text=clause.text,
            evidence=(
                *clause.evidence,
                Evidence(
                    iteration=len(loop.iterations),
                    source=source.strip(),
                    detail=detail,
                    recorded_at=utc_now(),
                ),
            ),
        )
        loop.acceptance[index] = updated
        return updated
    raise GoalLoopError(f"no such acceptance line: {acceptance_id}")


def _gate_report(loop: GoalLoop, planning_dir) -> tuple[tuple[str, ...], int, int]:
    """Sections that did not pass, needs-human count, results seen.

    Each iteration plans and implements in its own directory, so verification
    is spread across them. Aggregation is worst-first, the same rule
    `verification.phase_status` uses within one phase: a broken section does
    not become acceptable by sitting next to nine good ones.
    """
    directories = [Path(planning_dir)]
    directories += [Path(r.directory) for r in loop.iterations if r.directory]

    failing: list[str] = []
    pending_human = 0
    seen = 0
    for directory in dict.fromkeys(directories):
        status = phase_status(directory)
        seen += status.sections
        failing += [
            f"{directory.name}/{section}"
            for section, reason in sorted(status.reasons.items())
            if reason != PASSED
        ]
        pending_human += len(handoff.load(directory))
    return tuple(failing), pending_human, seen


def evaluate(loop: GoalLoop, planning_dir) -> GoalStatus:
    """The three-clause done test. All must hold; the refusal names which did not."""
    open_increments = tuple(i.id for i in loop.ledger if i.is_open)
    failing, pending_human, results_seen = _gate_report(loop, planning_dir)
    unevidenced = tuple(a.id for a in loop.acceptance if not a.evidenced)

    clauses = {
        "ledger_clear": bool(loop.ledger) and not open_increments,
        "gates_green": not failing and pending_human == 0 and results_seen > 0,
        "acceptance_evidenced": bool(loop.acceptance) and not unevidenced,
    }
    unmet: dict[str, str] = {}
    if not clauses["ledger_clear"]:
        unmet["ledger_clear"] = (
            "no increments on the ledger yet"
            if not loop.ledger
            else f"{len(open_increments)} open: {', '.join(open_increments)}"
        )
    if not clauses["gates_green"]:
        unmet["gates_green"] = (
            "no section has recorded a verification result"
            if results_seen == 0
            else f"{len(failing)} failing section(s), {pending_human} in the needs-human queue"
        )
    if not clauses["acceptance_evidenced"]:
        unmet["acceptance_evidenced"] = (
            "the goal has no acceptance lines"
            if not loop.acceptance
            else f"no evidence recorded for: {', '.join(unevidenced)}"
        )

    met = all(clauses.values())
    next_increment = next((i.id for i in loop.ledger if i.state in (ACTIVE, PENDING)), None)
    return GoalStatus(
        met=met,
        stop_reason=_stop_reason(
            loop,
            status={**clauses, "met": met},
            next_increment=next_increment,
            pending_human=pending_human,
        ),
        clauses=clauses,
        unmet=unmet,
        next_increment=next_increment,
        open_increments=open_increments,
        failing_sections=failing,
        needs_human=pending_human,
        unevidenced=unevidenced,
        iterations_done=len(loop.iterations),
        max_iterations=loop.max_iterations,
    )


def _stop_reason(loop: GoalLoop, *, status: dict, next_increment, pending_human: int) -> str:
    """Why the loop stops, or does not, in precedence order.

    Goal met outranks the iteration ceiling: a run that finished on its last
    allowed pass finished, it did not run out.
    """
    if status["met"]:
        return GOAL_MET
    if loop.max_iterations and len(loop.iterations) >= loop.max_iterations:
        return ITERATIONS_EXHAUSTED
    if next_increment is not None:
        return RUNNING
    if pending_human or any(i.state == BLOCKED for i in loop.ledger):
        return BLOCKED_ON_HUMAN
    if status["ledger_clear"] and status["gates_green"]:
        # The only thing missing is a measurement. Keep going: add an
        # increment that takes it, or record the evidence directly.
        return MEASUREMENT_NEEDED
    return BLOCKED_ON_HUMAN


_STATE_MARK = {
    PENDING: "[ ]",
    ACTIVE: "[>]",
    DELIVERED: "[x]",
    BLOCKED: "[!]",
    DROPPED: "[-]",
}


def render_ledger(loop: GoalLoop) -> str:
    """The run as one readable page.

    A convenience view of `goalloop.json`, regenerated on every write. Editing
    it by hand changes nothing — the loop reads the JSON.
    """
    lines = [
        "# Goal Ledger",
        "",
        "> Generated by `scripts/checks/goalloop.py`. Edit the goal or the",
        "> ledger through that CLI; this file is overwritten on every write.",
        "",
        "## Goal",
        "",
        loop.statement,
        "",
    ]
    if loop.target:
        lines += [f"**Target:** `{loop.target}`", ""]
    ceiling = str(loop.max_iterations) if loop.max_iterations else "unbounded"
    lines += [
        f"**Iterations:** {len(loop.iterations)} done, ceiling {ceiling}",
        "",
        "## Acceptance",
        "",
        "| | Clause | Evidence |",
        "|---|---|---|",
    ]
    for clause in loop.acceptance:
        evidence = (
            "; ".join(f"i{e.iteration} {e.source}" for e in clause.evidence)
            or "**none recorded**"
        )
        lines.append(f"| {clause.id} | {clause.text} | {evidence} |")

    lines += ["", "## Increments", ""]
    if not loop.ledger:
        lines.append("_Not decomposed yet._")
    for increment in loop.ledger:
        mark = _STATE_MARK.get(increment.state, "[ ]")
        when = f" · i{increment.iteration}" if increment.iteration else ""
        origin = "" if increment.origin == INITIAL else f" · {increment.origin}"
        lines.append(f"- {mark} **{increment.id}** {increment.title}{when}{origin}")
        lines.append(f"      acceptance: {increment.acceptance}")
        if increment.note:
            lines.append(f"      note: {increment.note}")

    if loop.iterations:
        lines += ["", "## Iteration log", "", "| # | Increment | Outcome | Detail |", "|---|---|---|---|"]
        for record in loop.iterations:
            outcome = record.outcome or "_open_"
            lines.append(
                f"| {record.n} | {record.increment} | {outcome} | {record.detail} |"
            )

    if loop.events:
        lines += ["", "## Triage log", "", "| At | Kind | What came up | Action |", "|---|---|---|---|"]
        for event in loop.events:
            lines.append(
                f"| i{event.iteration} | {event.kind} | {event.summary} | {event.action} |"
            )
    return "\n".join(lines) + "\n"


def summary(loop: GoalLoop, status: GoalStatus) -> str:
    """The end-of-run report.

    Leads with the verdict and, when the goal was not met, with what is
    outstanding. A run that stops without saying what is left is the failure
    this is here to prevent — the same reason `auto-gate.py handoff` exists.
    """
    headline = {
        GOAL_MET: "**Goal met.**",
        ITERATIONS_EXHAUSTED: f"**Stopped: iteration ceiling ({loop.max_iterations}) reached.**",
        BLOCKED_ON_HUMAN: "**Stopped: needs a human.**",
        MEASUREMENT_NEEDED: "**Built and passing, not yet measured.**",
        RUNNING: "**Still running.**",
    }[status.stop_reason]

    lines = [
        "## Goalloop summary",
        "",
        headline,
        "",
        loop.statement,
        "",
        (
            f"{status.iterations_done} iteration(s). "
            f"{sum(1 for i in loop.ledger if i.state == DELIVERED)} of "
            f"{len(loop.ledger)} increment(s) delivered."
        ),
        "",
    ]
    if status.met:
        lines += ["Every acceptance line has recorded evidence:", ""]
        lines += [
            f"- {c.id} {c.text} — {'; '.join(e.source for e in c.evidence)}"
            for c in loop.acceptance
        ]
        return "\n".join(lines) + "\n"

    lines += ["### Outstanding", ""]
    lines += [f"- **{clause}** — {reason}" for clause, reason in status.unmet.items()]
    if status.open_increments:
        lines += ["", "### Increments left", ""]
        lines += [
            f"- {i.id} ({i.state}) {i.title} — {i.acceptance}"
            for i in loop.ledger
            if i.is_open
        ]
    if status.unevidenced:
        lines += ["", "### Acceptance lines with no evidence", ""]
        lines += [
            f"- {c.id} {c.text}" for c in loop.acceptance if not c.evidenced
        ]
    if status.failing_sections:
        lines += ["", "### Sections that did not pass", ""]
        lines += [f"- {section}" for section in status.failing_sections]
    return "\n".join(lines) + "\n"

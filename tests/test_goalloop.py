"""Goal, ledger, and the three-clause done test.

The tests that matter most here are the ones asserting the loop *refuses* to
finish: a run that declares victory with work outstanding, gates red, or an
acceptance line nobody measured is the failure mode this module exists to
prevent, and each of those has to stay a separate clause.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib import goalloop as gl
from lib import handoff, verification

CLI = Path(__file__).resolve().parent.parent / "scripts" / "checks" / "goalloop.py"

GOAL = "The price board reflects the current rack within a minute, no manual step."
ACCEPTANCE = [
    "A rack change appears on the board within 60s, measured end to end",
    "No operator touches a spreadsheet in the path",
]


@pytest.fixture
def planning_dir(tmp_path):
    (tmp_path / ".deepstate").mkdir()
    return tmp_path


@pytest.fixture
def loop(planning_dir):
    return gl.init(
        planning_dir, statement=GOAL, acceptance=ACCEPTANCE, target="/repo"
    )


def stock_ledger(loop):
    for title, acceptance in (
        ("read path behind a flag", "flag off = old behaviour, proven by a test"),
        ("backfill job", "runs twice, same row count"),
        ("cutover", "flag gone, no references remain"),
    ):
        gl.add_increment(loop, title=title, acceptance=acceptance)
    return loop


def pass_a_section(directory, name="S01"):
    Path(directory).mkdir(parents=True, exist_ok=True)
    verification.record(directory, section=name, gates_passed=True)


class TestInit:
    def test_init_writes_state_and_the_readable_ledger(self, planning_dir, loop):
        assert gl.state_path(planning_dir).exists()
        assert gl.ledger_path(planning_dir).exists()
        assert loop.statement == GOAL
        assert [a.id for a in loop.acceptance] == ["A1", "A2"]
        assert loop.max_iterations == 0  # unbounded unless asked otherwise

    def test_a_goal_with_no_acceptance_line_is_refused(self, planning_dir):
        # Without one there is nothing for evidence to satisfy, so the loop
        # could never terminate on its own.
        with pytest.raises(gl.GoalLoopError, match="acceptance line"):
            gl.init(planning_dir, statement=GOAL, acceptance=[])

    def test_an_empty_statement_is_refused(self, planning_dir):
        with pytest.raises(gl.GoalLoopError, match="end state"):
            gl.init(planning_dir, statement="   ", acceptance=ACCEPTANCE)

    def test_init_will_not_overwrite_a_running_goal(self, planning_dir, loop):
        with pytest.raises(gl.GoalLoopError, match="already set"):
            gl.init(planning_dir, statement="something else", acceptance=["x"])

    def test_load_returns_none_when_no_goal_is_set(self, planning_dir):
        assert gl.load(planning_dir) is None

    def test_a_corrupt_state_file_reads_as_no_goal_not_a_crash(self, planning_dir, loop):
        gl.state_path(planning_dir).write_text("{ truncated")
        assert gl.load(planning_dir) is None

    def test_state_survives_a_round_trip(self, planning_dir, loop):
        stock_ledger(loop)
        gl.triage(loop, kind=gl.BLOCKER, title="missing column",
                  acceptance="column added", because="cannot detect changes")
        gl.save(planning_dir, loop)
        again = gl.load(planning_dir)
        assert again.to_dict() == loop.to_dict()


class TestLedger:
    def test_ids_are_sequential_and_never_reused(self, loop):
        stock_ledger(loop)
        assert [i.id for i in loop.ledger] == ["I01", "I02", "I03"]
        gl.split(loop, "I02", [("drop reads", "no reads left"), ("drop table", "table gone")])
        # I02 is dropped, and its id stays retired.
        assert gl.next_increment_id(loop) == "I06"

    def test_an_increment_without_an_acceptance_line_is_refused(self, loop):
        with pytest.raises(gl.GoalLoopError, match="acceptance test"):
            gl.add_increment(loop, title="do the thing", acceptance="")

    def test_after_inserts_behind_the_named_increment(self, loop):
        stock_ledger(loop)
        gl.add_increment(loop, title="wedged", acceptance="done", after="I01")
        assert [i.id for i in loop.ledger] == ["I01", "I04", "I02", "I03"]

    def test_split_replaces_the_parent_and_keeps_the_lineage(self, loop):
        stock_ledger(loop)
        children = gl.split(
            loop, "I03",
            [("drop the reads", "no caller reads it"), ("drop the table", "table gone")],
        )
        assert gl.find(loop, "I03").state == gl.DROPPED
        assert [c.parent for c in children] == ["I03", "I03"]
        assert [i.id for i in loop.ledger] == ["I01", "I02", "I03", "I04", "I05"]
        assert "split into I04, I05" in gl.find(loop, "I03").note

    def test_a_split_needs_at_least_two_slices(self, loop):
        stock_ledger(loop)
        with pytest.raises(gl.GoalLoopError, match="at least two"):
            gl.split(loop, "I01", [("only one", "done")])

    def test_a_delivered_increment_cannot_be_split(self, loop):
        stock_ledger(loop)
        gl.begin_iteration(loop)
        gl.end_iteration(loop, outcome=gl.DELIVERED)
        with pytest.raises(gl.GoalLoopError, match="delivered"):
            gl.split(loop, "I01", [("a", "x"), ("b", "y")])

    def test_an_unknown_increment_is_named_in_the_error(self, loop):
        with pytest.raises(gl.GoalLoopError, match="I99"):
            gl.find(loop, "I99")


class TestTriage:
    def test_a_blocker_jumps_the_queue_and_returns_the_active_one_to_pending(self, loop):
        stock_ledger(loop)
        gl.begin_iteration(loop)
        blocker = gl.triage(
            loop, kind=gl.BLOCKER, title="source has no updated_at",
            acceptance="column added and backfilled",
            because="cannot detect a rack change without it",
        )
        assert loop.ledger[0].id == blocker.id
        assert gl.find(loop, "I01").state == gl.PENDING
        assert "displaced by I04" in gl.find(loop, "I01").note

    def test_a_blocker_abandons_the_pass_in_progress(self, loop):
        # Leaving the record open would make the next `begin` resume work that
        # is now blocked on the increment that displaced it.
        stock_ledger(loop)
        gl.begin_iteration(loop)
        gl.triage(loop, kind=gl.BLOCKER, title="blocker", acceptance="fixed")
        assert loop.iterations[0].outcome == gl.PREEMPTED
        assert gl.begin_iteration(loop).increment == "I04"

    def test_a_deferral_waits_behind_the_active_increment(self, loop):
        stock_ledger(loop)
        gl.begin_iteration(loop)
        gl.triage(
            loop, kind=gl.DEFERRABLE, title="metrics tile",
            acceptance="tile shows p95", because="not blocking cutover",
        )
        assert [i.id for i in loop.ledger] == ["I01", "I04", "I02", "I03"]
        assert gl.find(loop, "I01").state == gl.ACTIVE  # work continues
        assert loop.iterations[0].ended == ""

    def test_a_deferral_with_nothing_active_lands_at_the_end(self, loop):
        stock_ledger(loop)
        gl.triage(loop, kind=gl.DEFERRABLE, title="later", acceptance="done")
        assert loop.ledger[-1].title == "later"

    def test_every_triage_decision_is_logged_with_its_reason(self, loop):
        stock_ledger(loop)
        gl.triage(loop, kind=gl.BLOCKER, title="blocker",
                  acceptance="fixed", because="it blocks")
        event = loop.events[-1]
        assert (event.kind, event.summary, event.detail) == (
            gl.BLOCKER, "blocker", "it blocks",
        )
        assert "preempt" in event.action

    def test_the_kind_is_never_inferred(self, loop):
        with pytest.raises(gl.GoalLoopError, match="triage kind"):
            gl.triage(loop, kind="probably_a_blocker", title="x", acceptance="y")


class TestIterations:
    def test_begin_takes_the_first_pending_increment(self, loop):
        stock_ledger(loop)
        record = gl.begin_iteration(loop, directory="/iters/i01")
        assert (record.n, record.increment, record.directory) == (1, "I01", "/iters/i01")
        assert gl.find(loop, "I01").state == gl.ACTIVE

    def test_begin_resumes_an_open_pass_rather_than_starting_a_second(self, loop):
        stock_ledger(loop)
        first = gl.begin_iteration(loop)
        assert gl.begin_iteration(loop) == first
        assert len(loop.iterations) == 1

    def test_a_delivered_pass_settles_its_increment(self, loop):
        stock_ledger(loop)
        gl.begin_iteration(loop)
        gl.end_iteration(loop, outcome=gl.DELIVERED, detail="shipped behind the flag")
        assert gl.find(loop, "I01").state == gl.DELIVERED
        assert gl.begin_iteration(loop).increment == "I02"

    def test_a_blocked_increment_is_not_picked_up_again(self, loop):
        # Whatever the loop could clear on its own it already cleared. What is
        # left needs a person, and retrying it burns the run.
        gl.add_increment(loop, title="needs a decision", acceptance="decided")
        gl.begin_iteration(loop)
        gl.end_iteration(loop, outcome=gl.BLOCKED, detail="which BU owns this?")
        with pytest.raises(gl.GoalLoopError, match="blocked"):
            gl.begin_iteration(loop)

    def test_begin_on_an_empty_ledger_says_so(self, loop):
        with pytest.raises(gl.GoalLoopError, match="no pending increment"):
            gl.begin_iteration(loop)

    def test_preempted_is_not_an_outcome_end_iteration_accepts(self, loop):
        stock_ledger(loop)
        gl.begin_iteration(loop)
        with pytest.raises(gl.GoalLoopError, match="outcome must be"):
            gl.end_iteration(loop, outcome=gl.PREEMPTED)

    def test_ending_with_no_open_pass_is_an_error(self, loop):
        with pytest.raises(gl.GoalLoopError, match="no open iteration"):
            gl.end_iteration(loop, outcome=gl.DELIVERED)


class TestEvidence:
    def test_evidence_attaches_to_the_named_clause(self, loop):
        stock_ledger(loop)
        gl.begin_iteration(loop)
        clause = gl.add_evidence(
            loop, acceptance_id="A1",
            source="tests/test_lag.py::test_under_60s", detail="p95 41s",
        )
        assert clause.evidenced
        assert clause.evidence[0].iteration == 1
        assert not loop.acceptance[1].evidenced

    def test_evidence_needs_a_source_naming_an_artifact(self, loop):
        # An acceptance line is met by evidence, never by an argument that it
        # is met.
        with pytest.raises(gl.GoalLoopError, match="naming the artifact"):
            gl.add_evidence(loop, acceptance_id="A1", source="  ")

    def test_an_unknown_clause_is_refused(self, loop):
        with pytest.raises(gl.GoalLoopError, match="A9"):
            gl.add_evidence(loop, acceptance_id="A9", source="somewhere")


class TestDoneTest:
    def deliver_everything(self, loop, planning_dir):
        stock_ledger(loop)
        for _ in range(3):
            record = gl.begin_iteration(
                loop, directory=str(Path(planning_dir) / "iters" / "x")
            )
            pass_a_section(record.directory, f"S{record.n}")
            gl.end_iteration(loop, outcome=gl.DELIVERED)
        for clause in list(loop.acceptance):
            gl.add_evidence(loop, acceptance_id=clause.id, source="a recorded run")
        return loop

    def test_all_three_clauses_holding_is_met(self, loop, planning_dir):
        self.deliver_everything(loop, planning_dir)
        status = gl.evaluate(loop, planning_dir)
        assert status.met is True
        assert status.stop_reason == gl.GOAL_MET
        assert status.unmet == {}

    def test_an_open_increment_keeps_the_loop_running(self, loop, planning_dir):
        self.deliver_everything(loop, planning_dir)
        gl.add_increment(loop, title="one more thing", acceptance="done")
        status = gl.evaluate(loop, planning_dir)
        assert not status.met
        assert "I04" in status.unmet["ledger_clear"]
        assert status.stop_reason == gl.RUNNING

    def test_a_failing_section_blocks_a_clear_ledger(self, loop, planning_dir):
        self.deliver_everything(loop, planning_dir)
        verification.record(
            Path(planning_dir) / "iters" / "x", section="S9", gates_passed=False
        )
        status = gl.evaluate(loop, planning_dir)
        assert not status.met
        assert status.clauses["gates_green"] is False
        assert any("S9" in s for s in status.failing_sections)

    def test_a_needs_human_item_blocks_it_too(self, loop, planning_dir):
        self.deliver_everything(loop, planning_dir)
        handoff.record(
            Path(planning_dir) / "iters" / "x", section="S2",
            reason="three_strikes", detail="rolled back",
        )
        status = gl.evaluate(loop, planning_dir)
        assert not status.met
        assert status.needs_human == 1

    def test_an_unmeasured_acceptance_line_blocks_it(self, loop, planning_dir):
        # Everything built, gates green, and nobody checked the thing the user
        # actually asked for.
        self.deliver_everything(loop, planning_dir)
        loop.acceptance.append(gl.Acceptance(id="A3", text="board refreshes under 2s"))
        status = gl.evaluate(loop, planning_dir)
        assert not status.met
        assert status.unevidenced == ("A3",)
        assert "A3" in status.unmet["acceptance_evidenced"]

    def test_a_ledger_that_was_never_decomposed_is_not_clear(self, loop, planning_dir):
        status = gl.evaluate(loop, planning_dir)
        assert status.clauses["ledger_clear"] is False
        assert "no increments" in status.unmet["ledger_clear"]

    def test_gates_are_not_green_when_nothing_was_ever_verified(self, loop, planning_dir):
        # Absence of evidence is the usual way an autonomous run convinces
        # itself everything is fine.
        stock_ledger(loop)
        for _ in range(3):
            gl.begin_iteration(loop)
            gl.end_iteration(loop, outcome=gl.DELIVERED)
        for clause in list(loop.acceptance):
            gl.add_evidence(loop, acceptance_id=clause.id, source="a run")
        status = gl.evaluate(loop, planning_dir)
        assert status.clauses["gates_green"] is False
        assert "no section has recorded" in status.unmet["gates_green"]

    def test_the_ceiling_stops_a_run_that_has_not_finished(self, planning_dir):
        loop = gl.init(
            planning_dir, statement=GOAL, acceptance=ACCEPTANCE, max_iterations=2
        )
        stock_ledger(loop)
        for _ in range(2):
            gl.begin_iteration(loop)
            gl.end_iteration(loop, outcome=gl.DELIVERED)
        status = gl.evaluate(loop, planning_dir)
        assert status.stop_reason == gl.ITERATIONS_EXHAUSTED
        assert not status.should_continue

    def test_meeting_the_goal_on_the_last_allowed_pass_reads_as_met(self, planning_dir):
        # Finished on the final pass is finished, not out of budget.
        loop = gl.init(
            planning_dir, statement=GOAL, acceptance=["it works"], max_iterations=1
        )
        gl.add_increment(loop, title="the whole thing", acceptance="it works")
        record = gl.begin_iteration(loop, directory=str(planning_dir / "i01"))
        pass_a_section(record.directory)
        gl.end_iteration(loop, outcome=gl.DELIVERED)
        gl.add_evidence(loop, acceptance_id="A1", source="tests/test_it.py")
        status = gl.evaluate(loop, planning_dir)
        assert status.stop_reason == gl.GOAL_MET

    def test_an_unmeasured_acceptance_line_keeps_the_loop_working(
        self, loop, planning_dir
    ):
        # Everything built and passing, one line nobody measured. Halting here
        # would hand back a run that was one command from done.
        self.deliver_everything(loop, planning_dir)
        loop.acceptance.append(gl.Acceptance(id="A3", text="board refreshes under 2s"))
        status = gl.evaluate(loop, planning_dir)
        assert status.stop_reason == gl.MEASUREMENT_NEEDED
        assert status.should_continue is True
        assert status.next_increment is None

    def test_a_failing_gate_still_halts_rather_than_asking_for_a_measurement(
        self, loop, planning_dir
    ):
        # measurement_needed is only for a run that is otherwise finished.
        self.deliver_everything(loop, planning_dir)
        loop.acceptance.append(gl.Acceptance(id="A3", text="unmeasured"))
        verification.record(
            Path(planning_dir) / "iters" / "x", section="S9", gates_passed=False
        )
        assert gl.evaluate(loop, planning_dir).stop_reason == gl.BLOCKED_ON_HUMAN

    def test_the_ceiling_outranks_a_pending_measurement(self, planning_dir):
        loop = gl.init(
            planning_dir, statement=GOAL, acceptance=["measure me"], max_iterations=1
        )
        gl.add_increment(loop, title="thing", acceptance="done")
        record = gl.begin_iteration(loop, directory=str(planning_dir / "i01"))
        pass_a_section(record.directory)
        gl.end_iteration(loop, outcome=gl.DELIVERED)
        assert gl.evaluate(loop, planning_dir).stop_reason == gl.ITERATIONS_EXHAUSTED

    def test_a_blocked_increment_halts_rather_than_spins(self, loop, planning_dir):
        gl.add_increment(loop, title="needs a decision", acceptance="decided")
        record = gl.begin_iteration(loop, directory=str(planning_dir / "i01"))
        pass_a_section(record.directory)
        gl.end_iteration(loop, outcome=gl.BLOCKED, detail="which BU owns this?")
        status = gl.evaluate(loop, planning_dir)
        assert status.stop_reason == gl.BLOCKED_ON_HUMAN
        assert not status.should_continue


class TestRendering:
    def test_the_ledger_shows_state_evidence_and_triage(self, loop, planning_dir):
        stock_ledger(loop)
        gl.begin_iteration(loop)
        gl.triage(loop, kind=gl.BLOCKER, title="missing column",
                  acceptance="column added", because="blocks detection")
        gl.add_evidence(loop, acceptance_id="A1", source="tests/test_lag.py")
        rendered = gl.render_ledger(loop)
        assert GOAL in rendered
        assert "tests/test_lag.py" in rendered
        assert "**none recorded**" in rendered  # A2 has nothing yet
        assert "missing column" in rendered
        assert "## Triage log" in rendered

    def test_an_undecomposed_ledger_says_so(self, loop):
        assert "_Not decomposed yet._" in gl.render_ledger(loop)

    def test_the_summary_of_an_unmet_goal_leads_with_what_is_outstanding(
        self, loop, planning_dir
    ):
        stock_ledger(loop)
        status = gl.evaluate(loop, planning_dir)
        report = gl.summary(loop, status)
        assert "Still running" in report
        assert "### Increments left" in report
        assert "### Acceptance lines with no evidence" in report

    def test_the_summary_of_a_met_goal_cites_the_evidence(self, loop, planning_dir):
        stock_ledger(loop)
        for _ in range(3):
            record = gl.begin_iteration(loop, directory=str(planning_dir / "i"))
            pass_a_section(record.directory, f"S{record.n}")
            gl.end_iteration(loop, outcome=gl.DELIVERED)
        for clause in list(loop.acceptance):
            gl.add_evidence(loop, acceptance_id=clause.id, source=f"proof-{clause.id}")
        report = gl.summary(loop, gl.evaluate(loop, planning_dir))
        assert "**Goal met.**" in report
        assert "proof-A1" in report and "proof-A2" in report

    def test_a_ceiling_stop_names_the_ceiling(self, planning_dir):
        loop = gl.init(planning_dir, statement=GOAL, acceptance=["x"], max_iterations=1)
        gl.add_increment(loop, title="thing", acceptance="done")
        gl.begin_iteration(loop)
        gl.end_iteration(loop, outcome=gl.DELIVERED)
        report = gl.summary(loop, gl.evaluate(loop, planning_dir))
        assert "iteration ceiling (1)" in report


class TestCLI:
    def run(self, planning_dir, *args):
        return subprocess.run(
            [sys.executable, str(CLI), "--planning-dir", str(planning_dir), *args],
            capture_output=True,
            text=True,
        )

    def init(self, planning_dir, *extra):
        return self.run(
            planning_dir, "init", "--goal", GOAL,
            "--acceptance", ACCEPTANCE[0], "--acceptance", ACCEPTANCE[1], *extra,
        )

    def test_init_reports_the_files_it_wrote(self, planning_dir):
        result = self.init(planning_dir)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["acceptance"] == ["A1", "A2"]
        assert Path(payload["ledger_file"]).exists()

    def test_init_from_a_file(self, planning_dir, tmp_path):
        goal_file = tmp_path / "goal.md"
        goal_file.write_text(GOAL)
        result = self.run(
            planning_dir, "init", "--goal-file", str(goal_file),
            "--acceptance", "it works",
        )
        assert json.loads(result.stdout)["goal"] == GOAL

    def test_tick_returns_three_while_work_remains(self, planning_dir):
        self.init(planning_dir)
        self.run(planning_dir, "add", "--title", "slice one", "--acceptance", "done")
        result = self.run(planning_dir, "tick")
        assert result.returncode == 3
        payload = json.loads(result.stdout)
        assert payload["should_continue"] is True
        assert "Run iteration 1 on I01" in payload["guidance"]

    def test_tick_returns_zero_when_the_goal_is_met(self, planning_dir):
        self.init(planning_dir)
        self.run(planning_dir, "add", "--title", "the work", "--acceptance", "done")
        iteration_dir = planning_dir / "i01"
        self.run(planning_dir, "begin", "--dir", str(iteration_dir))
        pass_a_section(iteration_dir)
        self.run(planning_dir, "end", "--outcome", "delivered")
        for clause in ("A1", "A2"):
            self.run(
                planning_dir, "evidence", "--acceptance-id", clause,
                "--source", f"proof-{clause}",
            )
        result = self.run(planning_dir, "tick")
        assert result.returncode == 0
        assert json.loads(result.stdout)["met"] is True

    def test_tick_returns_one_when_a_human_is_needed(self, planning_dir):
        self.init(planning_dir)
        self.run(planning_dir, "add", "--title", "the work", "--acceptance", "done")
        self.run(planning_dir, "begin", "--dir", str(planning_dir / "i01"))
        self.run(planning_dir, "end", "--outcome", "blocked", "--detail", "who owns this?")
        result = self.run(planning_dir, "tick")
        assert result.returncode == 1
        assert json.loads(result.stdout)["stop_reason"] == gl.BLOCKED_ON_HUMAN

    def test_tick_asks_for_a_measurement_rather_than_halting(self, planning_dir):
        self.init(planning_dir)
        self.run(planning_dir, "add", "--title", "the work", "--acceptance", "done")
        iteration_dir = planning_dir / "i01"
        self.run(planning_dir, "begin", "--dir", str(iteration_dir))
        pass_a_section(iteration_dir)
        self.run(planning_dir, "end", "--outcome", "delivered")
        result = self.run(planning_dir, "tick")
        assert result.returncode == 3
        payload = json.loads(result.stdout)
        assert payload["stop_reason"] == gl.MEASUREMENT_NEEDED
        assert "do not record an argument as evidence" in payload["guidance"]

    def test_triage_reports_what_it_did_to_the_ledger(self, planning_dir):
        self.init(planning_dir)
        self.run(planning_dir, "add", "--title", "slice one", "--acceptance", "done")
        self.run(planning_dir, "begin")
        result = self.run(
            planning_dir, "triage", "--kind", "blocker", "--title", "missing column",
            "--acceptance", "column added", "--because", "blocks detection",
        )
        payload = json.loads(result.stdout)
        assert payload["ledger"] == ["I02", "I01"]
        assert "preempt" in payload["action"]

    def test_split_parses_the_slice_syntax(self, planning_dir):
        self.init(planning_dir)
        self.run(planning_dir, "add", "--title", "big thing", "--acceptance", "done")
        result = self.run(
            planning_dir, "split", "--increment", "I01",
            "--slice", "drop reads :: no caller reads it",
            "--slice", "drop table :: table is gone",
        )
        children = json.loads(result.stdout)["children"]
        assert [c["title"] for c in children] == ["drop reads", "drop table"]
        assert children[0]["acceptance"] == "no caller reads it"

    def test_a_slice_without_an_acceptance_line_is_a_usage_error(self, planning_dir):
        self.init(planning_dir)
        self.run(planning_dir, "add", "--title", "big", "--acceptance", "done")
        result = self.run(
            planning_dir, "split", "--increment", "I01",
            "--slice", "no separator here", "--slice", "also :: fine",
        )
        assert result.returncode == 2
        assert "title :: acceptance" in json.loads(result.stdout)["error"]

    def test_commands_before_init_explain_what_is_missing(self, planning_dir):
        result = self.run(planning_dir, "tick")
        assert result.returncode == 2
        assert "no goal set" in json.loads(result.stdout)["error"]

    def test_handoff_renders_markdown_not_json(self, planning_dir):
        self.init(planning_dir)
        result = self.run(planning_dir, "handoff")
        assert result.returncode == 0
        assert result.stdout.startswith("## Goalloop summary")

    def test_status_carries_the_whole_record(self, planning_dir):
        self.init(planning_dir, "--max-iters", "4")
        payload = json.loads(self.run(planning_dir, "status").stdout)
        assert payload["goal"]["max_iterations"] == 4
        assert payload["status"]["stop_reason"] == gl.BLOCKED_ON_HUMAN

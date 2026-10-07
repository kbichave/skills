"""The data tier's read-only SQL gate, its hook, and the marker that arms it."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from lib import sql_guard

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "hooks" / "warehouse-sql-guard.py"
CLI = ROOT / "scripts" / "checks" / "data-tier.py"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"


class TestClassify:
    @pytest.mark.parametrize(
        "sql",
        [
            "select count(*) from DB.S.T",
            "SELECT site_id, count(*) FROM DB.S.T GROUP BY site_id",
            "with x as (select a from DB.S.T) select max(a) from x",
            "select a, b from DB.S.T limit 100",
            "describe table DB.S.T",
            "show tables like 'FOO%' in schema DB.S",
            "select a from t where note = 'drop table x; delete' limit 5",
            "select created_at, is_deleted from t limit 10",
            "-- delete everything\nselect count(*) from t",
            "select count(*) from t;",
        ],
    )
    def test_allowed(self, sql):
        assert sql_guard.classify(sql) is None

    @pytest.mark.parametrize(
        ("sql", "reason_part"),
        [
            ("delete from DB.S.T", "DELETE"),
            ("insert into t select 1", "INSERT"),
            ("create table t as select 1", "CREATE"),
            ("with x as (select 1) delete from t", "DELETE"),
            ("select 1 limit 1; drop table t", "one statement"),
            ("select * from t limit 10", "SELECT *"),
            ("select t.* from t limit 10", "SELECT *"),
            ("select a, b from DB.S.T", "LIMIT"),
            ("use role ACCOUNTADMIN", "USE"),
            ("call my_proc()", "CALL"),
            ("", "empty"),
        ],
    )
    def test_blocked(self, sql, reason_part):
        reason = sql_guard.classify(sql)
        assert reason is not None and reason_part in reason


class TestExtract:
    def test_batch_and_single_shapes(self):
        payload = {"sql": "a", "queries": ["b", {"query": "c"}]}
        assert sql_guard.extract_sql(payload) == ["a", "b", "c"]

    @pytest.mark.parametrize(
        "name",
        ["mcp__claude_ai_dbt__execute_sql", "mcp__dbt__execute_sql",
         "mcp__dq__sf_query", "mcp__dq__sf_batch"],
    )
    def test_warehouse_tools_match(self, name):
        assert sql_guard.WAREHOUSE_TOOL.match(name)

    @pytest.mark.parametrize("name", ["Bash", "mcp__dbt__get_lineage", "Write"])
    def test_other_tools_do_not(self, name):
        assert not sql_guard.WAREHOUSE_TOOL.match(name)


class TestMarker:
    def test_start_stop_roundtrip(self):
        assert not sql_guard.is_active("s1")
        sql_guard.start("s1")
        assert sql_guard.is_active("s1")
        assert not sql_guard.is_active("s2")
        assert sql_guard.stop("s1")
        assert not sql_guard.is_active("s1")

    def test_expires(self):
        sql_guard.start("s1", timedelta(minutes=1))
        later = datetime.now(UTC) + timedelta(minutes=2)
        assert not sql_guard.is_active("s1", now=later)

    def test_session_id_cannot_escape_dir(self):
        path = sql_guard.start("../../evil")
        assert path.parent == sql_guard.marker_dir()


def _run_hook(payload: object, raw: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=raw if raw is not None else json.dumps(payload),
        capture_output=True, text=True, env=os.environ.copy(), timeout=10, check=False,
    )


def _payload(sql: str, session: str = "hook-s") -> dict:
    return {"tool_name": "mcp__dbt__execute_sql", "session_id": session,
            "tool_input": {"sql": sql}}


class TestHook:
    def test_inactive_session_is_silent_even_for_writes(self):
        result = _run_hook(_payload("drop table t"))
        assert result.returncode == 0 and result.stdout == ""

    def test_active_session_denies_write(self):
        sql_guard.start("hook-s")
        result = _run_hook(_payload("drop table t"))
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "DROP" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_active_session_allows_read_with_no_stdout(self):
        sql_guard.start("hook-s")
        result = _run_hook(_payload("select count(*) from t"))
        assert result.returncode == 0 and result.stdout == ""

    def test_non_warehouse_tool_ignored(self):
        sql_guard.start("hook-s")
        result = _run_hook({"tool_name": "Bash", "session_id": "hook-s",
                            "tool_input": {"command": "drop table t"}})
        assert result.stdout == ""

    @pytest.mark.parametrize("raw", ["not json", "[]", '{"tool_input": 5}'])
    def test_fails_open_on_bad_payload(self, raw):
        result = _run_hook(None, raw=raw)
        assert result.returncode == 0 and result.stdout == ""

    def test_registered_with_python3(self):
        hooks = json.loads(HOOKS_JSON.read_text())["hooks"]["PreToolUse"]
        commands = [h["command"] for entry in hooks for h in entry["hooks"]]
        assert any(c.startswith("python3 ") and "warehouse-sql-guard.py" in c
                   for c in commands)


class TestCli:
    def _cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                              text=True, env=os.environ.copy(), timeout=10, check=False)

    def test_lifecycle_exit_codes(self):
        assert self._cli("status", "--session", "c1").returncode == 1
        assert self._cli("start", "--session", "c1").returncode == 0
        assert self._cli("status", "--session", "c1").returncode == 0
        assert self._cli("stop", "--session", "c1").returncode == 0
        assert self._cli("status", "--session", "c1").returncode == 1

    def test_empty_session_is_usage_error(self):
        assert self._cli("start", "--session", " ").returncode == 2

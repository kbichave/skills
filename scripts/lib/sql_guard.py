"""Read-only gate for SQL the warehouse tier sends to a warehouse MCP tool.

The data tier runs model-written SQL against production. Prompts tell the
agents to stay read-only, but a prompt is a request and this is a check. The
hook that calls it (`warehouse-sql-guard.py`) is active only while a data-tier
run is open for the session, so a user's own Snowflake work in the same
session is never touched.

`classify` returns the first problem found, or None for an allowed statement:

- one statement only;
- it starts with SELECT, WITH, DESCRIBE/DESC, SHOW or EXPLAIN;
- no write or DDL keyword anywhere outside string literals and comments;
- no `SELECT *` (a `COUNT(*)` is fine);
- a statement that reads rows without aggregating carries a LIMIT.

This is a lexical check, not a parser. It errs toward blocking, and every
block names the rule so the agent can rewrite the query.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ALLOWED_LEAD = ("SELECT", "WITH", "DESCRIBE", "DESC", "SHOW", "EXPLAIN")
_WRITE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|DROP|CREATE|ALTER|GRANT|REVOKE|"
    r"COPY|PUT|REMOVE|UNDROP|CALL|EXECUTE|USE|SET|UNSET|BEGIN|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)
_STAR = re.compile(r"SELECT\s+(DISTINCT\s+)?(\w+\.)?\*", re.IGNORECASE)
_AGGREGATE = re.compile(
    r"\b(COUNT|SUM|AVG|MIN|MAX|MEDIAN|STDDEV\w*|VARIANCE|PERCENTILE_\w+|"
    r"APPROX_\w+|COUNT_IF|LISTAGG|ARRAY_AGG|ANY_VALUE)\s*\(|\bGROUP\s+BY\b",
    re.IGNORECASE,
)
_LIMIT = re.compile(r"\b(LIMIT\s+\d+|TOP\s+\d+|FETCH\s+FIRST)\b", re.IGNORECASE)

# Tool names whose `sql`/`query`/`statement` argument the hook checks.
WAREHOUSE_TOOL = re.compile(
    r"^mcp__.*(execute_sql|sf_query|sf_batch|run_snowflake_query|snowflake.*query|"
    r"run_query|query_sql)$",
    re.IGNORECASE,
)


def strip_literals(sql: str) -> str:
    """Blank out comments and quoted text so keywords inside them don't count."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    return re.sub(r'"(?:[^"]|"")*"', '""', sql)


def _statements(code: str) -> list[str]:
    return [s.strip() for s in code.split(";") if s.strip()]


def classify(sql: str) -> str | None:
    """Return why `sql` is blocked, or None when it may run."""
    code = strip_literals(sql or "")
    statements = _statements(code)
    if not statements:
        return "empty statement"
    if len(statements) > 1:
        return "one statement per call (split the batch into separate queries)"
    stmt = statements[0]
    lead = stmt.split(None, 1)[0].upper()
    if lead not in _ALLOWED_LEAD:
        return f"read-only tier allows SELECT/WITH/DESCRIBE/SHOW/EXPLAIN, got {lead}"
    write = _WRITE_WORDS.search(stmt)
    if write:
        return f"write or session keyword {write.group(1).upper()} in a read-only query"
    if _STAR.search(stmt):
        return "no SELECT *: name the columns"
    if lead in ("SELECT", "WITH") and not _AGGREGATE.search(stmt) and not _LIMIT.search(stmt):
        return "row-level read needs a LIMIT (default 100) or an aggregate"
    return None


def extract_sql(tool_input: dict) -> list[str]:
    """Every SQL string in a tool call. sf_batch carries a list of queries."""
    found: list[str] = []
    for key in ("sql", "query", "statement", "sql_query"):
        value = tool_input.get(key)
        if isinstance(value, str):
            found.append(value)
    for key in ("queries", "statements"):
        for item in tool_input.get(key) or []:
            if isinstance(item, str):
                found.append(item)
            elif isinstance(item, dict):
                found.extend(extract_sql(item))
    return found


# --- data-tier activation marker -------------------------------------------

DEFAULT_TTL = timedelta(hours=4)


def marker_dir() -> Path:
    home = Path(os.environ.get("DEEP_STATE_HOME") or Path.home() / ".claude")
    return home / "marketplace" / "deep-plan-enhanced" / "data-tier"


def _marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id) or "unknown"
    return marker_dir() / f"{safe}.json"


def start(session_id: str, ttl: timedelta = DEFAULT_TTL) -> Path:
    path = _marker(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    expires = datetime.now(UTC) + ttl
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"session_id": session_id, "expires_at": expires.isoformat()}))
    os.rename(tmp, path)
    return path


def stop(session_id: str) -> bool:
    path = _marker(session_id)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def is_active(session_id: str, now: datetime | None = None) -> bool:
    try:
        data = json.loads(_marker(session_id).read_text())
        expires = datetime.fromisoformat(data["expires_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return (now or datetime.now(UTC)) < expires

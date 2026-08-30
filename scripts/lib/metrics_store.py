"""Cross-session run store — the foundation for every playbook measurement.

`MetricsCollector` writes one `.deepstate/metrics.json` per session and nothing
aggregates them, so nothing can compute a trend, a baseline, or an improvement.
This is the append-only log that makes those possible.

Lives at `~/.claude/marketplace/deep-plan-enhanced/metrics/`, outside every
repo, matching the code-review skill's no-trace rule: nothing here can be
accidentally staged or need a .gitignore entry. It is not the vault — the vault
is curated human-readable knowledge, this is machine telemetry.

**What is deliberately not stored:** no file contents, no code, no prompt or
user text, no titles. Counts, rates, timestamps and identifiers only. That keeps
the privacy story short enough to actually hold.

JSONL rather than SQLite: stdlib only, greppable, and an append of a single
short line under PIPE_BUF with O_APPEND is atomic on POSIX — which matters
because two `/deep` sessions can finalize at once.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 4096
DEFAULT_MAX_RECORDS = 500
DEFAULT_MAX_AGE_DAYS = 365

# Below this, report the raw numbers and refuse to call anything a baseline.
MIN_SAMPLES_FOR_BASELINE = 8

VALID_OUTCOMES = frozenset({"complete", "abandoned", "error"})


def metrics_home() -> Path:
    """Overridable via `$DEEP_STATE_HOME` so tests never touch the real home."""
    base = Path(os.environ.get("DEEP_STATE_HOME") or Path.home() / ".claude")
    return base / "marketplace" / "deep-plan-enhanced" / "metrics"


def runs_path(store_dir: Path | None = None) -> Path:
    return (store_dir or metrics_home()) / "runs.jsonl"


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    project_slug: str
    mode: str
    started_at: str
    completed_at: str
    wall_clock_seconds: int
    outcome: str = "complete"
    plugin_version: str = ""
    schema: int = SCHEMA_VERSION
    metrics: dict = field(default_factory=dict)
    derived: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class Baseline:
    metric: str
    n: int
    center: float
    spread: float
    trustworthy: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _rate(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def derive(metrics: dict, wall_clock_seconds: int) -> dict:
    """Rates a run can be compared on. Only ratios whose denominator is present.

    A rate with a zero denominator is omitted rather than stored as 0.0, because
    "no gates ran" and "every gate failed" must not look identical downstream.
    """
    derived: dict = {}

    research_total = metrics.get("research_gate_pass", 0) + metrics.get("research_gate_fail", 0)
    bvb_total = metrics.get("build_vs_buy_gate_pass", 0) + metrics.get("build_vs_buy_gate_fail", 0)

    for name, passes, total in (
        ("research_gate_pass_rate", metrics.get("research_gate_pass", 0), research_total),
        ("build_vs_buy_gate_pass_rate", metrics.get("build_vs_buy_gate_pass", 0), bvb_total),
    ):
        value = _rate(passes, total)
        if value is not None:
            derived[name] = value

    waves = metrics.get("wave_count", 0)
    agents = metrics.get("agents_launched", 0)
    per_wave = _rate(agents, waves)
    if per_wave is not None:
        derived["agents_per_wave"] = per_wave

    if wall_clock_seconds:
        derived["wall_clock_seconds"] = wall_clock_seconds

    return derived


def build_record(
    *,
    run_id: str,
    project_slug: str,
    mode: str,
    metrics: dict,
    outcome: str = "complete",
    plugin_version: str = "",
) -> RunRecord:
    started = metrics.get("started_at", "")
    completed = metrics.get("completed_at", "")
    wall_clock = int(metrics.get("wall_clock_seconds") or 0)

    return RunRecord(
        run_id=run_id,
        project_slug=project_slug,
        mode=mode,
        started_at=started,
        completed_at=completed,
        wall_clock_seconds=wall_clock,
        outcome=outcome if outcome in VALID_OUTCOMES else "complete",
        plugin_version=plugin_version,
        metrics=dict(metrics),
        derived=derive(metrics, wall_clock),
    )


def append_run(record: RunRecord, store_dir: Path | None = None) -> bool:
    """Append one record. Best-effort: telemetry never fails a run.

    Oversized records drop the raw `metrics` blob but keep `derived`, so a
    pathological session degrades to less detail rather than to no record.
    """
    path = runs_path(store_dir)
    try:
        line = record.to_json()
        if len(line.encode()) > MAX_RECORD_BYTES:
            from dataclasses import replace

            line = replace(record, metrics={}).to_json()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False


def load_runs(
    store_dir: Path | None = None,
    *,
    project_slug: str | None = None,
    mode: str | None = None,
) -> list[dict]:
    """Read the log, skipping unparseable lines.

    A corrupt line is skipped rather than fatal — a half-written record from a
    killed process must not make the whole history unreadable.
    """
    path = runs_path(store_dir)
    if not path.exists():
        return []
    runs: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            if project_slug and record.get("project_slug") != project_slug:
                continue
            if mode and record.get("mode") != mode:
                continue
            runs.append(record)
    except OSError:
        return []
    return runs


def metric_values(runs: list[dict], metric: str) -> list[float]:
    values: list[float] = []
    for run in runs:
        raw = run.get("derived", {}).get(metric)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            values.append(float(raw))
    return values


def compute_baseline(runs: list[dict], metric: str) -> Baseline:
    """Median and MAD, not mean and standard deviation.

    A handful of runs, one of which was a disaster, would drag a mean far enough
    to make the band meaningless. Median and MAD survive that. `trustworthy` is
    False below MIN_SAMPLES_FOR_BASELINE, and callers must respect it rather
    than quietly presenting a two-sample "baseline" as fact.
    """
    values = metric_values(runs, metric)
    n = len(values)
    if n == 0:
        return Baseline(metric=metric, n=0, center=0.0, spread=0.0, trustworthy=False)

    center = median(values)
    # 1.4826 scales MAD to be comparable with a standard deviation on normal data.
    mad = median([abs(v - center) for v in values]) * 1.4826

    return Baseline(
        metric=metric,
        n=n,
        center=round(center, 4),
        spread=round(mad, 4),
        trustworthy=n >= MIN_SAMPLES_FOR_BASELINE,
    )


def prune(
    store_dir: Path | None = None,
    *,
    max_records: int = DEFAULT_MAX_RECORDS,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> int:
    """Trim the log, keeping whichever of the two limits is more generous.

    Returns the number of records dropped. Rewrites atomically.
    """
    runs = load_runs(store_dir)
    if not runs:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    def recent_enough(record: dict) -> bool:
        stamp = record.get("completed_at") or ""
        try:
            return datetime.fromisoformat(stamp) >= cutoff
        except ValueError:
            return True  # undated records are kept; dropping them loses history

    by_age = [r for r in runs if recent_enough(r)]
    by_count = runs[-max_records:]
    keep = by_age if len(by_age) >= len(by_count) else by_count

    dropped = len(runs) - len(keep)
    if dropped <= 0:
        return 0

    path = runs_path(store_dir)
    tmp = path.with_suffix(f".jsonl.{os.getpid()}.tmp")
    try:
        tmp.write_text(
            "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in keep),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        return 0
    return dropped


def summarize(runs: list[dict]) -> dict:
    """Counts and per-mode breakdown for the report dashboard."""
    by_mode: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for run in runs:
        mode = str(run.get("mode", "unknown"))
        outcome = str(run.get("outcome", "unknown"))
        by_mode[mode] = by_mode.get(mode, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

    wall = [
        float(r["wall_clock_seconds"])
        for r in runs
        if isinstance(r.get("wall_clock_seconds"), (int, float))
    ]
    return {
        "runs": len(runs),
        "by_mode": by_mode,
        "by_outcome": by_outcome,
        "median_wall_clock_seconds": round(median(wall), 1) if wall else None,
    }

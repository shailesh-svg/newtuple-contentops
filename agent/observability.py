"""Observability and run-tracking for ContentOps.

This is the telemetry backbone for the agent. Every agent invocation opens a
*run*; tool calls, token usage, provider fallbacks, quality-gate verdicts, and
review decisions are recorded as *events* hung off that run. Everything lands in
a single SQLite file so the dashboard can render pipeline + ops metrics with no
external services.

Design notes:
- Storage is SQLite (stdlib, no new dependency). WAL mode + a write lock make it
  safe for the Slack bot's worker threads.
- The "current run" is tracked with a ``contextvars.ContextVar`` so tools and the
  agent loop can record events without threading a recorder object through every
  function signature. If no run is active, recording is a silent no-op — that
  keeps unit tests and CLI one-shots free of side effects.
- All writes are best-effort: telemetry must never crash the agent. Failures are
  logged and swallowed.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from config import CONTENTOPS_DB

log = logging.getLogger(__name__)

_WRITE_LOCK = threading.Lock()
_INITIALIZED = False
_current_run: contextvars.ContextVar[Optional["Run"]] = contextvars.ContextVar(
    "contentops_current_run", default=None
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    path = Path(CONTENTOPS_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    """Create tables if they do not exist. Idempotent and cheap to call."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    try:
        with _WRITE_LOCK, _connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id        TEXT PRIMARY KEY,
                    ts_start      TEXT NOT NULL,
                    ts_end        TEXT,
                    command       TEXT,
                    user_id       TEXT,
                    provider      TEXT,
                    model         TEXT,
                    status        TEXT,
                    duration_ms   INTEGER,
                    tool_calls    INTEGER DEFAULT 0,
                    input_tokens  INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    error         TEXT,
                    summary       TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id      TEXT,
                    ts          TEXT NOT NULL,
                    kind        TEXT NOT NULL,
                    name        TEXT,
                    ok          INTEGER,
                    duration_ms INTEGER,
                    detail      TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_events_run  ON events(run_id);
                CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, ts);
                CREATE INDEX IF NOT EXISTS idx_runs_start  ON runs(ts_start);
                """
            )
        _INITIALIZED = True
    except Exception as e:  # pragma: no cover - telemetry must not crash callers
        log.warning("observability: init_db failed: %s", e)


class Run:
    """A single agent invocation. Accumulates counters, flushes on finish()."""

    def __init__(self, command: str, user_id: str = "", provider: str = "", model: str = "") -> None:
        self.run_id = uuid.uuid4().hex[:12]
        self.command = command
        self.user_id = user_id
        self.provider = provider
        self.model = model
        self.ts_start = _now()
        self._start_perf = datetime.now(timezone.utc)
        self.tool_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._finished = False
        self._persist_start()

    def _persist_start(self) -> None:
        _write(
            "INSERT OR REPLACE INTO runs "
            "(run_id, ts_start, command, user_id, provider, model, status) "
            "VALUES (?,?,?,?,?,?,?)",
            (self.run_id, self.ts_start, self.command, self.user_id,
             self.provider, self.model, "running"),
        )

    def set_provider(self, provider: str, model: str = "") -> None:
        self.provider = provider or self.provider
        if model:
            self.model = model
        _write(
            "UPDATE runs SET provider=?, model=? WHERE run_id=?",
            (self.provider, self.model, self.run_id),
        )

    def add_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.input_tokens += int(input_tokens or 0)
        self.output_tokens += int(output_tokens or 0)

    def record_event(
        self,
        kind: str,
        name: str = "",
        ok: bool = True,
        detail: Any = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        if kind == "tool_call":
            self.tool_calls += 1
        _write(
            "INSERT INTO events (run_id, ts, kind, name, ok, duration_ms, detail) "
            "VALUES (?,?,?,?,?,?,?)",
            (self.run_id, _now(), kind, name, 1 if ok else 0, duration_ms,
             _to_json(detail)),
        )

    def finish(self, status: str = "success", summary: str = "", error: str = "") -> None:
        if self._finished:
            return
        self._finished = True
        duration_ms = int(
            (datetime.now(timezone.utc) - self._start_perf).total_seconds() * 1000
        )
        _write(
            "UPDATE runs SET ts_end=?, status=?, duration_ms=?, tool_calls=?, "
            "input_tokens=?, output_tokens=?, error=?, summary=? WHERE run_id=?",
            (_now(), status, duration_ms, self.tool_calls, self.input_tokens,
             self.output_tokens, error[:2000] if error else None,
             summary[:500] if summary else None, self.run_id),
        )


def _to_json(detail: Any) -> Optional[str]:
    if detail is None:
        return None
    try:
        return json.dumps(detail, default=str)[:4000]
    except Exception:
        return str(detail)[:4000]


def _write(sql: str, params: tuple) -> None:
    """Best-effort write — telemetry failures never propagate."""
    init_db()
    try:
        with _WRITE_LOCK, _connect() as conn:
            conn.execute(sql, params)
    except Exception as e:  # pragma: no cover
        log.debug("observability: write failed: %s", e)


# ─── Public recording API (no-ops when no run is active) ──────────────────────

@contextmanager
def start_run(command: str, user_id: str = "", provider: str = "", model: str = "") -> Iterator[Run]:
    """Context manager that opens a run, sets it as current, and finalizes it.

    On an unhandled exception the run is marked ``error`` and the exception is
    re-raised so callers still see failures.
    """
    run = Run(command=command, user_id=user_id, provider=provider, model=model)
    token = _current_run.set(run)
    try:
        yield run
        run.finish(status="success")
    except Exception as e:
        run.finish(status="error", error=f"{type(e).__name__}: {e}")
        raise
    finally:
        _current_run.reset(token)


def current_run() -> Optional[Run]:
    return _current_run.get()


def record_event(
    kind: str,
    name: str = "",
    ok: bool = True,
    detail: Any = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Record an event against the active run, if any."""
    run = _current_run.get()
    if run is not None:
        run.record_event(kind, name=name, ok=ok, detail=detail, duration_ms=duration_ms)


def add_tokens(input_tokens: int = 0, output_tokens: int = 0) -> None:
    run = _current_run.get()
    if run is not None:
        run.add_tokens(input_tokens, output_tokens)


def set_provider(provider: str, model: str = "") -> None:
    run = _current_run.get()
    if run is not None:
        run.set_provider(provider, model)


def record_approval(idea_id: str, status: str, reviewer: str, source: str) -> None:
    """Approval/review decisions are recorded as standalone events (outside a run)."""
    _write(
        "INSERT INTO events (run_id, ts, kind, name, ok, detail) VALUES (?,?,?,?,?,?)",
        (None, _now(), "approval", status, 1,
         _to_json({"idea_id": idea_id, "reviewer": reviewer, "source": source})),
    )


# ─── Read API (used by the dashboard) ─────────────────────────────────────────

def _query(sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    init_db()
    try:
        with _connect() as conn:
            return list(conn.execute(sql, params).fetchall())
    except Exception as e:  # pragma: no cover
        log.debug("observability: query failed: %s", e)
        return []


def recent_runs(limit: int = 25) -> List[Dict[str, Any]]:
    rows = _query(
        "SELECT * FROM runs ORDER BY ts_start DESC LIMIT ?", (limit,)
    )
    return [dict(r) for r in rows]


def recent_events(kind: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    if kind:
        rows = _query(
            "SELECT * FROM events WHERE kind=? ORDER BY id DESC LIMIT ?", (kind, limit)
        )
    else:
        rows = _query("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
    out = []
    for r in rows:
        d = dict(r)
        if d.get("detail"):
            try:
                d["detail"] = json.loads(d["detail"])
            except Exception:
                pass
        out.append(d)
    return out


def ops_metrics(window_hours: int = 168) -> Dict[str, Any]:
    """Aggregate operational metrics for the dashboard (default: last 7 days)."""
    init_db()
    cutoff = _cutoff(window_hours)

    runs = _query("SELECT * FROM runs WHERE ts_start >= ?", (cutoff,))
    total = len(runs)
    errors = sum(1 for r in runs if r["status"] == "error")
    blocked = sum(1 for r in runs if r["status"] == "gate_blocked")
    durations = [r["duration_ms"] for r in runs if r["duration_ms"] is not None]
    out_tokens = sum(r["output_tokens"] or 0 for r in runs)
    in_tokens = sum(r["input_tokens"] or 0 for r in runs)

    gate_events = _query(
        "SELECT ok FROM events WHERE kind='gate' AND ts >= ?", (cutoff,)
    )
    gate_total = len(gate_events)
    gate_pass = sum(1 for e in gate_events if e["ok"] == 1)

    tool_events = _query(
        "SELECT name, ok FROM events WHERE kind='tool_call' AND ts >= ?", (cutoff,)
    )
    tool_total = len(tool_events)
    tool_fail = sum(1 for e in tool_events if e["ok"] == 0)

    fallbacks = _query(
        "SELECT COUNT(*) AS c FROM events WHERE kind='provider_fallback' AND ts >= ?",
        (cutoff,),
    )
    fallback_count = fallbacks[0]["c"] if fallbacks else 0

    return {
        "window_hours": window_hours,
        "runs_total": total,
        "runs_error": errors,
        "runs_gate_blocked": blocked,
        "run_success_rate": _rate(total - errors, total),
        "avg_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
        "p95_duration_ms": _percentile(durations, 95),
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "gate_total": gate_total,
        "gate_pass": gate_pass,
        "gate_pass_rate": _rate(gate_pass, gate_total),
        "tool_calls": tool_total,
        "tool_failures": tool_fail,
        "tool_failure_rate": _rate(tool_fail, tool_total),
        "provider_fallbacks": fallback_count,
    }


def gate_violation_breakdown(window_hours: int = 168) -> List[Dict[str, Any]]:
    """Count which gate rules fail most often — drives the dashboard's gate panel."""
    cutoff = _cutoff(window_hours)
    rows = _query(
        "SELECT detail FROM events WHERE kind='gate' AND ok=0 AND ts >= ?", (cutoff,)
    )
    counts: Dict[str, int] = {}
    for r in rows:
        try:
            detail = json.loads(r["detail"] or "{}")
        except Exception:
            continue
        for v in detail.get("violations", []):
            rule = v.get("rule", "unknown") if isinstance(v, dict) else str(v)
            counts[rule] = counts.get(rule, 0) + 1
    return sorted(
        ({"rule": k, "count": v} for k, v in counts.items()),
        key=lambda x: x["count"],
        reverse=True,
    )


def _cutoff(window_hours: int) -> str:
    from datetime import timedelta

    return (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()


def _rate(num: int, denom: int) -> float:
    return round(100.0 * num / denom, 1) if denom else 0.0


def _percentile(values: List[int], pct: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[k]

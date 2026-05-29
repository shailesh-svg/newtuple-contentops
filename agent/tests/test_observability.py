import observability as o
import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the telemetry store at a throwaway SQLite file per test."""
    db = tmp_path / "ops.db"
    monkeypatch.setattr(o, "CONTENTOPS_DB", str(db))
    monkeypatch.setattr(o, "_INITIALIZED", False)
    yield db


def test_run_lifecycle_records_metrics(fresh_db):
    with o.start_run("draft-from-idea", user_id="U1") as run:
        o.set_provider("claude", "claude-opus-4-7")
        run.record_event("tool_call", name="read_tracker", ok=True, duration_ms=100)
        run.record_event("tool_call", name="post_to_slack", ok=False, duration_ms=50)
        o.add_tokens(200, 80)

    runs = o.recent_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "success"
    assert runs[0]["provider"] == "claude"
    assert runs[0]["tool_calls"] == 2
    assert runs[0]["output_tokens"] == 80

    metrics = o.ops_metrics()
    assert metrics["runs_total"] == 1
    assert metrics["tool_calls"] == 2
    assert metrics["tool_failures"] == 1


def test_failed_run_marked_error(fresh_db):
    with pytest.raises(ValueError):
        with o.start_run("plan-week"):
            raise ValueError("boom")
    runs = o.recent_runs()
    assert runs[0]["status"] == "error"
    assert "boom" in (runs[0]["error"] or "")


def test_gate_pass_rate_and_violation_breakdown(fresh_db):
    with o.start_run("draft-from-idea"):
        o.record_event("gate", name="A", ok=True)
        o.record_event(
            "gate", name="B", ok=False,
            detail={"violations": [{"rule": "banned_phrase"}, {"rule": "bucket_missing"}]},
        )
    metrics = o.ops_metrics()
    assert metrics["gate_total"] == 2
    assert metrics["gate_pass"] == 1
    assert metrics["gate_pass_rate"] == 50.0

    breakdown = {v["rule"]: v["count"] for v in o.gate_violation_breakdown()}
    assert breakdown["banned_phrase"] == 1
    assert breakdown["bucket_missing"] == 1


def test_record_event_without_run_is_noop(fresh_db):
    # No active run — must not raise and must not create rows.
    o.record_event("tool_call", name="x")
    assert o.recent_runs() == []


def test_record_approval(fresh_db):
    o.record_approval("CNT-1", "Approved", "U9", "slack")
    approvals = o.recent_events(kind="approval")
    assert len(approvals) == 1
    assert approvals[0]["name"] == "Approved"
    assert approvals[0]["detail"]["idea_id"] == "CNT-1"

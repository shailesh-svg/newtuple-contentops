import pytest
import review_service as rs
from identity import Principal


def _principal(role, perms):
    return Principal(id=role + "-user", display_name=role.title(), platform="test",
                     role=role, permissions=frozenset(perms), strict=True)


REVIEWER = _principal("reviewer", {"approve", "revise", "reject", "help"})
VIEWER = _principal("viewer", {"help", "whoami"})
EDITOR = _principal("editor", {"edit", "draft-from-idea"})


@pytest.fixture(autouse=True)
def _capture(monkeypatch):
    """Capture tracker writes + audit calls instead of hitting real systems."""
    calls = {"write": [], "approval": [], "event": []}
    monkeypatch.setattr(rs, "write_tracker",
                        lambda cid, fields: calls["write"].append((cid, fields)) or {"updated": cid})
    monkeypatch.setattr(rs.observability, "record_approval",
                        lambda *a, **k: calls["approval"].append((a, k)))
    monkeypatch.setattr(rs.observability, "record_event",
                        lambda *a, **k: calls["event"].append((a, k)))
    return calls


def test_reviewer_can_approve(_capture):
    res = rs.decide(REVIEWER, "CNT-1", "approve", source="slack")
    assert res.ok and res.status == "Approved"
    cid, fields = _capture["write"][0]
    assert cid == "CNT-1"
    assert fields["status"] == "Approved"
    assert fields["reviewer"] == "reviewer-user"
    assert "review_action_ts" in fields
    assert len(_capture["approval"]) == 1  # audit recorded


def test_revise_carries_notes(_capture):
    res = rs.decide(REVIEWER, "CNT-2", "revise", notes="tighten the hook")
    assert res.ok and res.status == "Needs Revision"
    assert _capture["write"][0][1]["review_notes"] == "tighten the hook"


def test_viewer_cannot_approve(_capture):
    res = rs.decide(VIEWER, "CNT-1", "approve")
    assert not res.ok and res.unauthorized
    assert _capture["write"] == []        # nothing written
    assert _capture["approval"] == []


def test_unknown_decision_rejected(_capture):
    res = rs.decide(REVIEWER, "CNT-1", "yolo")
    assert not res.ok and "Unknown decision" in res.error
    assert _capture["write"] == []


def test_missing_content_id(_capture):
    res = rs.decide(REVIEWER, "", "approve")
    assert not res.ok and not res.unauthorized and "content id" in res.error.lower()


def test_tracker_error_propagates(monkeypatch, _capture):
    monkeypatch.setattr(rs, "write_tracker", lambda cid, fields: {"error": "boom"})
    res = rs.decide(REVIEWER, "CNT-1", "approve")
    assert not res.ok and res.error == "boom"
    assert _capture["approval"] == []     # no audit on failure


def test_editor_can_edit_others_cannot(_capture):
    ok = rs.edit(EDITOR, "CNT-1", {"Working Title / Hook": "New"})
    assert ok.ok
    assert _capture["write"][0] == ("CNT-1", {"Working Title / Hook": "New"})
    assert len(_capture["event"]) == 1

    denied = rs.edit(VIEWER, "CNT-1", {"Working Title / Hook": "New"})
    assert not denied.ok and denied.unauthorized

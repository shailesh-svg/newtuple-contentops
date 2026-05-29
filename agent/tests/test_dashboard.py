import authz
import dashboard
import review_service
from tools import sheets

ROW = {
    "Content ID": "CNT-1", "Working Title / Hook": "Reliability beats demos",
    "Status": "Needs Review", "Bucket": "Workflow Wins", "Draft Text": "body text",
}


def _login(client, uid):
    with client.session_transaction() as s:
        s["uid"] = uid
        s["platform"] = "slack"
        s["display_name"] = uid
        s["csrf"] = "testcsrf"


def _roles(monkeypatch, mapping):
    monkeypatch.setattr(authz.AUTHZ, "strict", True)
    monkeypatch.setattr(authz.AUTHZ, "identities", {})
    monkeypatch.setattr(authz.AUTHZ, "user_roles", mapping)
    # Reset to built-in role permissions so a local authz.yaml can't shadow them.
    monkeypatch.setattr(authz.AUTHZ, "role_permissions",
                        {r: set(p) for r, p in authz.DEFAULT_ROLE_PERMISSIONS.items()})


def _stub_tracker(monkeypatch):
    monkeypatch.setattr(sheets, "read_tracker", lambda **k: {"rows": [ROW], "count": 1})


def _capture_writes(monkeypatch):
    writes = []
    monkeypatch.setattr(review_service, "write_tracker",
                        lambda cid, fields: writes.append((cid, fields)) or {"updated": cid})
    monkeypatch.setattr(review_service.observability, "record_approval", lambda *a, **k: None)
    monkeypatch.setattr(review_service.observability, "record_event", lambda *a, **k: None)
    return writes


def _client():
    dashboard.app.config["TESTING"] = True
    return dashboard.app.test_client()


def test_unauthenticated_redirects_to_login():
    c = _client()
    r = c.get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_healthz_is_open():
    assert _client().get("/healthz").status_code == 200


def test_authed_overview_renders(monkeypatch):
    _roles(monkeypatch, {"alice": "viewer"})
    _stub_tracker(monkeypatch)
    c = _client()
    _login(c, "alice")
    r = c.get("/")
    assert r.status_code == 200
    assert b"ContentOps" in r.data and b"CNT-1" in r.data


def test_viewer_cannot_approve(monkeypatch):
    _roles(monkeypatch, {"alice": "viewer"})
    _stub_tracker(monkeypatch)
    writes = _capture_writes(monkeypatch)
    c = _client()
    _login(c, "alice")
    r = c.post("/item/CNT-1/decide", data={"csrf": "testcsrf", "decision": "approve"})
    assert r.status_code == 302          # redirect back with a flash
    assert writes == []                  # RBAC blocked the write


def test_reviewer_can_approve_through_review_service(monkeypatch):
    _roles(monkeypatch, {"bob": "reviewer"})
    _stub_tracker(monkeypatch)
    writes = _capture_writes(monkeypatch)
    c = _client()
    _login(c, "bob")
    r = c.post("/item/CNT-1/decide", data={"csrf": "testcsrf", "decision": "approve"})
    assert r.status_code == 302
    assert len(writes) == 1
    cid, fields = writes[0]
    assert cid == "CNT-1" and fields["status"] == "Approved" and fields["reviewer"] == "bob"


def test_csrf_required_on_decide(monkeypatch):
    _roles(monkeypatch, {"bob": "reviewer"})
    _stub_tracker(monkeypatch)
    _capture_writes(monkeypatch)
    c = _client()
    _login(c, "bob")
    r = c.post("/item/CNT-1/decide", data={"decision": "approve"})  # no csrf
    assert r.status_code == 400


def test_editor_can_edit_viewer_cannot(monkeypatch):
    _stub_tracker(monkeypatch)
    writes = _capture_writes(monkeypatch)

    _roles(monkeypatch, {"ed": "editor"})
    c = _client()
    _login(c, "ed")
    r = c.post("/item/CNT-1/edit",
               data={"csrf": "testcsrf", "title": "New title",
                     "bucket": "Workflow Wins", "key_message": "", "draft_text": "body text"})
    assert r.status_code == 302
    assert writes and writes[0][0] == "CNT-1"

    writes.clear()
    _roles(monkeypatch, {"vi": "viewer"})
    c2 = _client()
    _login(c2, "vi")
    c2.post("/item/CNT-1/edit", data={"csrf": "testcsrf", "title": "Nope",
                                      "bucket": "Workflow Wins", "key_message": "", "draft_text": "body text"})
    assert writes == []                  # viewer edit blocked


def test_dev_login_sets_session(monkeypatch):
    monkeypatch.setattr(dashboard, "_dev_login_enabled", lambda: True)
    monkeypatch.setattr(dashboard, "DASHBOARD_TOKEN", "")
    c = _client()
    r = c.post("/login", data={"user_id": "U999", "display_name": "Zed"})
    assert r.status_code == 302
    with c.session_transaction() as s:
        assert s["uid"] == "U999"

import pytest
import schema
from tools import tracker_backends as tb
from tools.tracker_backends import JsonFileBackend, get_backend, resolve_backend_name


@pytest.fixture
def json_backend(tmp_path):
    return JsonFileBackend(path=str(tmp_path / "tracker.json"))


def test_jsonfile_upsert_read_update_roundtrip(json_backend):
    row = schema.build_create_row(
        {"idea_id": "CNT-1", "title": "Hook", "bucket": "Workflow Wins",
         "raw_input": "body", "status": "needs_review"}
    )
    assert json_backend.upsert(row)["appended"] == "CNT-1"

    read = json_backend.read(None, 30)
    assert read["count"] == 1
    assert read["rows"][0]["Content ID"] == "CNT-1"

    # Status filter
    assert json_backend.read("Needs Review", 30)["count"] == 1
    assert json_backend.read("Approved", 30)["count"] == 0

    # Update existing
    res = json_backend.update("CNT-1", {"Status": "Approved", "Approved By": "U9"})
    assert res["updated"] == "CNT-1"
    assert json_backend.read("Approved", 30)["rows"][0]["Approved By"] == "U9"


def test_jsonfile_update_missing_id_errors(json_backend):
    assert "error" in json_backend.update("NOPE", {"Status": "Approved"})


def test_jsonfile_upsert_is_idempotent_on_same_id(json_backend):
    row = schema.build_create_row({"idea_id": "CNT-9", "title": "A", "bucket": "Founder Notes", "raw_input": "x"})
    json_backend.upsert(row)
    json_backend.upsert(row)
    assert json_backend.read(None, 30)["count"] == 1


def test_backend_resolution_prefers_explicit_then_legacy(monkeypatch):
    monkeypatch.setattr(tb, "TRACKER_BACKEND", "jsonfile")
    assert resolve_backend_name() == "jsonfile"

    monkeypatch.setattr(tb, "TRACKER_BACKEND", "")
    monkeypatch.setattr(tb, "GOOGLE_AUTH_MODE", "apps_script")
    assert resolve_backend_name() == "apps_script"

    monkeypatch.setattr(tb, "GOOGLE_AUTH_MODE", "service_account")
    assert resolve_backend_name() == "sheets"


def test_get_backend_returns_instance(monkeypatch):
    monkeypatch.setattr(tb, "TRACKER_BACKEND", "jsonfile")
    assert isinstance(get_backend(), JsonFileBackend)


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setattr(tb, "TRACKER_BACKEND", "nope")
    with pytest.raises(ValueError):
        get_backend()

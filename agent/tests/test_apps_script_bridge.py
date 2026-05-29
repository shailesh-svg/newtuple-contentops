import apps_script_bridge
import pytest
import requests
from apps_script_bridge import AppsScriptBridge


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"status {self.status_code}")
            err.response = self
            raise err

    def json(self):
        return self.payload


def test_bridge_sends_token_action_and_sheet_context(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"ok": True, "data": {"status": "ok"}})

    monkeypatch.setattr("apps_script_bridge.requests.post", fake_post)

    bridge = AppsScriptBridge("https://script.example/exec", "token", "sheet-id", "Content Tracker")
    result = bridge.health()

    assert result == {"status": "ok"}
    assert calls[0]["url"] == "https://script.example/exec"
    assert calls[0]["json"]["token"] == "token"
    assert calls[0]["json"]["action"] == "health"
    assert calls[0]["json"]["sheetId"] == "sheet-id"
    assert calls[0]["json"]["sheetName"] == "Content Tracker"


def test_bridge_returns_apps_script_errors(monkeypatch):
    def fake_post(url, json, timeout):
        return FakeResponse({"ok": False, "error": "Unauthorized"})

    monkeypatch.setattr("apps_script_bridge.requests.post", fake_post)

    bridge = AppsScriptBridge("https://script.example/exec", "bad", "sheet-id", "Content Tracker")

    assert bridge.health() == {"error": "Unauthorized"}


def test_bridge_retries_transient_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr(apps_script_bridge.time, "sleep", lambda *_: None)  # no real waiting
    attempts = []

    def fake_post(url, json, timeout):
        attempts.append(1)
        if len(attempts) < 3:
            return FakeResponse({"ok": False}, status_code=503)  # transient
        return FakeResponse({"ok": True, "data": {"status": "ok"}})

    monkeypatch.setattr("apps_script_bridge.requests.post", fake_post)
    bridge = AppsScriptBridge("https://script.example/exec", "t", "s", "Content Tracker")

    assert bridge.health() == {"status": "ok"}
    assert len(attempts) == 3  # retried twice before success


def test_bridge_does_not_retry_4xx(monkeypatch):
    monkeypatch.setattr(apps_script_bridge.time, "sleep", lambda *_: None)
    attempts = []

    def fake_post(url, json, timeout):
        attempts.append(1)
        return FakeResponse({"ok": False, "error": "bad request"}, status_code=400)

    monkeypatch.setattr("apps_script_bridge.requests.post", fake_post)
    bridge = AppsScriptBridge("https://script.example/exec", "t", "s", "Content Tracker")

    with pytest.raises(requests.HTTPError):
        bridge.health()
    assert len(attempts) == 1  # client errors are not retried


def test_bridge_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(apps_script_bridge.time, "sleep", lambda *_: None)
    attempts = []

    def fake_post(url, json, timeout):
        attempts.append(1)
        raise requests.ConnectionError("boom")

    monkeypatch.setattr("apps_script_bridge.requests.post", fake_post)
    bridge = AppsScriptBridge("https://script.example/exec", "t", "s", "Content Tracker")

    with pytest.raises(requests.ConnectionError):
        bridge.health()
    assert len(attempts) == apps_script_bridge._MAX_ATTEMPTS

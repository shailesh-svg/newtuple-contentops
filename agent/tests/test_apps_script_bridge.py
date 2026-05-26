from apps_script_bridge import AppsScriptBridge


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

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

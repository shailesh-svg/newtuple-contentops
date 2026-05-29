"""Logic-level coverage for the Google backends using fakes (no live creds).

These exercise the parsing / header-detection / row-finding / batched-write /
upsert-vs-update branches that the live integration cannot in CI.
"""

import schema
from tools.tracker_backends import AppsScriptBackend, SheetsBackend

HEADERS = ["Content ID", "Status", "Bucket", "Working Title / Hook"]
GRID = [
    ["My Content Tracker"],                                   # title row (not header)
    HEADERS,                                                  # header row (index 1 → sheet row 2)
    ["CNT-1", "Idea", "Workflow Wins", "Hook one"],          # sheet row 3
    ["CNT-2", "Needs Review", "Founder Notes", "Hook two"],  # sheet row 4
]


# ─── Fake Google Sheets service ───────────────────────────────────────────────

class _Req:
    def __init__(self, result):
        self._result = result

    def execute(self, num_retries=0):
        return self._result


class _Values:
    def __init__(self, store):
        self.store = store

    def get(self, spreadsheetId, range):
        return _Req({"values": self.store["grid"]})

    def batchUpdate(self, spreadsheetId, body):
        self.store["batch"].append(body)
        return _Req({})

    def append(self, spreadsheetId, range, valueInputOption, insertDataOption, body):
        self.store["append"].append(body)
        return _Req({})


class _Spreadsheets:
    def __init__(self, store):
        self._values = _Values(store)

    def values(self):
        return self._values


class FakeService:
    def __init__(self, grid):
        self.store = {"grid": grid, "batch": [], "append": []}

    def spreadsheets(self):
        return _Spreadsheets(self.store)


def _sheets_backend(grid):
    backend = SheetsBackend()
    fake = FakeService([list(r) for r in grid])
    backend._service = lambda: fake
    return backend, fake


def test_sheets_read_detects_header_below_title_row():
    backend, _ = _sheets_backend(GRID)
    out = backend.read(None, 30)
    assert out["count"] == 2
    assert out["rows"][0]["Content ID"] == "CNT-1"
    assert out["rows"][0]["Working Title / Hook"] == "Hook one"


def test_sheets_read_status_filter():
    backend, _ = _sheets_backend(GRID)
    out = backend.read("Needs Review", 30)
    assert out["count"] == 1
    assert out["rows"][0]["Content ID"] == "CNT-2"


def test_sheets_update_batches_known_fields_to_correct_cells():
    backend, fake = _sheets_backend(GRID)
    res = backend.update("CNT-1", {"Status": "Approved", "Unknown Col": "x"})
    assert res["updated"] == "CNT-1"
    assert res["fields"] == ["Status"]            # unknown column dropped
    assert len(fake.store["batch"]) == 1          # ONE batched call, not per-field
    data = fake.store["batch"][0]["data"]
    assert data[0]["range"].endswith("!B3")       # Status col (B), CNT-1 row (3)
    assert data[0]["values"] == [["Approved"]]


def test_sheets_update_missing_id_errors():
    backend, fake = _sheets_backend(GRID)
    res = backend.update("NOPE", {"Status": "Approved"})
    assert "error" in res
    assert fake.store["batch"] == []


def test_sheets_upsert_existing_id_updates_in_place():
    backend, fake = _sheets_backend(GRID)
    row = {"Content ID": "CNT-2", "Status": "Approved"}
    res = backend.upsert(row)
    assert res["updated"] == "CNT-2"
    assert fake.store["append"] == []             # no append — updated in place
    assert len(fake.store["batch"]) == 1


def test_sheets_upsert_new_id_appends_row_in_header_order():
    backend, fake = _sheets_backend(GRID)
    row = schema.build_create_row(
        {"idea_id": "CNT-9", "title": "New hook", "bucket": "Workflow Wins", "raw_input": "body"}
    )
    res = backend.upsert(row)
    assert res["appended"] == "CNT-9"
    assert len(fake.store["append"]) == 1
    values = fake.store["append"][0]["values"][0]
    # Values are aligned to the sheet's header order.
    assert values[HEADERS.index("Content ID")] == "CNT-9"
    assert values[HEADERS.index("Working Title / Hook")] == "New hook"


def test_sheets_missing_header_errors():
    backend, _ = _sheets_backend([["no"], ["headers"], ["here"]])
    assert "error" in backend.read(None, 30)


# ─── Fake Apps Script bridge ──────────────────────────────────────────────────

class FakeBridge:
    def __init__(self, upsert_result=None):
        self.calls = []
        self._upsert_result = upsert_result or {"status": "appended"}

    def read_tracker(self, status, limit):
        self.calls.append(("read_tracker", status, limit))
        return {"rows": [], "count": 0}

    def write_tracker(self, content_id, fields):
        self.calls.append(("write_tracker", content_id, fields))
        return {"updated": content_id}

    def upsert_tracker_row(self, row):
        self.calls.append(("upsert_tracker_row", row))
        return self._upsert_result

    def call(self, action, payload):
        self.calls.append((action, payload))
        return {"status": "appended"}

    def get_schema(self):
        return {"columns": {}}


def _appscript_backend(bridge):
    backend = AppsScriptBackend()
    backend._bridge = lambda: bridge
    return backend


def test_appscript_delegates_read_and_update():
    bridge = FakeBridge()
    backend = _appscript_backend(bridge)
    backend.read("Approved", 10)
    backend.update("CNT-1", {"Status": "Approved"})
    assert bridge.calls[0] == ("read_tracker", "Approved", 10)
    assert bridge.calls[1] == ("write_tracker", "CNT-1", {"Status": "Approved"})


def test_appscript_upsert_uses_modern_action():
    bridge = FakeBridge(upsert_result={"status": "appended"})
    backend = _appscript_backend(bridge)
    backend.upsert({"Content ID": "CNT-1", "Working Title / Hook": "H"})
    assert bridge.calls[0][0] == "upsert_tracker_row"


def test_appscript_upsert_falls_back_to_legacy_action():
    # Older deployed scripts don't know upsert_tracker_row.
    bridge = FakeBridge(upsert_result={"error": "Unknown action: upsert_tracker_row"})
    backend = _appscript_backend(bridge)
    backend.upsert({"Content ID": "CNT-1", "Working Title / Hook": "H", "Bucket": "Founder Notes"})
    actions = [c[0] for c in bridge.calls]
    assert actions == ["upsert_tracker_row", "append_idea"]

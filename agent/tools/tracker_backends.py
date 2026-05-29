"""Pluggable storage backends for the content tracker.

The agent talks to the tracker through a single `TrackerBackend` interface, so
the underlying system (Google Sheets, Apps Script bridge, a local JSON file, or
anything you add next — Notion, Airtable, Postgres) is swappable without
touching the agent, tools, or prompts.

All backends speak the **canonical schema** (see agent/schema.py): they receive
and return dicts keyed by canonical column names. Alias/status normalisation and
create-row construction happen once in the facade (tools/sheets.py) before the
backend is called, so backends only do I/O.

Add a backend in 3 steps:
  1. Implement a class with read / update / upsert / get_schema.
  2. Register it in `_BACKENDS`.
  3. Set TRACKER_BACKEND=<name>.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

sys.path.insert(0, str(Path(__file__).parent.parent))
import schema
from apps_script_bridge import AppsScriptBridge
from config import (
    CONTENTOPS_SHEET_ID,
    CONTENTOPS_SHEET_NAME,
    GOOGLE_APPS_SCRIPT_TOKEN,
    GOOGLE_APPS_SCRIPT_URL,
    GOOGLE_AUTH_MODE,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    TRACKER_BACKEND,
    TRACKER_JSON_FILE,
)


class TrackerBackend(Protocol):
    """Storage contract. Inputs/outputs use canonical schema column names."""

    def read(self, status: Optional[str], limit: int) -> Dict[str, Any]: ...
    def update(self, content_id: str, fields: Dict[str, Any]) -> Dict[str, Any]: ...
    def upsert(self, row: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_schema(self) -> Dict[str, Any]: ...


def _col_letter(index: int) -> str:
    """Convert a 0-based column index to a spreadsheet letter (A, B, … Z, AA…)."""
    result = ""
    while index >= 0:
        result = chr(index % 26 + ord("A")) + result
        index = index // 26 - 1
    return result


# ─── Google Sheets (service account) ──────────────────────────────────────────

class SheetsBackend:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    # googleapiclient retries transient 429/5xx with exponential backoff when
    # execute(num_retries=...) is set — production-grade resilience for free.
    NUM_RETRIES = 4

    def _service(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE, scopes=self.SCOPES
        )
        return build("sheets", "v4", credentials=creds)

    def _rows(self, service):
        result = (
            service.spreadsheets().values()
            .get(spreadsheetId=CONTENTOPS_SHEET_ID, range=CONTENTOPS_SHEET_NAME)
            .execute(num_retries=self.NUM_RETRIES)
        )
        rows = result.get("values", [])
        header_index = next((i for i, r in enumerate(rows) if schema.is_header_row(r)), -1)
        return rows, header_index

    def read(self, status, limit):
        try:
            service = self._service()
            rows, header_index = self._rows(service)
            if header_index < 0:
                return {"error": "Tracker header row not found"}
            headers = rows[header_index]
            data = [dict(zip(headers, row)) for row in rows[header_index + 1:]]
            if status:
                data = [r for r in data if str(r.get("Status", "")).lower() == status.lower()]
            return {"rows": data[:limit], "count": len(data)}
        except Exception as e:
            return {"error": str(e)}

    def update(self, content_id, fields):
        try:
            service = self._service()
            rows, header_index = self._rows(service)
            if header_index < 0:
                return {"error": "Tracker header row not found"}
            headers = rows[header_index]
            pk = schema.primary_key()
            if pk not in headers:
                return {"error": f"{pk} column not found in tracker"}
            id_col = headers.index(pk)
            target_row = None
            for i, row in enumerate(rows[header_index + 1:], start=header_index + 2):
                if len(row) > id_col and row[id_col] == content_id:
                    target_row = i
                    break
            if not target_row:
                return {"error": f"{pk} {content_id} not found"}

            # One batched write instead of one API call per field: fewer round
            # trips, friendlier to rate limits, closer to atomic.
            applied = [f for f in fields if f in headers]
            data = [
                {
                    "range": f"{CONTENTOPS_SHEET_NAME}!{_col_letter(headers.index(field))}{target_row}",
                    "values": [[fields[field]]],
                }
                for field in applied
            ]
            if data:
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=CONTENTOPS_SHEET_ID,
                    body={"valueInputOption": "RAW", "data": data},
                ).execute(num_retries=self.NUM_RETRIES)
            return {"updated": content_id, "fields": applied}
        except Exception as e:
            return {"error": str(e)}

    def upsert(self, row):
        try:
            service = self._service()
            rows, header_index = self._rows(service)
            if header_index < 0:
                return {"error": "Tracker header row not found"}
            headers = rows[header_index]
            pk = schema.primary_key()
            content_id = row.get(pk, "")
            # Update in place if the Content ID already exists.
            if pk in headers:
                id_col = headers.index(pk)
                for i, existing in enumerate(rows[header_index + 1:], start=header_index + 2):
                    if len(existing) > id_col and existing[id_col] == content_id:
                        return self.update(content_id, {k: v for k, v in row.items() if v != ""})
            values = [row.get(h, "") for h in headers]
            service.spreadsheets().values().append(
                spreadsheetId=CONTENTOPS_SHEET_ID,
                range=CONTENTOPS_SHEET_NAME,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            ).execute(num_retries=self.NUM_RETRIES)
            return {"appended": content_id, "title": row.get("Working Title / Hook", "")}
        except Exception as e:
            return {"error": str(e)}

    def get_schema(self):
        return {"backend": "sheets", "version": schema.schema_version(),
                "columns": schema.column_names()}


# ─── Apps Script bridge ───────────────────────────────────────────────────────

class AppsScriptBackend:
    def _bridge(self) -> AppsScriptBridge:
        return AppsScriptBridge(
            GOOGLE_APPS_SCRIPT_URL, GOOGLE_APPS_SCRIPT_TOKEN,
            CONTENTOPS_SHEET_ID, CONTENTOPS_SHEET_NAME,
        )

    def read(self, status, limit):
        return self._bridge().read_tracker(status=status, limit=limit)

    def update(self, content_id, fields):
        return self._bridge().write_tracker(content_id, fields)

    def upsert(self, row):
        bridge = self._bridge()
        result = bridge.upsert_tracker_row(row)
        # Fall back to the legacy append_idea action on older deployed scripts.
        if isinstance(result, dict) and "Unknown action" in result.get("error", ""):
            result = bridge.call("append_idea", {
                "content_id": row.get("Content ID", ""),
                "idea_id": row.get("Content ID", ""),
                "title": row.get("Working Title / Hook", ""),
                "bucket": row.get("Bucket", ""),
                "raw_input": row.get("Key Message", ""),
                "source_type": row.get("Series Theme", "manual"),
                "status": row.get("Status", "Idea"),
            })
        return result

    def get_schema(self):
        return self._bridge().get_schema()


# ─── Local JSON file (no credentials — dev / test / demos) ─────────────────────

class JsonFileBackend:
    """A fully-working tracker backed by a local JSON file.

    Proves the plug-and-play contract and gives a zero-credential mode for tests
    and demos. Rows are dicts keyed by canonical column names.
    """

    _lock = threading.Lock()

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or TRACKER_JSON_FILE)

    def _load(self) -> List[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) or []
        except Exception:
            return []

    def _save(self, rows: List[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def read(self, status, limit):
        rows = self._load()
        if status:
            rows = [r for r in rows if str(r.get("Status", "")).lower() == status.lower()]
        return {"rows": rows[:limit], "count": len(rows)}

    def update(self, content_id, fields):
        pk = schema.primary_key()
        with self._lock:
            rows = self._load()
            for r in rows:
                if str(r.get(pk, "")) == str(content_id):
                    r.update(fields)
                    self._save(rows)
                    return {"updated": content_id, "fields": list(fields.keys())}
        return {"error": f"{pk} {content_id} not found"}

    def upsert(self, row):
        pk = schema.primary_key()
        content_id = row.get(pk, "")
        with self._lock:
            rows = self._load()
            for r in rows:
                if str(r.get(pk, "")) == str(content_id):
                    r.update({k: v for k, v in row.items() if v != ""})
                    self._save(rows)
                    return {"updated": content_id, "title": row.get("Working Title / Hook", "")}
            rows.append(row)
            self._save(rows)
        return {"appended": content_id, "title": row.get("Working Title / Hook", "")}

    def get_schema(self):
        return {"backend": "jsonfile", "version": schema.schema_version(),
                "columns": schema.column_names(), "path": str(self.path)}


# ─── Selection ────────────────────────────────────────────────────────────────

_BACKENDS = {
    "sheets": SheetsBackend,
    "service_account": SheetsBackend,  # alias matching GOOGLE_AUTH_MODE
    "apps_script": AppsScriptBackend,
    "jsonfile": JsonFileBackend,
}


def resolve_backend_name() -> str:
    if TRACKER_BACKEND:
        return TRACKER_BACKEND
    # Backward compatibility: derive from the legacy GOOGLE_AUTH_MODE.
    return "apps_script" if GOOGLE_AUTH_MODE == "apps_script" else "sheets"


def get_backend() -> TrackerBackend:
    name = resolve_backend_name()
    cls = _BACKENDS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown TRACKER_BACKEND {name!r}. Options: {sorted(set(_BACKENDS))}"
        )
    return cls()

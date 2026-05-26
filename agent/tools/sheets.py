from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    GOOGLE_AUTH_MODE,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    CONTENTOPS_SHEET_ID,
    CONTENTOPS_SHEET_NAME,
    GOOGLE_APPS_SCRIPT_URL,
    GOOGLE_APPS_SCRIPT_TOKEN,
)

from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_service():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def _apps_script_call(action: str, payload: dict = None) -> dict:
    if not GOOGLE_APPS_SCRIPT_URL:
        return {"error": "GOOGLE_APPS_SCRIPT_URL is not set"}
    if not GOOGLE_APPS_SCRIPT_TOKEN:
        return {"error": "GOOGLE_APPS_SCRIPT_TOKEN is not set"}

    body = {
        "token": GOOGLE_APPS_SCRIPT_TOKEN,
        "action": action,
        "sheetId": CONTENTOPS_SHEET_ID,
        "sheetName": CONTENTOPS_SHEET_NAME,
    }
    if payload:
        body.update(payload)

    try:
        response = requests.post(GOOGLE_APPS_SCRIPT_URL, json=body, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("ok") is False:
            return {"error": data.get("error", "Apps Script returned ok=false")}
        return data.get("data", data)
    except Exception as e:
        return {"error": str(e)}


def read_tracker(status: str = None, limit: int = 30) -> dict:
    """Read rows from the content tracker. Optionally filter by status."""
    if GOOGLE_AUTH_MODE == "apps_script":
        return _apps_script_call("read_tracker", {"status": status, "limit": limit})

    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=CONTENTOPS_SHEET_ID, range=CONTENTOPS_SHEET_NAME)
            .execute()
        )
        rows = result.get("values", [])
        if not rows:
            return {"rows": [], "count": 0}

        headers = rows[0]
        data = [dict(zip(headers, row)) for row in rows[1:]]

        if status:
            data = [r for r in data if r.get("status", "").lower() == status.lower()]

        return {"rows": data[:limit], "count": len(data)}
    except Exception as e:
        return {"error": str(e)}


def write_tracker(idea_id: str, fields: dict) -> dict:
    """Update a row in the tracker by idea_id."""
    if GOOGLE_AUTH_MODE == "apps_script":
        return _apps_script_call(
            "write_tracker",
            {"idea_id": idea_id, "fields": fields},
        )

    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=CONTENTOPS_SHEET_ID, range=CONTENTOPS_SHEET_NAME)
            .execute()
        )
        rows = result.get("values", [])
        if not rows:
            return {"error": "Tracker is empty"}

        headers = rows[0]
        if "idea_id" not in headers:
            return {"error": "idea_id column not found in tracker"}

        id_col = headers.index("idea_id")
        target_row = None
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > id_col and row[id_col] == idea_id:
                target_row = i
                break

        if not target_row:
            return {"error": f"idea_id {idea_id} not found"}

        for field, value in fields.items():
            if field in headers:
                col_index = headers.index(field)
                col_letter = _col_letter(col_index)
                cell_range = f"{CONTENTOPS_SHEET_NAME}!{col_letter}{target_row}"
                service.spreadsheets().values().update(
                    spreadsheetId=CONTENTOPS_SHEET_ID,
                    range=cell_range,
                    valueInputOption="RAW",
                    body={"values": [[value]]},
                ).execute()

        return {"updated": idea_id, "fields": list(fields.keys())}
    except Exception as e:
        return {"error": str(e)}


def append_idea(idea_id: str, title: str, bucket: str, raw_input: str,
                source_type: str = "manual", status: str = "new") -> dict:
    """Append a new idea row to the tracker."""
    if GOOGLE_AUTH_MODE == "apps_script":
        return _apps_script_call(
            "append_idea",
            {
                "idea_id": idea_id,
                "title": title,
                "bucket": bucket,
                "raw_input": raw_input,
                "source_type": source_type,
                "status": status,
            },
        )

    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=CONTENTOPS_SHEET_ID,
                range=f"{CONTENTOPS_SHEET_NAME}!1:1",
            )
            .execute()
        )
        headers = result.get("values", [[]])[0]

        row_map = {
            "idea_id": idea_id,
            "title": title,
            "bucket": bucket,
            "source_type": source_type,
            "raw_input": raw_input,
            "status": status,
        }
        row = [row_map.get(h, "") for h in headers]

        service.spreadsheets().values().append(
            spreadsheetId=CONTENTOPS_SHEET_ID,
            range=CONTENTOPS_SHEET_NAME,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        return {"appended": idea_id, "title": title}
    except Exception as e:
        return {"error": str(e)}


def _col_letter(index: int) -> str:
    """Convert 0-based column index to spreadsheet letter (A, B, ... Z, AA...)."""
    result = ""
    while index >= 0:
        result = chr(index % 26 + ord("A")) + result
        index = index // 26 - 1
    return result

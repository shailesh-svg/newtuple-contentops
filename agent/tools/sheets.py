import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps_script_bridge import AppsScriptBridge
from config import (
    CONTENTOPS_SHEET_ID,
    CONTENTOPS_SHEET_NAME,
    GOOGLE_APPS_SCRIPT_TOKEN,
    GOOGLE_APPS_SCRIPT_URL,
    GOOGLE_AUTH_MODE,
    GOOGLE_SERVICE_ACCOUNT_FILE,
)
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

FIELD_ALIASES = {
    "idea_id": "Content ID",
    "content_id": "Content ID",
    "created_at": "Publish Date",
    "source_type": "Series Theme",
    "source_link": "Source / Input Link",
    "raw_input": "Key Message",
    "title": "Working Title / Hook",
    "draft_text": "Draft Text",
    "bucket": "Bucket",
    "status": "Status",
    "reviewer": "Approved By",
    "review_notes": "Review Notes",
    "review_action_ts": "Approval Timestamp",
    "scheduled_at": "Publish Date",
    "published_url": "Published URL",
    "platform": "Channel",
}


def _get_service():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def _bridge() -> AppsScriptBridge:
    return AppsScriptBridge(
        GOOGLE_APPS_SCRIPT_URL,
        GOOGLE_APPS_SCRIPT_TOKEN,
        CONTENTOPS_SHEET_ID,
        CONTENTOPS_SHEET_NAME,
    )


def _normalize_field_name(name: str) -> str:
    if name in FIELD_ALIASES:
        return FIELD_ALIASES[name]
    return name


def _normalize_fields(fields: dict) -> dict:
    return {_normalize_field_name(k): v for k, v in (fields or {}).items()}


def _content_id_from_idea_id(idea_id: str) -> str:
    return str(idea_id or "").strip()


def _normalize_status(status: str) -> str:
    raw = str(status or "").strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "new": "Idea",
        "draft": "Draft",
        "needs_review": "Needs Review",
        "needs_revision": "Needs Revision",
        "approved": "Approved",
        "rejected": "Rejected",
        "scheduled": "Scheduled",
        "published": "Published",
    }
    return mapping.get(raw, status)


def read_tracker(status: str = None, limit: int = 30) -> dict:
    """Read rows from the content tracker. Optionally filter by Status."""
    status = _normalize_status(status) if status else None

    if GOOGLE_AUTH_MODE == "apps_script":
        return _bridge().read_tracker(status=status, limit=limit)

    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=CONTENTOPS_SHEET_ID, range=CONTENTOPS_SHEET_NAME)
            .execute()
        )
        rows = result.get("values", [])
        header_index = _find_header_index(rows)
        if header_index < 0:
            return {"error": "Tracker header row not found"}

        headers = rows[header_index]
        data = [dict(zip(headers, row)) for row in rows[header_index + 1 :]]
        if status:
            data = [r for r in data if str(r.get("Status", "")).lower() == status.lower()]
        return {"rows": data[:limit], "count": len(data)}
    except Exception as e:
        return {"error": str(e)}


def write_tracker(idea_id: str, fields: dict) -> dict:
    """Update a row in the tracker by Content ID.

    The argument remains named idea_id for backwards compatibility with the
    existing agent tool schema and Slack command docs.
    """
    content_id = _content_id_from_idea_id(idea_id)
    normalized = _normalize_fields(fields)
    if "Status" in normalized:
        normalized["Status"] = _normalize_status(normalized["Status"])
    if "Approval Timestamp" not in normalized and (
        "Review Notes" in normalized or "Approved By" in normalized
    ):
        normalized["Approval Timestamp"] = datetime.now(timezone.utc).isoformat()

    if GOOGLE_AUTH_MODE == "apps_script":
        return _bridge().write_tracker(content_id, normalized)

    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=CONTENTOPS_SHEET_ID, range=CONTENTOPS_SHEET_NAME)
            .execute()
        )
        rows = result.get("values", [])
        header_index = _find_header_index(rows)
        if header_index < 0:
            return {"error": "Tracker header row not found"}

        headers = rows[header_index]
        if "Content ID" not in headers:
            return {"error": "Content ID column not found in tracker"}

        id_col = headers.index("Content ID")
        target_row = None
        for i, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
            if len(row) > id_col and row[id_col] == content_id:
                target_row = i
                break

        if not target_row:
            return {"error": f"Content ID {content_id} not found"}

        for field, value in normalized.items():
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

        return {"updated": content_id, "fields": list(normalized.keys())}
    except Exception as e:
        return {"error": str(e)}


def update_approval(
    content_id: str,
    status: str,
    review_notes: str = "",
    approved_by: str = "",
) -> dict:
    """Update approval fields for a tracker row."""
    normalized_status = _normalize_status(status)
    if GOOGLE_AUTH_MODE == "apps_script":
        return _bridge().update_approval(
            content_id=content_id,
            status=normalized_status,
            review_notes=review_notes,
            approved_by=approved_by,
        )
    return write_tracker(
        content_id,
        {
            "Status": normalized_status,
            "Review Notes": review_notes,
            "Approved By": approved_by,
            "Approval Timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def append_idea(
    idea_id: str,
    title: str,
    bucket: str,
    raw_input: str,
    source_type: str = "manual",
    status: str = "new",
) -> dict:
    """Append/upsert a tracker row using the live Content Tracker schema."""
    content_id = _content_id_from_idea_id(idea_id)
    row = {
        "Content ID": content_id,
        "Week": "",
        "Publish Date": datetime.now(timezone.utc).date().isoformat(),
        "Weekday": "",
        "Bucket": bucket,
        "Series Theme": source_type,
        "Working Title / Hook": title,
        "Audience Intent": "Educate and build trust",
        "Key Message": raw_input,
        "Draft Text": raw_input,
        "Format": "Text Post",
        "Channel": "LinkedIn",
        "Status": _normalize_status(status),
        "Priority": "Medium",
        "Source / Input Link": "",
        "CTA Type": "Start a conversation",
        "Repurpose Notes": "",
    }

    if GOOGLE_AUTH_MODE == "apps_script":
        return _bridge().upsert_tracker_row(row)

    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=CONTENTOPS_SHEET_ID,
                range=CONTENTOPS_SHEET_NAME,
            )
            .execute()
        )
        rows = result.get("values", [])
        header_index = _find_header_index(rows)
        if header_index < 0:
            return {"error": "Tracker header row not found"}
        headers = rows[header_index]
        values = [row.get(h, "") for h in headers]

        service.spreadsheets().values().append(
            spreadsheetId=CONTENTOPS_SHEET_ID,
            range=CONTENTOPS_SHEET_NAME,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [values]},
        ).execute()

        return {"appended": content_id, "title": title}
    except Exception as e:
        return {"error": str(e)}


def get_schema() -> dict:
    if GOOGLE_AUTH_MODE == "apps_script":
        return _bridge().get_schema()
    return {"error": "get_schema is only implemented for Apps Script mode"}


def _find_header_index(rows: list) -> int:
    for index, row in enumerate(rows):
        if "Content ID" in row or ("Week" in row and "Working Title / Hook" in row):
            return index
    return -1


def _col_letter(index: int) -> str:
    """Convert 0-based column index to spreadsheet letter (A, B, ... Z, AA...)."""
    result = ""
    while index >= 0:
        result = chr(index % 26 + ord("A")) + result
        index = index // 26 - 1
    return result

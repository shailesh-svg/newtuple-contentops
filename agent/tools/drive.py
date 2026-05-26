import re
from pathlib import Path
import sys
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    GOOGLE_AUTH_MODE,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_APPS_SCRIPT_URL,
    GOOGLE_APPS_SCRIPT_TOKEN,
)

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


def _get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def _get_docs_service():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("docs", "v1", credentials=creds)


def _apps_script_call(action: str, payload: dict = None) -> dict:
    if not GOOGLE_APPS_SCRIPT_URL:
        return {"error": "GOOGLE_APPS_SCRIPT_URL is not set"}
    if not GOOGLE_APPS_SCRIPT_TOKEN:
        return {"error": "GOOGLE_APPS_SCRIPT_TOKEN is not set"}

    body = {
        "token": GOOGLE_APPS_SCRIPT_TOKEN,
        "action": action,
        "folderId": GOOGLE_DRIVE_FOLDER_ID,
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


def _extract_id(doc_id_or_url: str) -> str:
    """Pull the file ID out of a full Drive/Docs URL, or return as-is."""
    patterns = [
        r"/document/d/([a-zA-Z0-9_-]+)",
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, doc_id_or_url)
        if match:
            return match.group(1)
    return doc_id_or_url


def _doc_to_text(doc: dict) -> str:
    """Extract plain text from a Google Docs API response."""
    text_parts = []
    body = doc.get("body", {})
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if paragraph:
            for pe in paragraph.get("elements", []):
                text_run = pe.get("textRun")
                if text_run:
                    text_parts.append(text_run.get("content", ""))
    return "".join(text_parts)


def read_drive_doc(doc_id: str) -> dict:
    """Read a Google Doc's text content by ID or URL."""
    if GOOGLE_AUTH_MODE == "apps_script":
        return _apps_script_call("read_drive_doc", {"doc_id": doc_id})

    file_id = _extract_id(doc_id)
    try:
        drive = _get_drive_service()
        meta = drive.files().get(fileId=file_id, fields="name,mimeType").execute()
        mime = meta.get("mimeType", "")

        if mime == "application/vnd.google-apps.document":
            docs = _get_docs_service()
            doc = docs.documents().get(documentId=file_id).execute()
            content = _doc_to_text(doc)
        else:
            # Plain text / markdown file — export as plain text
            content = (
                drive.files()
                .export(fileId=file_id, mimeType="text/plain")
                .execute()
                .decode("utf-8")
            )

        return {"file_id": file_id, "name": meta.get("name"), "content": content}
    except Exception as e:
        return {"error": str(e)}


def list_drive_files(query: str = "") -> dict:
    """List files in the configured source Drive folder."""
    if GOOGLE_AUTH_MODE == "apps_script":
        return _apps_script_call("list_drive_files", {"query": query})

    try:
        drive = _get_drive_service()
        q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
        if query:
            q += f" and name contains '{query}'"

        result = (
            drive.files()
            .list(
                q=q,
                fields="files(id, name, mimeType, modifiedTime)",
                orderBy="modifiedTime desc",
                pageSize=30,
            )
            .execute()
        )
        return {"files": result.get("files", [])}
    except Exception as e:
        return {"error": str(e)}

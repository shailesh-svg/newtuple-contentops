"""Pluggable knowledge-source backends.

Source material (blogs, founder notes, transcripts) can come from anywhere. The
agent reads it through one `SourceBackend` interface, so the system can point at
Google Drive, the Apps Script bridge, a local folder — or a new system you add —
purely via the SOURCE_BACKEND env var. Same adapter pattern as TrackerBackend.

Add a source in 3 steps: implement list/read, register in _SOURCES, set SOURCE_BACKEND.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    GOOGLE_APPS_SCRIPT_TOKEN,
    GOOGLE_APPS_SCRIPT_URL,
    GOOGLE_AUTH_MODE,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    SOURCE_BACKEND,
    SOURCE_LOCAL_DIR,
)

_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


class SourceBackend(Protocol):
    """Read-only knowledge source. Returns plain dicts the agent can consume."""

    def list(self, query: str = "") -> Dict[str, Any]: ...
    def read(self, doc_id: str) -> Dict[str, Any]: ...


def _extract_id(doc_id_or_url: str) -> str:
    """Pull a file ID out of a Drive/Docs URL, or return the input as-is."""
    for pattern in (r"/document/d/([a-zA-Z0-9_-]+)", r"/file/d/([a-zA-Z0-9_-]+)", r"id=([a-zA-Z0-9_-]+)"):
        m = re.search(pattern, doc_id_or_url)
        if m:
            return m.group(1)
    return doc_id_or_url


# ─── Google Drive (service account) ───────────────────────────────────────────

class GoogleDriveSource:
    def _drive(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE, scopes=_DRIVE_SCOPES)
        return build("drive", "v3", credentials=creds)

    def _docs(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE, scopes=_DRIVE_SCOPES)
        return build("docs", "v1", credentials=creds)

    @staticmethod
    def _doc_to_text(doc: dict) -> str:
        parts = []
        for element in doc.get("body", {}).get("content", []):
            for pe in (element.get("paragraph") or {}).get("elements", []):
                run = pe.get("textRun")
                if run:
                    parts.append(run.get("content", ""))
        return "".join(parts)

    def list(self, query: str = ""):
        try:
            drive = self._drive()
            q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
            if query:
                q += f" and name contains '{_escape_q(query)}'"
            result = drive.files().list(
                q=q, fields="files(id, name, mimeType, modifiedTime)",
                orderBy="modifiedTime desc", pageSize=30,
            ).execute()
            return {"files": result.get("files", [])}
        except Exception as e:
            return {"error": str(e)}

    def read(self, doc_id: str):
        file_id = _extract_id(doc_id)
        try:
            drive = self._drive()
            meta = drive.files().get(fileId=file_id, fields="name,mimeType").execute()
            mime = meta.get("mimeType", "")
            if mime == "application/vnd.google-apps.document":
                content = self._doc_to_text(self._docs().documents().get(documentId=file_id).execute())
            else:
                content = drive.files().export(fileId=file_id, mimeType="text/plain").execute().decode("utf-8")
            return {"file_id": file_id, "name": meta.get("name"), "content": content}
        except Exception as e:
            return {"error": str(e)}


def _escape_q(query: str) -> str:
    # Escape single quotes for the Drive query language.
    return query.replace("\\", "\\\\").replace("'", "\\'")


# ─── Apps Script bridge ───────────────────────────────────────────────────────

class AppsScriptSource:
    def _call(self, action: str, payload: dict) -> dict:
        if not GOOGLE_APPS_SCRIPT_URL or not GOOGLE_APPS_SCRIPT_TOKEN:
            return {"error": "Apps Script URL/token not set"}
        body = {"token": GOOGLE_APPS_SCRIPT_TOKEN, "action": action,
                "folderId": GOOGLE_DRIVE_FOLDER_ID, **payload}
        try:
            resp = requests.post(GOOGLE_APPS_SCRIPT_URL, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok") is False:
                return {"error": data.get("error", "Apps Script returned ok=false")}
            return data.get("data", data)
        except Exception as e:
            return {"error": str(e)}

    def list(self, query: str = ""):
        return self._call("list_drive_files", {"query": query})

    def read(self, doc_id: str):
        return self._call("read_drive_doc", {"doc_id": doc_id})


# ─── Local filesystem (no credentials — dev / test / demos) ───────────────────

class LocalFsSource:
    """Reads source material from a local directory. Zero credentials."""

    _TEXT_SUFFIXES = {".md", ".txt", ".markdown", ".rst", ".csv", ".json"}

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = Path(root or SOURCE_LOCAL_DIR)

    def list(self, query: str = ""):
        if not self.root.exists():
            return {"files": []}
        files = []
        for p in sorted(self.root.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            if query and query.lower() not in p.name.lower():
                continue
            rel = str(p.relative_to(self.root))
            files.append({"id": rel, "name": p.name,
                          "mimeType": "text/plain", "modifiedTime": ""})
        return {"files": files[:30]}

    def read(self, doc_id: str):
        # doc_id is a path relative to root (or an absolute path inside it).
        candidate = (self.root / doc_id).resolve()
        try:
            root_resolved = self.root.resolve()
            if root_resolved not in candidate.parents and candidate != root_resolved:
                return {"error": "path escapes the source directory"}
            if not candidate.is_file():
                return {"error": f"File not found: {doc_id}"}
            return {"file_id": doc_id, "name": candidate.name,
                    "content": candidate.read_text(encoding="utf-8", errors="replace")}
        except Exception as e:
            return {"error": str(e)}


# ─── Selection ────────────────────────────────────────────────────────────────

_SOURCES = {
    "gdrive": GoogleDriveSource,
    "service_account": GoogleDriveSource,  # alias for GOOGLE_AUTH_MODE
    "apps_script": AppsScriptSource,
    "localfs": LocalFsSource,
}


def resolve_source_name() -> str:
    if SOURCE_BACKEND:
        return SOURCE_BACKEND
    return "apps_script" if GOOGLE_AUTH_MODE == "apps_script" else "gdrive"


def get_source() -> SourceBackend:
    name = resolve_source_name()
    cls = _SOURCES.get(name)
    if cls is None:
        raise ValueError(f"Unknown SOURCE_BACKEND {name!r}. Options: {sorted(set(_SOURCES))}")
    return cls()

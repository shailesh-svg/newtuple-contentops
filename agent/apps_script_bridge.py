"""Token-based Google Apps Script bridge for tracker operations.

This bridge matches the deployed ContentOps Apps Script style:
POST {token, action, sheetId, sheetName, ...}

It intentionally does not use OAuth bearer headers. The Apps Script web app
already runs as the owner's Google account and gates requests with the shared
ContentOps token.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests


class AppsScriptBridge:
    def __init__(self, url: str, token: str, sheet_id: str, sheet_name: str) -> None:
        self.url = url
        self.token = token
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name

    def call(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "token": self.token,
            "action": action,
            "sheetId": self.sheet_id,
            "sheetName": self.sheet_name,
        }
        if payload:
            body.update(payload)

        response = requests.post(self.url, json=body, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("ok") is False:
            return {"error": data.get("error", "Apps Script returned ok=false")}
        return data.get("data", data)

    def health(self) -> Dict[str, Any]:
        return self.call("health")

    def get_schema(self) -> Dict[str, Any]:
        return self.call("get_schema")

    def read_tracker(self, status: str = None, limit: int = 30) -> Dict[str, Any]:
        return self.call("read_tracker", {"status": status, "limit": limit})

    def write_tracker(self, content_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self.call("write_tracker", {"content_id": content_id, "fields": fields})

    def upsert_tracker_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.call("upsert_tracker_row", {"row": row})

    def update_approval(
        self,
        content_id: str,
        status: str,
        review_notes: str = "",
        approved_by: str = "",
    ) -> Dict[str, Any]:
        return self.call(
            "update_approval",
            {
                "content_id": content_id,
                "status": status,
                "review_notes": review_notes,
                "approved_by": approved_by,
            },
        )

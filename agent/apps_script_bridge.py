"""Token-based Google Apps Script bridge for tracker operations.

This bridge matches the deployed ContentOps Apps Script style:
POST {token, action, sheetId, sheetName, ...}

It intentionally does not use OAuth bearer headers. The Apps Script web app
already runs as the owner's Google account and gates requests with the shared
ContentOps token.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

log = logging.getLogger(__name__)

# Apps Script web apps occasionally return transient 5xx / time out under load.
# Retry those a few times with exponential backoff; do NOT retry 4xx (a 401/400
# won't fix itself) or application-level ok=false errors.
_MAX_ATTEMPTS = 4
_BACKOFF_BASE = 0.5  # seconds: 0.5, 1.0, 2.0 between attempts
_RETRY_STATUS = {429, 500, 502, 503, 504}
_TIMEOUT = 30


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

        response = self._post_with_retry(body)
        data = response.json()
        if data.get("ok") is False:
            return {"error": data.get("error", "Apps Script returned ok=false")}
        return data.get("data", data)

    def _post_with_retry(self, body: Dict[str, Any]) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = requests.post(self.url, json=body, timeout=_TIMEOUT)
                if response.status_code in _RETRY_STATUS and attempt < _MAX_ATTEMPTS:
                    raise requests.HTTPError(f"transient {response.status_code}")
                response.raise_for_status()
                return response
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                last_exc = e
                # Don't retry deterministic client errors (4xx other than 429).
                resp = getattr(e, "response", None)
                status = getattr(resp, "status_code", None)
                if status is not None and status not in _RETRY_STATUS:
                    raise
                if attempt >= _MAX_ATTEMPTS:
                    break
                sleep_s = _BACKOFF_BASE * (2 ** (attempt - 1))
                log.warning("apps_script %s failed (attempt %d/%d): %s — retrying in %.1fs",
                            body.get("action"), attempt, _MAX_ATTEMPTS, e, sleep_s)
                time.sleep(sleep_s)
        raise last_exc  # type: ignore[misc]

    def health(self) -> Dict[str, Any]:
        return self.call("health")

    def get_schema(self) -> Dict[str, Any]:
        return self.call("get_schema")

    def read_tracker(self, status: str = None, limit: int = 30) -> Dict[str, Any]:
        return self.call("read_tracker", {"status": status, "limit": limit})

    def write_tracker(self, content_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        # Send both content_id and idea_id for backward compat with older deployed scripts
        return self.call("write_tracker", {"content_id": content_id, "idea_id": content_id, "fields": fields})

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

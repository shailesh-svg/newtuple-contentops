"""Content tracker facade.

This module is the stable, agent-facing API for the tracker. It applies the
canonical schema (alias + status normalisation, create-row construction) and
delegates I/O to whichever storage backend is configured (Google Sheets, Apps
Script, local JSON file, …). Public function names + signatures are unchanged
for backward compatibility with the agent tools and Slack commands.

Schema lives in contentops/schema/tracker.schema.json (loaded via agent/schema.py).
Backends live in tools/tracker_backends.py.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import schema

from tools.tracker_backends import get_backend


def _content_id_from_idea_id(idea_id: str) -> str:
    return str(idea_id or "").strip()


def read_tracker(status: str = None, limit: int = 30) -> dict:
    """Read rows from the content tracker. Optionally filter by Status."""
    status = schema.normalize_status(status) if status else None
    return get_backend().read(status, limit)


def write_tracker(idea_id: str, fields: dict) -> dict:
    """Update a row in the tracker by Content ID.

    The argument remains named idea_id for backwards compatibility with the
    agent tool schema and Slack command docs.
    """
    content_id = _content_id_from_idea_id(idea_id)
    normalized = schema.normalize_fields(fields)
    if "Status" in normalized:
        normalized["Status"] = schema.normalize_status(normalized["Status"])
    # Stamp an approval timestamp whenever review fields change.
    if "Approval Timestamp" not in normalized and (
        "Review Notes" in normalized or "Approved By" in normalized
    ):
        normalized["Approval Timestamp"] = datetime.now(timezone.utc).isoformat()
    return get_backend().update(content_id, normalized)


def append_idea(
    idea_id: str,
    title: str,
    bucket: str,
    raw_input: str,
    source_type: str = "manual",
    status: str = "new",
) -> dict:
    """Append/upsert a tracker row using the canonical schema + create defaults."""
    row = schema.build_create_row(
        {
            "idea_id": _content_id_from_idea_id(idea_id),
            "title": title,
            "bucket": bucket,
            "raw_input": raw_input,
            "source_type": source_type,
            "status": status,
        }
    )
    return get_backend().upsert(row)


def update_approval(
    content_id: str,
    status: str,
    review_notes: str = "",
    approved_by: str = "",
) -> dict:
    """Update approval fields for a tracker row."""
    return write_tracker(
        content_id,
        {
            "status": status,
            "review_notes": review_notes,
            "reviewer": approved_by,
            "review_action_ts": datetime.now(timezone.utc).isoformat(),
        },
    )


def get_schema() -> dict:
    return get_backend().get_schema()

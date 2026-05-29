"""Platform-neutral review service.

The single home for approve / revise / reject / edit. Every interface — Slack,
the web dashboard, CLI, future Teams/email — translates its input into a
`Principal` and calls these functions. RBAC, the tracker write, and the audit
trail happen here, so they are identical on every surface and never duplicated
in an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

import observability
from identity import Principal
from tools.sheets import write_tracker

# Review decision verb → canonical tracker status.
DECISIONS: Dict[str, str] = {
    "approve": "Approved",
    "revise": "Needs Revision",
    "reject": "Rejected",
}

STATUS_ICON = {"Approved": "✅", "Needs Revision": "✏️", "Rejected": "❌"}


@dataclass
class ReviewResult:
    ok: bool
    status: str = ""
    content_id: str = ""
    message: str = ""
    error: str = ""
    unauthorized: bool = False

    @property
    def icon(self) -> str:
        return STATUS_ICON.get(self.status, "")


def decide(
    principal: Principal,
    content_id: str,
    decision: str,
    notes: str = "",
    source: str = "",
) -> ReviewResult:
    """Apply a review decision (approve/revise/reject) under RBAC.

    Returns a ReviewResult; never raises for the normal authz/not-found cases so
    every interface can render the outcome consistently.
    """
    decision = (decision or "").strip().lower()
    if decision not in DECISIONS:
        return ReviewResult(ok=False, error=f"Unknown decision: {decision!r}")

    if not principal.can(decision):
        return ReviewResult(
            ok=False,
            unauthorized=True,
            message=(
                f"{principal.display_name} ({principal.role}) is not authorized to "
                f"{decision}."
            ),
        )

    if not content_id:
        return ReviewResult(ok=False, error="No content id provided.")

    status = DECISIONS[decision]
    fields = {
        "status": status,
        "reviewer": principal.id,
        "review_action_ts": datetime.now(timezone.utc).isoformat(),
    }
    if notes:
        fields["review_notes"] = notes

    result = write_tracker(content_id, fields)
    if isinstance(result, dict) and "error" in result:
        return ReviewResult(ok=False, status=status, content_id=content_id,
                            error=result["error"])

    observability.record_approval(content_id, status, principal.id,
                                  source=source or principal.platform)
    msg = f"{STATUS_ICON.get(status, '')} `{content_id}` → *{status}*"
    if notes:
        msg += f"\n> {notes}"
    return ReviewResult(ok=True, status=status, content_id=content_id, message=msg)


def edit(
    principal: Principal,
    content_id: str,
    fields: dict,
    source: str = "",
) -> ReviewResult:
    """Edit content fields (title, draft text, bucket, …) under RBAC."""
    if not principal.can("edit"):
        return ReviewResult(
            ok=False,
            unauthorized=True,
            message=f"{principal.display_name} ({principal.role}) is not authorized to edit.",
        )
    if not content_id:
        return ReviewResult(ok=False, error="No content id provided.")
    if not fields:
        return ReviewResult(ok=False, error="No fields to update.")

    result = write_tracker(content_id, fields)
    if isinstance(result, dict) and "error" in result:
        return ReviewResult(ok=False, content_id=content_id, error=result["error"])

    observability.record_event(
        "edit", name=content_id, ok=True,
        detail={"by": principal.id, "fields": list(fields.keys()), "source": source or principal.platform},
    )
    return ReviewResult(ok=True, content_id=content_id,
                        message=f"`{content_id}` updated ({', '.join(fields.keys())}).")

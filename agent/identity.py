"""Platform-neutral identity.

The engine reasons about a `Principal` — a canonical actor with a role — not a
Slack user id. Each interface (Slack, web dashboard, CLI, …) resolves its own
platform identity to a Principal via `resolve()`, then the rest of the system
(RBAC, ReviewService, audit) is identical regardless of where the actor came
from. Role/permission data and the identity map live in authz.yaml (see authz.py).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    """An actor, resolved from any platform to a canonical identity + role."""

    id: str                      # canonical principal id, e.g. "alice"
    display_name: str
    platform: str                # "slack" | "web" | "cli" | ...
    role: str                    # admin | editor | reviewer | viewer
    permissions: frozenset       # resolved permission set for the role
    strict: bool = True          # when False, RBAC is disabled (allow all)

    def can(self, action: str) -> bool:
        """True if this principal may perform `action` (a command or review verb)."""
        if not self.strict:
            return True
        return "*" in self.permissions or action in self.permissions

    @property
    def is_authenticated(self) -> bool:
        return bool(self.id)


def resolve(platform: str, platform_user_id: str, display_name: str = "") -> Principal:
    """Resolve a platform identity to a Principal using the shared AuthZ config."""
    from authz import AUTHZ

    return AUTHZ.resolve_principal(platform, platform_user_id, display_name)

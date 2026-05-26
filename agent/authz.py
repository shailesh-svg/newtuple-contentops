"""Role-based access control for Slack users."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Set

from config import AUTHZ_ADMIN_USERS, AUTHZ_DEFAULT_ROLE, AUTHZ_FILE, AUTHZ_STRICT

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional at bootstrap
    yaml = None


DEFAULT_ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {"*"},
    "editor": {
        "draft-from-idea",
        "plan-week",
        "repurpose-blog",
        "help",
        "whoami",
    },
    "reviewer": {
        "help",
        "whoami",
        "approve",
        "revise",
        "reject",
    },
    "viewer": {
        "help",
        "whoami",
    },
}


class AuthZ:
    def __init__(self) -> None:
        self.strict = AUTHZ_STRICT
        self.default_role = AUTHZ_DEFAULT_ROLE
        self.load_error = ""
        self.role_permissions: Dict[str, Set[str]] = {
            r: set(p) for r, p in DEFAULT_ROLE_PERMISSIONS.items()
        }
        self.user_roles: Dict[str, str] = {}
        self.load_config()

    def load_config(self) -> None:
        path = Path(AUTHZ_FILE)

        # Bootstrap admins from env always win.
        for uid in AUTHZ_ADMIN_USERS:
            self.user_roles[uid] = "admin"

        if not path.exists():
            return

        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return

        cfg = self._parse_config(raw, path.suffix.lower())
        if not isinstance(cfg, dict):
            return

        roles = cfg.get("roles", {})
        if isinstance(roles, dict):
            for role, perms in roles.items():
                if isinstance(perms, list):
                    self.role_permissions[role] = {str(p).strip() for p in perms if str(p).strip()}

        users = cfg.get("users", {})
        if isinstance(users, dict):
            for user_id, role in users.items():
                if role in self.role_permissions:
                    self.user_roles[str(user_id).strip()] = str(role)

        default_role = cfg.get("default_role")
        if isinstance(default_role, str) and default_role in self.role_permissions:
            self.default_role = default_role

    def _parse_config(self, raw: str, suffix: str) -> dict:
        try:
            if suffix == ".json":
                return json.loads(raw)
            if yaml is not None:
                return yaml.safe_load(raw)
            self.load_error = "PyYAML is not installed but AUTHZ_FILE is YAML"
            return {}
        except Exception as e:
            self.load_error = str(e)
            return {}

    def role_for_user(self, user_id: str) -> str:
        return self.user_roles.get(user_id, self.default_role)

    def permissions_for_user(self, user_id: str) -> Set[str]:
        role = self.role_for_user(user_id)
        return self.role_permissions.get(role, set())

    def can_run_command(self, user_id: str, command: str) -> bool:
        if not self.strict:
            return True
        perms = self.permissions_for_user(user_id)
        if "*" in perms:
            return True
        if command in perms:
            return True
        if command == "doctor":
            # CLI command, not intended for Slack users.
            return False
        if command == "update-status":
            return False
        return False

    def can_review(self, user_id: str, action: str) -> bool:
        if not self.strict:
            return True
        perms = self.permissions_for_user(user_id)
        return "*" in perms or action in perms

    def auth_message(self, user_id: str, attempted: str) -> str:
        role = self.role_for_user(user_id)
        perms = sorted(self.permissions_for_user(user_id))
        allowed = ", ".join(f"`{p}`" for p in perms) if perms else "none"

        if not self.strict:
            return ""

        return (
            f"You are not authorized to run `{attempted}`. "
            f"Your role: `{role}`. Allowed actions: {allowed}. "
            "Ask an admin to update `agent/authz.yaml` or `AUTHZ_ADMIN_USERS`."
        )


AUTHZ = AuthZ()

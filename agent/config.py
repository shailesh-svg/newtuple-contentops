import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - fallback when deps not installed yet
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).parent / ".env")
else:
    # Lightweight fallback so basic commands (e.g., doctor) can read .env
    # before dependencies are installed.
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, value = s.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def _env(name: str, default: str = "") -> str:
    """Read an env var and tolerate inline comments in local .env values."""
    value = os.environ.get(name, default)
    if " #" in value:
        value = value.split(" #", 1)[0]
    return value.strip().strip("'").strip('"')


REPO_ROOT = Path(__file__).parent.parent
CONTENTOPS_DIR = REPO_ROOT / "contentops"

# AI providers — Claude is primary, OpenAI is secondary
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
AI_PROVIDER = _env("AI_PROVIDER", "claude")  # "claude" | "openai"

CLAUDE_MODEL = _env("CLAUDE_MODEL", "claude-opus-4-7")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o")

# Google
GOOGLE_AUTH_MODE = _env("GOOGLE_AUTH_MODE", "service_account").lower()
GOOGLE_SERVICE_ACCOUNT_FILE = _env("GOOGLE_SERVICE_ACCOUNT_FILE")
CONTENTOPS_SHEET_ID = _env("CONTENTOPS_SHEET_ID")
CONTENTOPS_SHEET_NAME = _env("CONTENTOPS_SHEET_NAME", "Content Tracker")
GOOGLE_DRIVE_FOLDER_ID = _env("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_APPS_SCRIPT_URL = _env("GOOGLE_APPS_SCRIPT_URL")
GOOGLE_APPS_SCRIPT_TOKEN = _env("GOOGLE_APPS_SCRIPT_TOKEN")

# Slack
SLACK_BOT_TOKEN = _env("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = _env("SLACK_APP_TOKEN")  # required for Socket Mode
SLACK_REVIEW_CHANNEL = _env("SLACK_REVIEW_CHANNEL", "#contentops-review")

# AuthZ / RBAC
AUTHZ_FILE = _env("AUTHZ_FILE", str(Path(__file__).parent / "authz.yaml"))
if not Path(AUTHZ_FILE).is_absolute():
    AUTHZ_FILE = str((Path(__file__).parent / AUTHZ_FILE).resolve())
AUTHZ_STRICT = _env("AUTHZ_STRICT", "true").lower() in {
    "1",
    "true",
    "yes",
}
AUTHZ_DEFAULT_ROLE = _env("AUTHZ_DEFAULT_ROLE", "viewer")
AUTHZ_ADMIN_USERS = [
    u.strip()
    for u in _env("AUTHZ_ADMIN_USERS").split(",")
    if u.strip()
]

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

REPO_ROOT = Path(__file__).parent.parent
CONTENTOPS_DIR = REPO_ROOT / "contentops"

# AI providers — Claude is primary, OpenAI is secondary
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "claude")  # "claude" | "openai"

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Google
GOOGLE_AUTH_MODE = os.environ.get("GOOGLE_AUTH_MODE", "service_account").strip().lower()
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
CONTENTOPS_SHEET_ID = os.environ.get("CONTENTOPS_SHEET_ID", "")
CONTENTOPS_SHEET_NAME = os.environ.get("CONTENTOPS_SHEET_NAME", "Sheet1")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_APPS_SCRIPT_URL = os.environ.get("GOOGLE_APPS_SCRIPT_URL", "")
GOOGLE_APPS_SCRIPT_TOKEN = os.environ.get("GOOGLE_APPS_SCRIPT_TOKEN", "")

# Slack
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")  # required for Socket Mode
SLACK_REVIEW_CHANNEL = os.environ.get("SLACK_REVIEW_CHANNEL", "#contentops-review")

# AuthZ / RBAC
AUTHZ_FILE = os.environ.get("AUTHZ_FILE", str(Path(__file__).parent / "authz.yaml"))
if not Path(AUTHZ_FILE).is_absolute():
    AUTHZ_FILE = str((Path(__file__).parent / AUTHZ_FILE).resolve())
AUTHZ_STRICT = os.environ.get("AUTHZ_STRICT", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}
AUTHZ_DEFAULT_ROLE = os.environ.get("AUTHZ_DEFAULT_ROLE", "viewer")
AUTHZ_ADMIN_USERS = [
    u.strip()
    for u in os.environ.get("AUTHZ_ADMIN_USERS", "").split(",")
    if u.strip()
]

import logging
import os
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

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

# AI providers — Claude is primary, OpenAI is secondary, Ollama for local testing
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
AI_PROVIDER = _env("AI_PROVIDER", "claude")  # "claude" | "openai" | "ollama"

CLAUDE_MODEL = _env("CLAUDE_MODEL", "claude-opus-4-7")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o")

# Ollama (local) — uses OpenAI-compatible API
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3.1")

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


def validate_startup() -> None:
    """Fail fast with a clear message if required credentials are missing.

    Call this at the top of start_slack_bot() so misconfiguration is caught
    immediately rather than surfacing as a cryptic error on the first tool call.
    """
    _log = logging.getLogger(__name__)
    errors: list = []

    provider = AI_PROVIDER.lower()
    if provider not in {"claude", "openai", "ollama"}:
        errors.append(f"AI_PROVIDER must be claude, openai, or ollama — got {provider!r}")
    if provider == "claude" and not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY is required when AI_PROVIDER=claude")
    if provider == "openai" and not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is required when AI_PROVIDER=openai")
    if provider == "openai" and not OPENAI_MODEL:
        errors.append("OPENAI_MODEL is required when AI_PROVIDER=openai (e.g. gpt-4o)")
    if not SLACK_BOT_TOKEN:
        errors.append("SLACK_BOT_TOKEN is required")
    if not SLACK_APP_TOKEN:
        errors.append("SLACK_APP_TOKEN is required for Socket Mode")
    if GOOGLE_AUTH_MODE == "apps_script":
        if not GOOGLE_APPS_SCRIPT_URL:
            errors.append("GOOGLE_APPS_SCRIPT_URL is required when GOOGLE_AUTH_MODE=apps_script")
        if not GOOGLE_APPS_SCRIPT_TOKEN:
            errors.append("GOOGLE_APPS_SCRIPT_TOKEN is required when GOOGLE_AUTH_MODE=apps_script")
    elif GOOGLE_AUTH_MODE == "service_account":
        if not GOOGLE_SERVICE_ACCOUNT_FILE:
            errors.append("GOOGLE_SERVICE_ACCOUNT_FILE is required when GOOGLE_AUTH_MODE=service_account")
    if not CONTENTOPS_SHEET_ID:
        errors.append("CONTENTOPS_SHEET_ID is required")

    if errors:
        for err in errors:
            _log.error("config: %s", err)
        raise SystemExit(
            f"\n[contentops] {len(errors)} config error(s) — fix agent/.env and restart:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

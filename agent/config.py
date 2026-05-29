import json
import logging
import os
from pathlib import Path


class _JsonLogFormatter(logging.Formatter):
    """Structured one-line-JSON logs for ingestion by log platforms."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
if os.environ.get("LOG_FORMAT", "text").lower() == "json":
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonLogFormatter())
    logging.basicConfig(level=_LOG_LEVEL, handlers=[_handler])
else:
    logging.basicConfig(
        level=_LOG_LEVEL,
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

# Tracker backend selection (plug-and-play storage).
#   sheets      — Google Sheets via service account
#   apps_script — Google Apps Script web-app bridge
#   jsonfile    — local JSON file (no credentials; for dev/test/demos)
# Left blank, it is derived from GOOGLE_AUTH_MODE for backward compatibility.
TRACKER_BACKEND = _env("TRACKER_BACKEND").lower()
TRACKER_JSON_FILE = _env("TRACKER_JSON_FILE", str(Path(__file__).parent / "data" / "tracker.json"))

# Knowledge-source backend (where the agent reads source material from).
#   gdrive      — Google Drive via service account
#   apps_script — Google Apps Script bridge
#   localfs     — a local directory (no credentials; dev/test/demos)
# Blank → derived from GOOGLE_AUTH_MODE for backward compatibility.
SOURCE_BACKEND = _env("SOURCE_BACKEND").lower()
SOURCE_LOCAL_DIR = _env("SOURCE_LOCAL_DIR", str(Path(__file__).parent / "data" / "sources"))

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

# Observability / tracking
# SQLite store for run + event telemetry. On Fly.io point this at a mounted
# volume (e.g. /data/ops.db) so history survives deploys.
CONTENTOPS_DB = _env("CONTENTOPS_DB", str(Path(__file__).parent / "data" / "ops.db"))

# Quality gate — drafts that fail hard checks are blocked before reaching Slack.
QUALITY_GATE_ENABLED = _env("QUALITY_GATE_ENABLED", "true").lower() in {"1", "true", "yes"}
QUALITY_MIN_VOICE_SCORE = int(_env("QUALITY_MIN_VOICE_SCORE", "8") or "8")
QUALITY_MIN_CHARS = int(_env("QUALITY_MIN_CHARS", "200") or "200")
QUALITY_MAX_CHARS = int(_env("QUALITY_MAX_CHARS", "3000") or "3000")

# Dashboard (read-only web view for non-technical members)
DASHBOARD_PORT = int(_env("DASHBOARD_PORT", "8080") or "8080")
DASHBOARD_HOST = _env("DASHBOARD_HOST", "0.0.0.0")
# Optional shared-secret gate: if set, viewers must pass ?token=... (or an
# Authorization: Bearer header). Leave empty for an open internal dashboard.
DASHBOARD_TOKEN = _env("DASHBOARD_TOKEN")


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
    # Tracker backend: explicit TRACKER_BACKEND wins, else derive from the legacy
    # GOOGLE_AUTH_MODE. The jsonfile backend needs no Google credentials.
    backend = TRACKER_BACKEND or ("apps_script" if GOOGLE_AUTH_MODE == "apps_script" else "sheets")
    if backend == "apps_script":
        if not GOOGLE_APPS_SCRIPT_URL:
            errors.append("GOOGLE_APPS_SCRIPT_URL is required for the apps_script backend")
        if not GOOGLE_APPS_SCRIPT_TOKEN:
            errors.append("GOOGLE_APPS_SCRIPT_TOKEN is required for the apps_script backend")
        if not CONTENTOPS_SHEET_ID:
            errors.append("CONTENTOPS_SHEET_ID is required")
    elif backend in {"sheets", "service_account"}:
        if not GOOGLE_SERVICE_ACCOUNT_FILE:
            errors.append("GOOGLE_SERVICE_ACCOUNT_FILE is required for the sheets backend")
        if not CONTENTOPS_SHEET_ID:
            errors.append("CONTENTOPS_SHEET_ID is required")
    elif backend == "jsonfile":
        pass  # no external credentials required
    else:
        errors.append(f"Unknown TRACKER_BACKEND {backend!r} (sheets | apps_script | jsonfile)")

    if errors:
        for err in errors:
            _log.error("config: %s", err)
        raise SystemExit(
            f"\n[contentops] {len(errors)} config error(s) — fix agent/.env and restart:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

"""
Environment and connectivity checks for ContentOps Agent.

Run:
  python main.py doctor
"""

import re
from pathlib import Path

from authz import AUTHZ
from config import (
    AI_PROVIDER,
    ANTHROPIC_API_KEY,
    AUTHZ_FILE,
    AUTHZ_STRICT,
    CONTENTOPS_SHEET_ID,
    GOOGLE_APPS_SCRIPT_TOKEN,
    GOOGLE_APPS_SCRIPT_URL,
    GOOGLE_AUTH_MODE,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    SLACK_APP_TOKEN,
    SLACK_BOT_TOKEN,
)


def _ok(label: str, details: str = "") -> str:
    suffix = f" — {details}" if details else ""
    return f"[OK] {label}{suffix}"


def _fail(label: str, details: str = "") -> str:
    suffix = f" — {details}" if details else ""
    return f"[FAIL] {label}{suffix}"


def _looks_placeholder(value: str) -> bool:
    v = (value or "").strip().lower()
    return (
        not v
        or "your_" in v
        or "your-" in v
        or "example" in v
        or "path/to" in v
        or "here" in v
        or v in {"changeme", "replace_me", "todo"}
    )


def _redact_error(error: Exception) -> str:
    text = str(error)
    patterns = [
        r"sk-[A-Za-z0-9_\-]+",
        r"sk-proj-[A-Za-z0-9_\-]+",
        r"xoxb-[A-Za-z0-9_\-]+",
        r"xapp-[A-Za-z0-9_\-]+",
        r"[A-Za-z0-9]{8,}\*+[A-Za-z0-9]{4,}",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "[redacted]", text)
    return text


def _looks_openai_key(value: str) -> bool:
    return bool(re.match(r"^sk-(proj-)?[A-Za-z0-9_\-]+$", value or ""))


def _looks_anthropic_key(value: str) -> bool:
    return bool(re.match(r"^sk-ant-[A-Za-z0-9_\-]+$", value or ""))


def _looks_slack_bot_token(value: str) -> bool:
    return bool(re.match(r"^xoxb-[A-Za-z0-9\-]+$", value or ""))


def _looks_slack_app_token(value: str) -> bool:
    return bool(re.match(r"^xapp-[A-Za-z0-9\-]+$", value or ""))


def run_doctor() -> str:
    lines = []

    # Env presence checks
    anthropic_ready = ANTHROPIC_API_KEY and not _looks_placeholder(ANTHROPIC_API_KEY)
    openai_ready = OPENAI_API_KEY and not _looks_placeholder(OPENAI_API_KEY)
    slack_bot_ready = SLACK_BOT_TOKEN and not _looks_placeholder(SLACK_BOT_TOKEN)
    slack_app_ready = SLACK_APP_TOKEN and not _looks_placeholder(SLACK_APP_TOKEN)
    apps_script_mode = GOOGLE_AUTH_MODE == "apps_script"
    service_account_mode = GOOGLE_AUTH_MODE == "service_account"
    google_file_ready = (
        GOOGLE_SERVICE_ACCOUNT_FILE
        and not _looks_placeholder(GOOGLE_SERVICE_ACCOUNT_FILE)
        and Path(GOOGLE_SERVICE_ACCOUNT_FILE).exists()
    )

    if GOOGLE_AUTH_MODE in {"apps_script", "service_account"}:
        lines.append(_ok("GOOGLE_AUTH_MODE", GOOGLE_AUTH_MODE))
    else:
        lines.append(_fail("GOOGLE_AUTH_MODE invalid", "expected apps_script or service_account"))

    if anthropic_ready:
        lines.append(_ok("ANTHROPIC_API_KEY present"))
    else:
        lines.append(_fail("ANTHROPIC_API_KEY missing or placeholder"))

    if openai_ready:
        lines.append(_ok("OPENAI_API_KEY present"))
    else:
        lines.append(_fail("OPENAI_API_KEY missing or placeholder"))

    # Availability signal: with one provider there is no failover. A quota or
    # rate-limit blip on it stalls every run (transient errors are retried with
    # backoff, but sustained quota exhaustion needs a second provider).
    if AI_PROVIDER != "ollama":
        usable_providers = sum([bool(anthropic_ready), bool(openai_ready)])
        if usable_providers >= 2:
            lines.append(_ok("Provider failover available", "Claude + OpenAI both configured"))
        else:
            only = "OpenAI" if openai_ready else "Claude" if anthropic_ready else "none"
            lines.append(_fail(
                "No provider failover",
                f"only {only} configured — a quota/rate limit will stall runs; "
                "set the other provider's key for failover",
            ))

    if service_account_mode:
        if google_file_ready:
            lines.append(_ok("GOOGLE_SERVICE_ACCOUNT_FILE found", GOOGLE_SERVICE_ACCOUNT_FILE))
        else:
            lines.append(_fail("GOOGLE_SERVICE_ACCOUNT_FILE missing or path invalid", GOOGLE_SERVICE_ACCOUNT_FILE))

    if apps_script_mode:
        if GOOGLE_APPS_SCRIPT_URL and not _looks_placeholder(GOOGLE_APPS_SCRIPT_URL):
            lines.append(_ok("GOOGLE_APPS_SCRIPT_URL present"))
        else:
            lines.append(_fail("GOOGLE_APPS_SCRIPT_URL missing or placeholder"))

        if GOOGLE_APPS_SCRIPT_TOKEN and not _looks_placeholder(GOOGLE_APPS_SCRIPT_TOKEN):
            lines.append(_ok("GOOGLE_APPS_SCRIPT_TOKEN present"))
        else:
            lines.append(_fail("GOOGLE_APPS_SCRIPT_TOKEN missing or placeholder"))

    if CONTENTOPS_SHEET_ID and not _looks_placeholder(CONTENTOPS_SHEET_ID):
        lines.append(_ok("CONTENTOPS_SHEET_ID present"))
    else:
        lines.append(_fail("CONTENTOPS_SHEET_ID missing or placeholder"))

    if GOOGLE_DRIVE_FOLDER_ID and not _looks_placeholder(GOOGLE_DRIVE_FOLDER_ID):
        lines.append(_ok("GOOGLE_DRIVE_FOLDER_ID present"))
    else:
        lines.append(_fail("GOOGLE_DRIVE_FOLDER_ID missing or placeholder"))

    if slack_bot_ready:
        lines.append(_ok("SLACK_BOT_TOKEN present"))
    else:
        lines.append(_fail("SLACK_BOT_TOKEN missing or placeholder"))

    if slack_app_ready:
        lines.append(_ok("SLACK_APP_TOKEN present"))
    else:
        lines.append(_fail("SLACK_APP_TOKEN missing or placeholder"))

    authz_path = Path(AUTHZ_FILE)
    if authz_path.exists():
        lines.append(
            _ok(
                "AUTHZ_FILE found",
                f"{AUTHZ_FILE} (strict={AUTHZ_STRICT}, users={len(AUTHZ.user_roles)})",
            )
        )
        if AUTHZ.load_error:
            lines.append(_fail("AUTHZ config parse issue", AUTHZ.load_error))
        if AUTHZ_STRICT and len(AUTHZ.user_roles) == 0:
            lines.append(
                _fail(
                    "AUTHZ strict mode has no mapped users",
                    "add users in authz.yaml or set AUTHZ_ADMIN_USERS in .env",
                )
            )
        else:
            valid_user_ids = [
                uid for uid in AUTHZ.user_roles.keys() if re.match(r"^U[A-Z0-9]{8,}$", uid)
            ]
            if AUTHZ_STRICT and len(valid_user_ids) == 0:
                lines.append(
                    _fail(
                        "AUTHZ users look like placeholders",
                        "replace sample IDs with real Slack user IDs",
                    )
                )
    else:
        if AUTHZ_STRICT and len(AUTHZ.user_roles) > 0:
            lines.append(
                _ok(
                    "AUTHZ_FILE missing",
                    f"{AUTHZ_FILE} (using AUTHZ_ADMIN_USERS, users={len(AUTHZ.user_roles)})",
                )
            )
        else:
            lines.append(_fail("AUTHZ_FILE missing", AUTHZ_FILE))

    # Live checks (best effort)
    if anthropic_ready:
        if not _looks_anthropic_key(ANTHROPIC_API_KEY):
            lines.append(_fail("Anthropic API check skipped", "key format does not look like sk-ant-*"))
        else:
            try:
                import anthropic

                c = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                c.messages.create(
                    model="claude-3-5-haiku-latest",
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                )
                lines.append(_ok("Anthropic generation check passed"))
            except ModuleNotFoundError:
                lines.append(_fail("Anthropic SDK missing", "run: pip install -r requirements.txt"))
            except Exception as e:
                lines.append(_fail("Anthropic API check failed", _redact_error(e)))

    if openai_ready:
        if not _looks_openai_key(OPENAI_API_KEY):
            lines.append(_fail("OpenAI API check skipped", "key format does not look like sk-*"))
        else:
            try:
                import openai

                c = openai.OpenAI(api_key=OPENAI_API_KEY)
                c.chat.completions.create(
                    model=OPENAI_MODEL,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                )
                lines.append(_ok("OpenAI generation check passed", f"model={OPENAI_MODEL}"))
            except ModuleNotFoundError:
                lines.append(_fail("OpenAI SDK missing", "run: pip install -r requirements.txt"))
            except Exception as e:
                lines.append(_fail("OpenAI API check failed", _redact_error(e)))

    if AI_PROVIDER == "ollama":
        try:
            import openai

            c = openai.OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
            c.chat.completions.create(
                model=OLLAMA_MODEL,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            lines.append(_ok("Ollama check passed", f"model={OLLAMA_MODEL} @ {OLLAMA_BASE_URL}"))
        except ModuleNotFoundError:
            lines.append(_fail("OpenAI SDK missing", "run: pip install -r requirements.txt"))
        except Exception as e:
            lines.append(_fail(
                "Ollama check failed",
                f"{_redact_error(e)} — is Ollama running? Try: ollama serve",
            ))

    if slack_bot_ready:
        if not _looks_slack_bot_token(SLACK_BOT_TOKEN):
            lines.append(_fail("Slack auth check skipped", "bot token format does not look like xoxb-*"))
        else:
            try:
                from slack_sdk import WebClient

                client = WebClient(token=SLACK_BOT_TOKEN)
                resp = client.auth_test()
                lines.append(_ok("Slack auth valid", f"team={resp.get('team')}, user={resp.get('user')}"))
            except ModuleNotFoundError:
                lines.append(_fail("Slack SDK missing", "run: pip install -r requirements.txt"))
            except Exception as e:
                lines.append(_fail("Slack auth check failed", _redact_error(e)))

    if slack_app_ready and not _looks_slack_app_token(SLACK_APP_TOKEN):
        lines.append(_fail("Slack app token format invalid", "expected xapp-* for Socket Mode"))

    google_live_ready = (
        (service_account_mode and google_file_ready)
        or (
            apps_script_mode
            and GOOGLE_APPS_SCRIPT_URL
            and not _looks_placeholder(GOOGLE_APPS_SCRIPT_URL)
            and GOOGLE_APPS_SCRIPT_TOKEN
            and not _looks_placeholder(GOOGLE_APPS_SCRIPT_TOKEN)
        )
    )

    if google_live_ready and CONTENTOPS_SHEET_ID:
        try:
            from tools.sheets import read_tracker

            tracker = read_tracker(limit=1)
            if "error" in tracker:
                lines.append(_fail("Google Sheets read failed", tracker["error"]))
            else:
                lines.append(_ok("Google Sheets read ok", f"rows={tracker.get('count', 0)}"))
        except ModuleNotFoundError:
            lines.append(_fail("Google SDK missing", "run: pip install -r requirements.txt"))
        except Exception as e:
            lines.append(_fail("Google Sheets read failed", _redact_error(e)))

    if google_live_ready and GOOGLE_DRIVE_FOLDER_ID:
        try:
            from tools.drive import list_drive_files

            drive = list_drive_files()
            if "error" in drive:
                lines.append(_fail("Google Drive list failed", drive["error"]))
            else:
                lines.append(_ok("Google Drive list ok", f"files={len(drive.get('files', []))}"))
        except ModuleNotFoundError:
            lines.append(_fail("Google SDK missing", "run: pip install -r requirements.txt"))
        except Exception as e:
            lines.append(_fail("Google Drive list failed", _redact_error(e)))

    # Telemetry store — must be writable for the dashboard + run tracking.
    try:
        import observability
        from config import CONTENTOPS_DB

        observability.init_db()
        observability.ops_metrics(window_hours=1)
        lines.append(_ok("Telemetry store writable", CONTENTOPS_DB))
    except Exception as e:
        lines.append(_fail("Telemetry store check failed", _redact_error(e)))

    # Quality gate — verify brand rules load (guards the guardrail).
    try:
        from quality_gate import load_banned_phrases, load_valid_buckets

        phrases = load_banned_phrases()
        buckets = load_valid_buckets()
        if phrases and buckets:
            lines.append(_ok("Quality gate ready", f"{len(phrases)} banned phrases, {len(buckets)} buckets"))
        else:
            lines.append(_fail("Quality gate rules empty", "check contentops/brand/ markdown"))
    except Exception as e:
        lines.append(_fail("Quality gate check failed", _redact_error(e)))

    # Tracker schema contract + active storage backend.
    try:
        import schema
        from tools.tracker_backends import resolve_backend_name

        lines.append(_ok(
            "Tracker schema loaded",
            f"v{schema.schema_version()}, {len(schema.column_names())} columns, "
            f"backend={resolve_backend_name()}",
        ))
    except Exception as e:
        lines.append(_fail("Tracker schema check failed", _redact_error(e)))

    # Active adapters (the platform-agnostic edges).
    try:
        from tools.source_backends import resolve_source_name

        lines.append(_ok("Knowledge source backend", resolve_source_name()))
    except Exception as e:
        lines.append(_fail("Source backend check failed", _redact_error(e)))

    return "\n".join(lines)

"""
ContentOps Agent — entry point.

CLI usage:
  python main.py draft-from-idea "your idea text"
  python main.py plan-week
  python main.py repurpose-blog "google_doc_id_or_url"
  python main.py update-status CNT-001 Approved
  python main.py google-email
  python main.py doctor
  python main.py bot                          # start Slack Socket Mode

Slack bot usage (after `python main.py bot`):
  @contentops draft-from-idea <idea>
  @contentops plan-week
  @contentops repurpose-blog <doc_url>
  @contentops update-status <idea_id> <status>
  @contentops whoami
  @contentops help
"""

import sys
import os
import re
from datetime import datetime, timezone

# Allow imports from agent/ directory
sys.path.insert(0, os.path.dirname(__file__))

from prompts import (
    build_draft_from_idea_prompt,
    build_weekly_plan_prompt,
    build_repurpose_blog_prompt,
)
from doctor import run_doctor
from authz import AUTHZ


# ─── Command handlers ────────────────────────────────────────────────────────

def cmd_draft_from_idea(idea: str) -> str:
    from contentops_agent import run
    prompt = build_draft_from_idea_prompt(idea)
    return run(prompt)


def cmd_plan_week() -> str:
    from contentops_agent import run
    prompt = build_weekly_plan_prompt()
    return run(prompt)


def cmd_repurpose_blog(doc_id: str) -> str:
    from contentops_agent import run
    prompt = build_repurpose_blog_prompt(doc_id)
    return run(prompt)


def cmd_update_status(idea_id: str, status: str) -> str:
    from tools.sheets import write_tracker
    result = write_tracker(idea_id, {"status": _normalize_status(status)})
    if "error" in result:
        return f"Error: {result['error']}"
    return f"Updated {idea_id} → {_normalize_status(status)}"


def cmd_help() -> str:
    return (
        "*ContentOps Agent — available commands:*\n"
        "• `@contentops draft-from-idea <idea>` — draft a LinkedIn post from an idea\n"
        "• `@contentops plan-week` — generate this week's content plan\n"
        "• `@contentops repurpose-blog <doc_url>` — repurpose a Google Doc into posts\n"
        "• `@contentops update-status <idea_id> <status>` — update tracker row status\n"
        "• `@contentops whoami` — show your Slack user ID for role mapping\n"
        "• `@contentops help` — show this message\n\n"
        "CLI only: `python main.py doctor` — run credential and connectivity checks\n\n"
        "CLI only: `python main.py google-email` — show service account email\n\n"
        "Status values: `new` | `needs_review` | `Approved` | `Needs Revision` | `Rejected` | `published`"
    )


def _normalize_status(status: str) -> str:
    raw = status.strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "approved": "Approved",
        "approve": "Approved",
        "needs_revision": "Needs Revision",
        "need_revision": "Needs Revision",
        "revise": "Needs Revision",
        "rejected": "Rejected",
        "reject": "Rejected",
        "needs_review": "needs_review",
        "new": "new",
        "published": "published",
        "scheduled": "scheduled",
    }
    return mapping.get(raw, status)


def _parse_and_run(command: str, args: list) -> str:
    """Parse a command string and dispatch to the right handler."""
    if command == "draft-from-idea":
        if not args:
            return "Usage: draft-from-idea <idea text>"
        return cmd_draft_from_idea(" ".join(args))

    if command == "plan-week":
        return cmd_plan_week()

    if command == "repurpose-blog":
        if not args:
            return "Usage: repurpose-blog <google_doc_id_or_url>"
        return cmd_repurpose_blog(args[0])

    if command == "update-status":
        if len(args) < 2:
            return "Usage: update-status <idea_id> <status>"
        return cmd_update_status(args[0], args[1])

    if command == "help":
        return cmd_help()

    if command == "doctor":
        return run_doctor()

    if command == "google-email":
        return cmd_google_email()

    return f"Unknown command: `{command}`. Try `help`."


def cmd_google_email() -> str:
    import json
    from pathlib import Path
    from config import GOOGLE_SERVICE_ACCOUNT_FILE

    path = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
    if not GOOGLE_SERVICE_ACCOUNT_FILE or not path.exists():
        return f"Google service account file not found: {GOOGLE_SERVICE_ACCOUNT_FILE}"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Could not read service account JSON: {e}"

    email = data.get("client_email", "")
    if not email:
        return "No client_email found in service account JSON."
    return f"Share the Google Sheet and Drive folder with this service account email:\n{email}"


# ─── Slack Socket Mode bot ────────────────────────────────────────────────────

def start_slack_bot():
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    from config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN

    app = App(token=SLACK_BOT_TOKEN)

    @app.event("app_mention")
    def handle_mention(event, say, client):
        """Handle @contentops <command> mentions."""
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        channel = event["channel"]
        user_id = event.get("user", "")

        # Strip the bot mention prefix (<@UXXXXXXXXX>)
        parts = text.split()[1:]  # drop the @mention token
        if not parts:
            say(text=cmd_help(), thread_ts=thread_ts)
            return

        command = parts[0].lower()
        args = parts[1:]

        if command == "whoami":
            say(text=f"Your Slack user ID is `{user_id}`", thread_ts=thread_ts)
            return

        if not AUTHZ.can_run_command(user_id, command):
            denial = AUTHZ.auth_message(user_id, command)
            if denial:
                say(text=denial, thread_ts=thread_ts)
                return

        # Acknowledge immediately so Slack doesn't time out
        say(text=f"On it — running `{command}`...", thread_ts=thread_ts)

        result = _parse_and_run(command, args)

        # Post result back in thread
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=result,
            mrkdwn=True,
        )

    @app.event("message")
    def handle_approval_reply(event, client):
        """
        Handle approve/revise/reject replies in review threads.
        The agent posts drafts with a thread_ts; reviewers reply in that thread.
        """
        if event.get("subtype") == "bot_message":
            return

        text = event.get("text", "").strip().lower()
        thread_ts = event.get("thread_ts")
        channel = event.get("channel")
        user_id = event.get("user", "")

        if not thread_ts:
            return  # not a thread reply

        # Only act on clear approval keywords
        if text.startswith("approve"):
            if not AUTHZ.can_review(user_id, "approve"):
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=AUTHZ.auth_message(user_id, "approve"),
                    mrkdwn=True,
                )
                return
            _handle_approval(channel, thread_ts, "Approved", "", client, user_id)
        elif text.startswith("revise:"):
            if not AUTHZ.can_review(user_id, "revise"):
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=AUTHZ.auth_message(user_id, "revise"),
                    mrkdwn=True,
                )
                return
            notes = event.get("text", "")[7:].strip()
            _handle_approval(channel, thread_ts, "Needs Revision", notes, client, user_id)
        elif text.startswith("reject:"):
            if not AUTHZ.can_review(user_id, "reject"):
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=AUTHZ.auth_message(user_id, "reject"),
                    mrkdwn=True,
                )
                return
            reason = event.get("text", "")[7:].strip()
            _handle_approval(channel, thread_ts, "Rejected", reason, client, user_id)

    def _handle_approval(channel, thread_ts, status, notes, client, reviewer_user_id):
        """Update the tracker and confirm in thread when a reviewer acts."""
        from tools.sheets import write_tracker

        try:
            # The idea_id was embedded in the original message text — retrieve it
            history = client.conversations_replies(channel=channel, ts=thread_ts)
            original_text = history["messages"][0].get("text", "")
        except Exception as e:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"Could not read thread history: {e}",
                mrkdwn=True,
            )
            return

        idea_id = _extract_idea_id(original_text)
        if idea_id:
            fields = {"status": status}
            fields["reviewer"] = reviewer_user_id
            fields["review_action_ts"] = datetime.now(timezone.utc).isoformat()
            if notes:
                fields["review_notes"] = notes
            update = write_tracker(idea_id, fields)
            if "error" in update:
                reply = f"Could not update tracker for `{idea_id}`: {update['error']}"
            else:
                reply = f"Tracker updated — `{idea_id}` → `{status}`"
                if notes:
                    reply += f"\nNotes: {notes}"
        else:
            reply = f"Status recorded: `{status}`. (Could not extract idea_id to update tracker — update manually.)"

        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts, text=reply, mrkdwn=True
        )

    def _extract_idea_id(text: str) -> str:
        # Common formats: "Idea: CNT-T1", "`IDEA_2026_001`", "idea_id=CNT-001"
        patterns = [
            r"idea[_\s-]*id[:=\s`]*([A-Za-z0-9_-]+)",
            r"idea[:=\s`]*([A-Za-z0-9_-]+)",
            r"`([A-Za-z]{2,10}[-_][A-Za-z0-9_-]+)`",
            r"\b([A-Za-z]{2,10}[-_][A-Za-z0-9_-]+)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    print("ContentOps bot starting in Socket Mode...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


# ─── CLI entry ────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    command = args[0].lower()

    if command == "bot":
        start_slack_bot()
        return

    result = _parse_and_run(command, args[1:])
    print(result)


if __name__ == "__main__":
    main()

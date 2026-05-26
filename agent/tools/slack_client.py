from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SLACK_BOT_TOKEN, SLACK_REVIEW_CHANNEL

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def _client() -> WebClient:
    return WebClient(token=SLACK_BOT_TOKEN)


def post_to_slack(text: str, idea_id: str = "") -> dict:
    """Post a draft or plan to the Slack review channel. Returns thread_ts."""
    try:
        client = _client()
        header = f"*ContentOps Review* {f'— `{idea_id}`' if idea_id else ''}\n\n"
        response = client.chat_postMessage(
            channel=SLACK_REVIEW_CHANNEL,
            text=header + text,
            mrkdwn=True,
        )
        thread_ts = response["ts"]
        # Post instructions in the thread so reviewer knows what to do
        client.chat_postMessage(
            channel=SLACK_REVIEW_CHANNEL,
            thread_ts=thread_ts,
            text=(
                "Reply in this thread to action this draft:\n"
                "• `approve` — mark as approved, update tracker\n"
                "• `revise: <your notes>` — send back for revision\n"
                "• `reject: <reason>` — discard this draft"
            ),
            mrkdwn=True,
        )
        return {"thread_ts": thread_ts, "channel": SLACK_REVIEW_CHANNEL}
    except SlackApiError as e:
        return {"error": e.response["error"]}


def read_slack_thread(thread_ts: str, channel: str = "") -> dict:
    """Read all replies in a Slack thread. Returns messages with user and text."""
    try:
        client = _client()
        ch = channel or SLACK_REVIEW_CHANNEL
        response = client.conversations_replies(channel=ch, ts=thread_ts)
        messages = response.get("messages", [])
        # Skip the first message (original post) and the instruction reply
        replies = [
            {"user": m.get("user", ""), "text": m.get("text", ""), "ts": m.get("ts")}
            for m in messages[2:]  # skip original + instructions
        ]
        return {"thread_ts": thread_ts, "replies": replies}
    except SlackApiError as e:
        return {"error": e.response["error"]}


def post_thread_reply(thread_ts: str, text: str, channel: str = "") -> dict:
    """Post a reply into an existing Slack thread (e.g., confirmation message)."""
    try:
        client = _client()
        ch = channel or SLACK_REVIEW_CHANNEL
        response = client.chat_postMessage(
            channel=ch, thread_ts=thread_ts, text=text, mrkdwn=True
        )
        return {"ts": response["ts"]}
    except SlackApiError as e:
        return {"error": e.response["error"]}


def get_channel_id(channel_name: str) -> str:
    """Resolve a channel name like #contentops-review to its ID."""
    try:
        client = _client()
        name = channel_name.lstrip("#")
        cursor = None
        while True:
            result = client.conversations_list(
                types="public_channel,private_channel",
                cursor=cursor,
                limit=200,
            )
            for ch in result.get("channels", []):
                if ch["name"] == name:
                    return ch["id"]
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return ""
    except SlackApiError:
        return ""

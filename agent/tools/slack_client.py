import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SLACK_BOT_TOKEN, SLACK_REVIEW_CHANNEL
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_SECTION_LIMIT = 3000  # Slack Block Kit max chars per section text


def _client() -> WebClient:
    return WebClient(token=SLACK_BOT_TOKEN)


def _chunk_text(text: str, max_len: int = _SECTION_LIMIT) -> list:
    """Split text into chunks that fit in one section block.

    Splits at paragraph boundaries first; if a single paragraph still exceeds
    max_len it is hard-split at the character limit.
    """
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n\n"):
        # Hard-split paragraphs that are themselves too long
        while len(para) > max_len:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.append(para[:max_len])
            para = para[max_len:]
        if len(current) + len(para) + 2 > max_len:
            if current:
                chunks.append(current.strip())
            current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current:
        chunks.append(current.strip())
    return chunks or [text[:max_len]]


def _build_draft_blocks(text: str, idea_id: str) -> list:
    """Block Kit layout for a draft that needs approval — includes action buttons."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "ContentOps Draft", "emoji": True},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"ID: `{idea_id}` • Status: *Needs Review*"}
            ],
        },
        {"type": "divider"},
    ]
    for chunk in _chunk_text(text):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
    blocks += [
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": f"approval_{idea_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_draft",
                    "value": idea_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Revision", "emoji": True},
                    "action_id": "revise_draft",
                    "value": idea_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "reject_draft",
                    "value": idea_id,
                },
            ],
        },
    ]
    return blocks


def _build_plan_blocks(text: str) -> list:
    """Block Kit layout for a plan or general response — no approval buttons."""
    blocks: list = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "ContentOps", "emoji": True},
        }
    ]
    # Split on markdown heading boundaries so each section becomes a block
    sections = re.split(r"\n(?=#{1,3} |\*\*[A-Z]|\d+\.\s+\*\*)", text)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        blocks.append({"type": "divider"})
        for chunk in _chunk_text(section):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
    return blocks


def post_to_slack(text: str, idea_id: str = "") -> dict:
    """Post a draft or plan to the Slack review channel. Returns thread_ts.

    If idea_id is provided the message includes approve / revise / reject buttons.
    Otherwise it renders as a formatted plan with sections.
    """
    try:
        client = _client()
        blocks = _build_draft_blocks(text, idea_id) if idea_id else _build_plan_blocks(text)
        # Slack requires a fallback `text` for notifications / accessibility
        fallback = f"ContentOps {'Draft' if idea_id else 'Update'}{f' — {idea_id}' if idea_id else ''}"
        response = client.chat_postMessage(
            channel=SLACK_REVIEW_CHANNEL,
            blocks=blocks,
            text=fallback,
        )
        return {"thread_ts": response["ts"], "channel": SLACK_REVIEW_CHANNEL}
    except SlackApiError as e:
        return {"error": e.response["error"]}


def update_draft_message_status(channel: str, ts: str, status: str, reviewer_id: str) -> None:
    """Replace the action buttons on a draft message with a final status badge."""
    status_icon = {"Approved": "✅", "Needs Revision": "✏️", "Rejected": "❌"}.get(status, "")
    try:
        client = _client()
        history = client.conversations_history(channel=channel, latest=ts, limit=1, inclusive=True)
        original_blocks = history["messages"][0].get("blocks", [])
        # Drop the actions block; append a context block with the outcome
        new_blocks = [b for b in original_blocks if b.get("type") != "actions"]
        new_blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"{status_icon} *{status}* by <@{reviewer_id}>",
                    }
                ],
            }
        )
        client.chat_update(channel=channel, ts=ts, blocks=new_blocks, text=f"Draft {status}")
    except Exception:
        pass  # Non-critical — thread confirmation already sent


def read_slack_thread(thread_ts: str, channel: str = "") -> dict:
    """Read all replies in a Slack thread. Returns messages with user and text."""
    try:
        client = _client()
        ch = channel or SLACK_REVIEW_CHANNEL
        response = client.conversations_replies(channel=ch, ts=thread_ts)
        messages = response.get("messages", [])
        replies = [
            {"user": m.get("user", ""), "text": m.get("text", ""), "ts": m.get("ts")}
            for m in messages[1:]  # skip the original post
        ]
        return {"thread_ts": thread_ts, "replies": replies}
    except SlackApiError as e:
        return {"error": e.response["error"]}


def post_thread_reply(thread_ts: str, text: str, channel: str = "") -> dict:
    """Post a reply into an existing Slack thread."""
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

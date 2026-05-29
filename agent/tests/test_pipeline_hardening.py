"""Tests for the hardened approval pipeline + gate enforcement at the boundary."""

import main
from tools import slack_client

# ─── Event de-duplication ─────────────────────────────────────────────────────

def test_duplicate_event_detected():
    assert main._is_duplicate_event("EvtABC") is False  # first sighting
    assert main._is_duplicate_event("EvtABC") is True   # redelivery
    assert main._is_duplicate_event("EvtDEF") is False


def test_blank_event_id_never_duplicate():
    assert main._is_duplicate_event("") is False
    assert main._is_duplicate_event("") is False


# ─── Draft-thread verification ────────────────────────────────────────────────

def test_real_draft_via_block_id():
    msg = {"bot_id": "B1", "blocks": [{"type": "actions", "block_id": "approval_CNT-1"}]}
    assert main._is_contentops_draft(msg, bot_id="B1") is True


def test_real_draft_via_fallback_text():
    msg = {"bot_id": "B1", "text": "ContentOps Draft — CNT-1", "blocks": []}
    assert main._is_contentops_draft(msg, bot_id="B1") is True


def test_human_message_is_not_a_draft():
    msg = {"user": "U1", "text": "approve JIRA-1234 please", "blocks": []}
    assert main._is_contentops_draft(msg, bot_id="B1") is False


def test_other_bot_message_is_not_our_draft():
    msg = {"bot_id": "B2", "blocks": [{"block_id": "approval_X"}]}
    assert main._is_contentops_draft(msg, bot_id="B1") is False


# ─── Quality gate blocks at the Slack boundary ────────────────────────────────

def test_post_to_slack_blocks_bad_draft_without_calling_slack(monkeypatch):
    # If the gate fails, no Slack client should ever be constructed.
    def _boom():
        raise AssertionError("Slack should not be called for a blocked draft")

    monkeypatch.setattr(slack_client, "_client", _boom)
    result = slack_client.post_to_slack("too short", idea_id="CNT-9", bucket="")
    assert result.get("blocked") is True
    assert result["error"] == "quality_gate_failed"
    assert any(v["rule"] == "bucket_missing" for v in result["violations"])

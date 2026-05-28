"""
ContentOps Agent — agentic loop powered by Claude (primary), OpenAI, or Ollama (local).

Claude handles: strategy, narrative, founder voice, long-form reasoning.
OpenAI handles: structured JSON extraction, classification (when configured).
Ollama: local models for testing without API costs (set AI_PROVIDER=ollama).
"""

import json
import logging
from typing import Any

import anthropic
import openai
from config import (
    AI_PROVIDER,
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from prompts import build_system_prompt
from tools.drive import list_drive_files, read_drive_doc
from tools.repo_tools import list_repo_files, read_repo_file
from tools.sheets import append_idea, read_tracker, write_tracker
from tools.slack_client import post_to_slack, read_slack_thread

log = logging.getLogger(__name__)

# Tool definitions exposed to the model
TOOLS = [
    {
        "name": "read_tracker",
        "description": (
            "Read rows from the Google Sheets content tracker. "
            "Use to check pipeline, published posts, and performance signals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: new, needs_review, Approved, Needs Revision, Rejected, published. Omit for all rows.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default 30).",
                },
            },
        },
    },
    {
        "name": "write_tracker",
        "description": "Update fields on an existing tracker row identified by Content ID. The parameter is named idea_id for backwards compatibility.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string", "description": "The Content ID to update, e.g. CNT-2026-06-29-026."},
                "fields": {
                    "type": "object",
                    "description": (
                        "Fields to update. Common keys: status, title, draft_text, "
                        "hook, bucket, review_notes, publish_date."
                    ),
                },
            },
            "required": ["idea_id", "fields"],
        },
    },
    {
        "name": "append_idea",
        "description": "Add or update a tracker row. Use a stable Content ID as idea_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string", "description": "Stable Content ID, e.g. CNT-2026-06-29-026."},
                "title": {"type": "string"},
                "bucket": {"type": "string", "description": "One of the 5 content buckets."},
                "raw_input": {"type": "string", "description": "The source idea or notes."},
                "source_type": {
                    "type": "string",
                    "description": "founder_note | blog | workflow_lesson | ai_news | manual",
                },
                "status": {"type": "string", "description": "new | needs_review"},
            },
            "required": ["idea_id", "title", "bucket", "raw_input"],
        },
    },
    {
        "name": "read_drive_doc",
        "description": "Read the text content of a Google Doc or Drive file by ID or URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Google Doc/Drive file ID or full URL."},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "list_drive_files",
        "description": "List files in the configured Drive source folder (blogs, notes, transcripts).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional name filter, e.g. 'founder' or 'blog'.",
                },
            },
        },
    },
    {
        "name": "read_repo_file",
        "description": (
            "Read a file from this repository by relative path. "
            "Use to fetch brand assets, examples, templates, or prompts not already in context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from repo root, e.g. contentops/examples/hooks.md",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_repo_files",
        "description": "List files under a repo directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory relative to repo root (default: contentops).",
                },
            },
        },
    },
    {
        "name": "post_to_slack",
        "description": (
            "Post a draft, plan, or analysis to the Slack review channel. "
            "Returns thread_ts — save it to later read approval replies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Full message text (markdown supported)."},
                "idea_id": {"type": "string", "description": "Idea ID this relates to (optional)."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "read_slack_thread",
        "description": "Read replies in a Slack thread. Use to check for approve/revise/reject decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_ts": {"type": "string", "description": "Thread timestamp from post_to_slack."},
                "channel": {"type": "string", "description": "Channel ID (uses review channel if omitted)."},
            },
            "required": ["thread_ts"],
        },
    },
]


def _dispatch_tool(name: str, inputs: dict) -> Any:
    """Route tool calls, filtering args and filling in safe defaults.

    Smaller models (Ollama) sometimes pass wrong kwargs or omit required ones.
    We strip unexpected args and provide fallbacks so the agentic loop never
    crashes on a TypeError — the model can see the result and continue.
    """
    def _only(d: dict, *keys) -> dict:
        return {k: v for k, v in d.items() if k in keys}

    try:
        if name == "read_tracker":
            return read_tracker(**_only(inputs, "status", "limit"))

        if name == "write_tracker":
            return write_tracker(**_only(inputs, "idea_id", "fields"))

        if name == "append_idea":
            f = _only(inputs, "idea_id", "title", "bucket", "raw_input", "source_type", "status")
            # Fill missing required fields so the model doesn't hard-fail
            if "raw_input" not in f:
                f["raw_input"] = f.get("title", inputs.get("hook", ""))
            if "title" not in f:
                f["title"] = str(f.get("raw_input", ""))[:80]
            if "bucket" not in f:
                f["bucket"] = "Founder Notes"
            if "idea_id" not in f:
                from datetime import datetime, timezone
                f["idea_id"] = f"CNT-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}"
            return append_idea(**f)

        if name == "read_drive_doc":
            return read_drive_doc(**_only(inputs, "doc_id"))

        if name == "list_drive_files":
            return list_drive_files(**_only(inputs, "query"))

        if name == "read_repo_file":
            return read_repo_file(**_only(inputs, "path"))

        if name == "list_repo_files":
            return list_repo_files(**_only(inputs, "directory"))

        if name == "post_to_slack":
            return post_to_slack(**_only(inputs, "text", "idea_id"))

        if name == "read_slack_thread":
            return read_slack_thread(**_only(inputs, "thread_ts", "channel"))

        return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        # Return error as data so the agentic loop can continue
        return {"error": f"Tool '{name}' failed: {e}. Check inputs and retry."}


MAX_TOOL_ITERATIONS = 20  # prevent runaway loops on repeated tool failures


def run_agent_claude(user_prompt: str) -> str:
    """Agentic loop using Claude with tool_use."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is missing")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system = build_system_prompt()
    messages = [{"role": "user", "content": user_prompt}]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # Collect any text output for logging
        text_output = ""
        for block in response.content:
            if hasattr(block, "text"):
                text_output += block.text

        if response.stop_reason == "end_turn":
            return text_output

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _dispatch_tool(block.name, block.input)
                    log.info("tool %s → %s", block.name, json.dumps(result)[:200])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason — return what we have
            return text_output or f"[stopped: {response.stop_reason}]"

    return "[error] Agent hit the tool iteration limit — repeated tool failures. Check credentials and tracker connectivity."


def run_agent_openai(user_prompt: str) -> str:
    """Agentic loop using OpenAI with function calling."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    system = build_system_prompt()

    # Convert Anthropic tool format to OpenAI function format
    openai_tools = [
        {"type": "function", "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        }}
        for t in TOOLS
    ]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            tools=openai_tools,
            messages=messages,
        )

        choice = response.choices[0]
        msg = choice.message
        messages.append(msg)

        if choice.finish_reason == "stop":
            return msg.content or ""

        if choice.finish_reason == "tool_calls":
            for tc in msg.tool_calls:
                inputs = json.loads(tc.function.arguments)
                result = _dispatch_tool(tc.function.name, inputs)
                log.info("tool %s → %s", tc.function.name, json.dumps(result)[:200])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
        else:
            return msg.content or f"[stopped: {choice.finish_reason}]"

    return "[error] Agent hit the tool iteration limit — repeated tool failures. Check credentials and tracker connectivity."


def run_agent_ollama(user_prompt: str) -> str:
    """Agentic loop using a local Ollama model via its OpenAI-compatible API."""
    client = openai.OpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key="ollama",  # required by SDK but unused by Ollama
    )
    system = build_system_prompt()

    openai_tools = [
        {"type": "function", "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        }}
        for t in TOOLS
    ]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            tools=openai_tools,
            messages=messages,
        )

        choice = response.choices[0]
        msg = choice.message
        messages.append(msg)

        if choice.finish_reason == "stop":
            return msg.content or ""

        if choice.finish_reason == "tool_calls":
            for tc in msg.tool_calls:
                inputs = json.loads(tc.function.arguments)
                result = _dispatch_tool(tc.function.name, inputs)
                log.info("tool %s → %s", tc.function.name, json.dumps(result)[:200])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
        else:
            return msg.content or f"[stopped: {choice.finish_reason}]"

    return "[error] Agent hit the tool iteration limit — repeated tool failures. Check credentials and tracker connectivity."


def run(user_prompt: str) -> str:
    """Entry point — routes to the configured AI provider."""
    provider = (AI_PROVIDER or "openai").strip().lower()

    if provider == "ollama":
        log.info("provider: ollama (%s @ %s)", OLLAMA_MODEL, OLLAMA_BASE_URL)
        return run_agent_ollama(user_prompt)

    if provider == "openai":
        try:
            return run_agent_openai(user_prompt)
        except Exception as primary_error:
            if ANTHROPIC_API_KEY:
                log.warning("OpenAI failed, falling back to Claude: %s", primary_error)
                try:
                    return run_agent_claude(user_prompt)
                except Exception as fallback_error:
                    raise RuntimeError(
                        "OpenAI failed and Claude fallback also failed. "
                        f"OpenAI error: {primary_error}. "
                        f"Claude error: {fallback_error}."
                    ) from fallback_error
            raise

    try:
        return run_agent_claude(user_prompt)
    except Exception as primary_error:
        if OPENAI_API_KEY:
            log.warning("Claude failed, falling back to OpenAI: %s", primary_error)
            try:
                return run_agent_openai(user_prompt)
            except Exception as fallback_error:
                raise RuntimeError(
                    "Claude failed and OpenAI fallback also failed. "
                    f"Claude error: {primary_error}. "
                    f"OpenAI error: {fallback_error}."
                ) from fallback_error
        raise

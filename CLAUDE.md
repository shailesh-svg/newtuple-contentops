# Newtuple ContentOps — Claude Code Project Context

## What This Is

An agentic content operating system for Newtuple.

The system converts organizational knowledge (founder notes, blogs, workflow learnings, client observations) into repeatable strategic content and GTM intelligence.

This is NOT a content scheduler or LinkedIn automation tool. It is a reasoning layer over Newtuple's operational knowledge.

## Repo Structure

```
contentops/          control plane — brand assets, prompts, templates, examples
agent/               the Python agent — run this to operate the system
  main.py            CLI entry + Slack Socket Mode bot
  contentops_agent.py  agentic loop (Claude primary, OpenAI secondary)
  prompts.py         loads brand context from contentops/ markdown files
  config.py          all env vars
  tools/
    sheets.py        Google Sheets read/write
    drive.py         Google Drive read
    repo_tools.py    read brand assets from this repo
    slack_client.py  Slack post + thread read
```

## Agent Commands

```bash
# Run the Slack bot (primary mode)
python agent/main.py bot

# One-shot CLI commands
python agent/main.py draft-from-idea "idea text here"
python agent/main.py plan-week
python agent/main.py repurpose-blog "doc_id_or_url"
python agent/main.py update-status CNT-001 Approved
python agent/main.py doctor
```

## Key Design Rules

1. Claude is the primary reasoning model. OpenAI is secondary (structured output, classification).
2. The agent NEVER publishes. It drafts, recommends, and updates the tracker only.
3. Human approval via Slack is mandatory before status moves to `Approved`.
4. Brand voice lives in `contentops/brand/` — always load it before generating.
5. Tracker operations go through Google Sheets only.

## Brand Context Files (Load Before Generating)

- `contentops/brand/voice-guide.md` — tone, style, post skeleton
- `contentops/brand/newtuple-narrative-engine.md` — recurring beliefs, objections, lessons
- `contentops/brand/content-buckets.md` — 5 content categories
- `contentops/brand/banned-phrases.md` — never use these
- `contentops/prompts/contentops-agent-system-prompt.md` — agent system prompt

## Quality Gate (Required Before Posting to Slack)

- voice score >= 8/10
- no banned phrases
- concrete enterprise implication included
- one actionable takeaway
- bucket assigned

## Environment Setup

Copy `agent/.env.example` to `agent/.env` and fill in all values before running.

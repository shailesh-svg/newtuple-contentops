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
    slack_client.py  Slack post + thread read (enforces the quality gate)
  quality_gate.py    deterministic content checks (banned phrases, bucket, length, voice)
  observability.py   SQLite run/event telemetry store + metrics
  dashboard.py       read-only Flask dashboard for non-technical members
  schema.py          loads the canonical tracker contract (single source of truth)
  tools/
    sheets.py        tracker facade — applies schema, delegates to a backend
    tracker_backends.py  pluggable storage: Sheets / Apps Script / JSON file
contentops/schema/tracker.schema.json   the tracker contract (fields, aliases, statuses)
```

See `ARCHITECTURE.md` for the schema contract + how to plug in a new storage backend.

## Agent Commands

```bash
# Run the Slack bot (primary mode)
python agent/main.py bot

# One-shot CLI commands
python agent/main.py draft-from-idea "idea text here"
python agent/main.py plan-week
python agent/main.py repurpose-blog "doc_id_or_url"
python agent/main.py update-status CNT-001 Approved
python agent/main.py doctor                 # checks creds, telemetry store, quality gate
python agent/main.py dashboard              # read-only web dashboard (http://localhost:8080)
```

## Key Design Rules

1. Claude is the primary reasoning model. OpenAI is secondary (structured output, classification).
2. The agent NEVER publishes. It drafts, recommends, and updates the tracker only.
3. Human approval via Slack is mandatory before status moves to `Approved`.
4. Brand voice lives in `contentops/brand/` — always load it before generating.
5. Tracker operations go through the `tools/sheets.py` facade, which applies the
   canonical schema (`contentops/schema/tracker.schema.json`) and delegates to
   the configured storage backend. Never hardcode column names — use `schema.py`.

## Brand Context Files (Load Before Generating)

- `contentops/brand/voice-guide.md` — tone, style, post skeleton
- `contentops/brand/newtuple-narrative-engine.md` — recurring beliefs, objections, lessons
- `contentops/brand/content-buckets.md` — 5 content categories
- `contentops/brand/banned-phrases.md` — never use these
- `contentops/prompts/contentops-agent-system-prompt.md` — agent system prompt

## Quality Gate (ENFORCED IN CODE before posting to Slack)

Implemented in `agent/quality_gate.py` and run inside `post_to_slack` for every
draft. A failing draft is **not posted** — violations are returned to the agent
to revise and retry. See `OBSERVABILITY.md` for the full rule table.

Blocking rules: no banned phrases · bucket assigned + valid · length within
bounds · voice score >= 8/10 (when provided).
Warnings (non-blocking, heuristic): concrete enterprise implication · actionable
takeaway · missing self-score.

When posting a draft, the agent must pass `idea_id`, `bucket`, and `voice_score`
to `post_to_slack`.

## Environment Setup

Copy `agent/.env.example` to `agent/.env` and fill in all values before running.

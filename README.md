# Newtuple Agentic ContentOps

This repository is the control plane for Newtuple's Agentic ContentOps system.

It is designed to support an agentic loop:

1. Retrieve context across MCP-accessible sources
2. Reason about what to create and why
3. Draft brand-aligned assets
4. Route human review
5. Track outcomes and improve narrative coverage

Primary focus: operational insight capture and narrative intelligence, not generic content generation.

## Current MVP

The repo now supports an agent-first operating loop:

`Slack @contentops -> Python agent -> Google Apps Script -> Google Sheets/Drive -> Slack review`

The bot can be used before LLM provider keys are fixed for:

- `@contentops whoami`
- `@contentops help`
- Google Sheets/Drive connectivity checks via `python main.py doctor`
- manual starter content review using `contentops/templates/week-1-starter-content.csv`

LLM commands such as `plan-week`, `draft-from-idea`, and `repurpose-blog` require a valid `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`.

## Primary Loop

`ContentOps Agent -> MCP Retrieval -> Draft/Plan -> Human Review -> Tracker Update`

Operational review loop:

`Tracker row -> Slack review -> approve/revise/reject -> Tracker status update`

See [contentops/README.md](contentops/README.md) for system setup and [architecture.md](contentops/agent/architecture.md) for the layer model.

## Fast Start

1. Clone the repo.
2. Follow [agent/setup.md](agent/setup.md).
3. Copy `agent/.env.example` to `agent/.env` and fill local credentials.
4. Copy `agent/authz.example.yaml` to `agent/authz.yaml` and add Slack user IDs.
5. Run:

```bash
cd agent
source .venv/bin/activate
python main.py doctor
```

6. Start the bot:

```bash
python main.py bot
```

7. In Slack, invite the bot to the review channel and test:

```text
/invite @contentops
@contentops whoami
@contentops help
```

## Starter Content

While provider keys are pending, use:

- `contentops/templates/week-1-starter-content.csv`

Import or paste those rows into the Google Sheets tracker. They already match the tracker schema and are set to `needs_review`.

## Important Security Rules

- Never commit `agent/.env`.
- Never commit provider keys, Slack tokens, Google Apps Script tokens, or downloaded Google credentials.
- `agent/authz.yaml` is intentionally local-only because it contains workspace-specific Slack user IDs.
- Commit changes to examples, templates, prompts, workflows, and docs only.

## Main References

- Agent runtime setup: [agent/setup.md](agent/setup.md)
- ContentOps control plane: [contentops/README.md](contentops/README.md)
- Google Apps Script bridge: [agent/google-apps-script/README.md](agent/google-apps-script/README.md)

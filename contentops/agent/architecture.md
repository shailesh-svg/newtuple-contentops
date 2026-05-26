# Agentic ContentOps Architecture

## Core Direction

This system is agent-first, not workflow-first.

Use the ContentOps Agent as the reasoning engine.

Use MCP tools as the retrieval layer.

Use automation only for optional operational movement.

## Layer Model

## 1) Knowledge Layer (MCP-accessible)

Sources:

- GitHub repo (control plane assets)
- Google Sheets (live tracker)
- Google Drive/Docs (blogs, transcripts, notes, decks)
- Slack (discussion context, reviewer signals)
- Website/blog pages (fresh external content)

## 2) ContentOps Agent (Reasoning Layer)

Responsibilities:

- gather context dynamically
- plan weekly content by bucket gaps
- draft in Newtuple voice
- review and improve quality
- repurpose high-signal sources
- recommend campaigns and narrative priorities

## 3) Operational Layer (Optional)

Tools:

- n8n
- Make
- scripts
- manual actions

Responsibilities:

- status updates
- notifications
- scheduling handoffs

## Control-Plane Rule

GitHub repo stores stable strategic assets:

- prompts
- templates
- examples
- narrative engine
- schemas
- workflow specs

Daily operations should remain in Sheet/Drive/Slack.

## MVP Principle

Start with agentic retrieval + reasoning.

Add orchestration only when manual effort becomes a bottleneck.

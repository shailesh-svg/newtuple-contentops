# ContentOps System

## Purpose

This folder contains the working system for Newtuple's agentic publishing engine.

The system is optimized for:

- workflow-first AI positioning
- enterprise operations framing
- founder-led practical insight
- production-readiness narratives

## System Layers

1. Control Plane (GitHub Repo)
- curated examples, hooks, patterns, and reusable narrative assets
- brand voice rules, prompts, templates, and tracker schema
- workflow specs and approval logic
- locations: `contentops/brand`, `contentops/prompts`, `contentops/examples`, `contentops/templates`, `contentops/workflows`

2. Knowledge Layer (Operational Sources)
- Google Sheets tracker
- Google Drive/Docs source material
- Slack review and discussion signals
- website/blog sources

3. ContentOps Agent Layer
- context retrieval orchestration via MCP
- planning, drafting, review intelligence, and gap detection
- location: `contentops/agent`

4. Optional Automation Layer
- n8n/Make/scripts for status movement and notifications
- location: `contentops/workflows`

5. Intelligence Layer
- performance fields and learning loop spec
- location: `contentops/analytics`

## Recommended Rollout (Agent-First)

1. Build the tracker in Google Sheets using `templates/content-calendar-template.csv`.
2. If LLM provider keys are not ready, seed the tracker with `templates/week-1-starter-content.csv`.
3. Run Slack/Google connectivity first, then add model generation.
4. Run agent sessions using:
- `agent/mcp-context-contract.md`
- `agent/weekly-agent-runbook.md`
- `agent/session-output-template.md`
- `agent/source-map.md`
5. Keep human review and manual posting for MVP.
6. Add optional automation only when manual movement is the bottleneck:
- `workflows/content-intake-openai.json`
- `workflows/slack-approval-callback.json`
7. Add extended automation later:
- `workflows/blog-repurpose-openai.json`
- `workflows/founder-notes-openai.json`

## No-Key Operating Mode

Until `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is valid, use the system in manual-review mode:

1. Import `templates/week-1-starter-content.csv` into the Google Sheets tracker.
2. Keep each row in `needs_review`.
3. Review posts in Slack or directly in the tracker.
4. Use statuses only:
- `needs_review`
- `Approved`
- `Needs Revision`
- `Rejected`
- `scheduled`
- `published`
5. Post manually to LinkedIn after approval.

This proves the operational loop without spending API credits.

## Team Collaboration Rules

- Treat this repo as the control plane: prompts, examples, schemas, workflows, runbooks.
- Treat Google Sheets as the live operational database.
- Treat Google Drive as source knowledge: blogs, notes, docs, transcripts, decks.
- Treat Slack as the review and approval surface.
- Do not store daily credentials or tokens in Git.
- Do not auto-publish from the agent during MVP.

## Role Setup

Each teammate should run:

```text
@contentops whoami
```

Then add their Slack user ID to local `agent/authz.yaml` using one of these roles:

- `admin`: all actions
- `editor`: draft, plan, repurpose
- `reviewer`: approve, revise, reject
- `viewer`: help and whoami only

Do not commit local `agent/authz.yaml`.

## Source of Truth Files

- Tracker schema: `templates/content-tracker-fields.md`
- Empty tracker CSV: `templates/content-calendar-template.csv`
- Week-one starter rows: `templates/week-1-starter-content.csv`
- Team collaboration guide: `agent/team-collaboration.md`
- Voice guide: `brand/voice-guide.md`
- Narrative engine: `brand/newtuple-narrative-engine.md`
- Banned phrases: `brand/banned-phrases.md`

## Operating Rhythm

- Monday: Founder Notes drafts
- Tuesday: AI shift analysis
- Wednesday: Workflow Wins/case-led post
- Thursday: Strategic operating model post
- Friday: Repurposed blog insights and recap

## Quality Gate

Do not auto-publish without human review.

Minimum gate:

- voice score >= 8/10
- no banned phrases
- concrete enterprise implication included
- one actionable takeaway

## Optional Local Fallback

Use local Ollama only as fallback:

- `workflows/optional-local-ollama-intake.json`
- `workflows/optional-local-ollama-blog-repurpose.json`
- `workflows/optional-local-ollama-founder-notes.json`

Setup guide: `workflows/zero-cost-setup.md`

## Optional n8n MVP

If you want to prove orchestration quickly, use:

- `workflows/mvp-proof-checklist.md`
- `workflows/content-intake-openai.json`
- `workflows/slack-approval-callback.json`

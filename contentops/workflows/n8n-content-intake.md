# n8n Workflow 1: Content Intake MVP

## Goal

Automate:

`Google Sheet row (status=new) -> Draft generation -> Slack review -> Status update`

## Prerequisites

- n8n instance
- Google Sheets credentials in n8n
- Slack incoming webhook
- Tracker sheet created from `contentops/templates/content-calendar-template.csv`
- one draft model path:
  - paid: OpenAI API key
  - zero-cost: local Ollama endpoint

## Row Contract

Rows eligible for processing:

- `status = new`
- `raw_input` not empty
- `source_type` set

## Node Flow

1. `Schedule Trigger` (every 15 min)
2. `Google Sheets: Read Rows` where `status = new`
3. `Split In Batches` (size 1)
4. `Function: Build Prompt Input`
5. `HTTP Request: Draft API (OpenAI or local Ollama)`
6. `Function: Parse Draft JSON`
7. `Google Sheets: Update Row` set:
- `title`
- `draft_text`
- `bucket`
- `status = needs_review`
8. `HTTP Request: Slack Webhook` post review message

## Optional Extension

Add second workflow for:

`Slack action approve/revise/reject -> update row status`

## File

Import starter JSON from:

`contentops/workflows/content-intake-mvp.json`

Local zero-cost variant:

`contentops/workflows/optional-local-ollama-intake.json`

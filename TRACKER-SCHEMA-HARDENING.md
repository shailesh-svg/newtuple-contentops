# Tracker Schema Hardening

## Problem

The live tracker uses a business-friendly schema:

- tab: `Content Tracker`
- header row: `3`
- columns: `Week`, `Publish Date`, `Bucket`, `Working Title / Hook`, `Status`, etc.

The original agent expected a CSV-style schema:

- header row: `1`
- primary key: `idea_id`
- columns: `title`, `draft_text`, `bucket`, `status`, etc.

That mismatch caused appends and status updates to fail.

## Current Contract

The hardened contract is:

- primary key: `Content ID`
- header row: auto-detected
- status column: `Status`
- approval fields: `Review Notes`, `Approved By`, `Approval Timestamp`
- draft storage: `Draft Text`

## Live Columns Required

- `Week`
- `Publish Date`
- `Weekday`
- `Bucket`
- `Series Theme`
- `Working Title / Hook`
- `Audience Intent`
- `Key Message`
- `Format`
- `Channel`
- `Owner`
- `Status`
- `Priority`
- `Source / Input Link`
- `CTA Type`
- `Repurpose Notes`
- `Published URL`
- `Content ID`
- `Draft Text`
- `Review Notes`
- `Approved By`
- `Approval Timestamp`

## Agent Compatibility

The agent still accepts old tool fields and maps them into the live tracker:

- `idea_id` -> `Content ID`
- `title` -> `Working Title / Hook`
- `bucket` -> `Bucket`
- `raw_input` -> `Key Message`
- `draft_text` -> `Draft Text`
- `status` -> `Status`
- `reviewer` -> `Approved By`
- `review_notes` -> `Review Notes`

This means existing prompts and Slack commands do not need to be rewritten immediately.

## Apps Script Requirement

Deploy the canonical Apps Script file:

```text
agent/google-apps-script/ContentOpsAgent.gs
```

Keep the existing `CONTENTOPS_TOKEN`.

The script supports:

- `health`
- `get_schema`
- `read_tracker`
- `write_tracker`
- `append_idea`
- `upsert_tracker_row`
- `update_approval`
- `list_drive_files`
- `read_drive_doc`

## Robustness Rules

- Use `Content ID` for updates.
- Do not update by row number from the Python agent.
- Do not assume headers are on row 1.
- Do not append without checking for an existing `Content ID`.
- Keep Slack approval messages tied to a `Content ID`.

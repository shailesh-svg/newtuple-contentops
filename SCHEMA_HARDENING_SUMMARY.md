# Schema Hardening Summary

The tracker hardening work is now aligned with the live Google Sheet instead of the old CSV-only schema.

## Root Cause

The live Sheet has headers on row `3` and uses business columns like `Week`, `Publish Date`, `Bucket`, and `Working Title / Hook`.

The agent expected headers on row `1` and an `idea_id` column.

## New Contract

- Primary tab: `Content Tracker`
- Header row: auto-detected
- Primary key: `Content ID`
- Backwards compatibility: agent tool fields like `idea_id`, `title`, `draft_text`, and `status` are mapped into live Sheet fields

## Live Sheet Additions

- `Content ID`
- `Draft Text`
- `Review Notes`
- `Approved By`
- `Approval Timestamp`

## Deployment Requirement

The Apps Script code in the repo has changed. The existing Apps Script project must be updated and redeployed before the Python agent gets the full schema-aware behavior.

Canonical source:

```text
agent/google-apps-script/ContentOpsAgent.gs
```

Standalone paste file:

```text
APPS_SCRIPT_CODE.js
```

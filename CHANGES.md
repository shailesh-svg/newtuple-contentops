# Changes

## 2026-05-26: Tracker Schema Hardening

### Live Sheet

Added these columns to the `Content Tracker` tab on row `3`:

- `Content ID`
- `Draft Text`
- `Review Notes`
- `Approved By`
- `Approval Timestamp`

`Content ID` is now the stable row key for automation.

### Agent Code

- Added `agent/apps_script_bridge.py`
- Updated `agent/tools/sheets.py`
- Updated `agent/config.py`
- Updated `agent/.env.example`

The agent still accepts older fields like `idea_id`, `title`, `draft_text`, and `status`, then maps them to the live tracker schema.

### Apps Script

Updated canonical Apps Script source:

- `agent/google-apps-script/ContentOpsAgent.gs`
- `APPS_SCRIPT_CODE.js`

The bridge remains token-based and compatible with the existing `.env`:

```bash
GOOGLE_AUTH_MODE=apps_script
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
GOOGLE_APPS_SCRIPT_TOKEN=...
CONTENTOPS_SHEET_NAME=Content Tracker
```

### Content Added

Added additional week 5 rows to the live tracker:

- `2026-06-29`: The workflow is only as strong as its weakest handoff
- `2026-06-30`: The AI news that matters is the news that changes work
- `2026-07-01`: Before scaling agents, define what failure looks like
- `2026-07-02`: The buyer does not ask for agents. They ask for work to move faster.
- `2026-07-03`: Agentic enterprise starts with ownership, not automation

### Manual Step Remaining

Redeploy the Apps Script web app with:

```text
agent/google-apps-script/ContentOpsAgent.gs
```

Keep the existing `CONTENTOPS_TOKEN`.

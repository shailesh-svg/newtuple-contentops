# Tracker Schema Hardening Implementation

Status: implemented in repo, live Sheet columns added.

## What Was Fixed

The live tracker uses:

- tab: `Content Tracker`
- header row: `3`
- primary key: `Content ID`

The earlier agent code assumed:

- header row: `1`
- primary key: `idea_id`

That mismatch caused automated writes to fail.

## Live Sheet Changes Applied

Added columns on row `3`:

- `Content ID`
- `Draft Text`
- `Review Notes`
- `Approved By`
- `Approval Timestamp`

Rows now generate `Content ID` values from `Publish Date` and row number.

## Repo Changes

- `agent/tools/sheets.py` maps old agent fields to the live tracker schema.
- `agent/apps_script_bridge.py` uses the existing token-based Apps Script protocol.
- `agent/google-apps-script/ContentOpsAgent.gs` supports:
  - header-row detection
  - schema discovery
  - read by status
  - write by `Content ID`
  - idempotent upsert
  - approval updates
  - Drive file listing and document reading
- `APPS_SCRIPT_CODE.js` mirrors the canonical Apps Script file for easy paste/deploy.

## Deployment Step Still Required

Open the existing Google Apps Script project and replace the current code with:

```text
agent/google-apps-script/ContentOpsAgent.gs
```

Keep your existing token value:

```javascript
const CONTENTOPS_TOKEN = 'your-existing-token';
```

Then deploy a new web app version.

Do not deploy the older bearer/function bridge version. The Python agent expects:

```json
{
  "token": "...",
  "action": "read_tracker",
  "sheetId": "...",
  "sheetName": "Content Tracker"
}
```

## Verification

After redeploy:

```bash
cd agent
source .venv/bin/activate
python main.py doctor
```

Expected before provider keys:

- Slack auth: OK
- Google Sheets read: OK
- Google Drive list: OK
- Provider keys: may fail until valid keys are added

Then test:

```bash
python - <<'PY'
from tools.sheets import read_tracker
print(read_tracker(status="Needs Review", limit=5))
PY
```

The returned rows should include `Content ID`, `Working Title / Hook`, and `Status`.

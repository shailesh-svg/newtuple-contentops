# Google Apps Script Setup

Use this path when you cannot create a Google Cloud service account.

The script runs as your Google account and exposes a private web endpoint protected by a token.

## 1. Create Script

Open:

```text
https://script.google.com/
```

Create a new project called:

```text
Newtuple ContentOps Agent
```

Paste the contents of `ContentOpsAgent.gs` into the editor.

If you already have the first ContentOps script deployed, update that existing
script instead of creating a second bridge. The agent expects this token-based
request shape:

```json
{
  "token": "your-token",
  "action": "read_tracker",
  "sheetId": "spreadsheet-id",
  "sheetName": "Content Tracker"
}
```

## 2. Set Token

In the script, replace:

```javascript
const CONTENTOPS_TOKEN = 'CHANGE_ME_TO_A_LONG_RANDOM_TOKEN';
```

Use a long random value. Example command:

```bash
openssl rand -hex 32
```

Use the same value in `agent/.env`:

```bash
GOOGLE_AUTH_MODE=apps_script
GOOGLE_APPS_SCRIPT_TOKEN=<same-token>
```

## 3. Deploy

In Apps Script:

- Click `Deploy`
- Click `New deployment`
- Select type: `Web app`
- Execute as: `Me`
- Who has access: `Anyone`

This does not make your data public because the script rejects requests without your token.

Copy the Web app URL into `agent/.env`:

```bash
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
CONTENTOPS_SHEET_NAME=Content Tracker
```

## 4. Authorize

Run the web app once from Apps Script or trigger any agent call.

Google will ask your Gmail account to approve access to:

- Google Sheets
- Google Drive
- Google Docs

Approve it.

## 5. Test

From this repo:

```bash
cd agent
source .venv/bin/activate
python main.py doctor
```

Success means:

```text
[OK] Google Sheets read ok
[OK] Google Drive list ok
```

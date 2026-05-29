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

## 2. Configure via Script Properties (no secrets in code)

Configuration lives in **Script Properties**, not in the source file. This keeps
the token out of code and lets one deployed script serve multiple environments
by changing properties only. It also **allowlists** which spreadsheets and Drive
folders the bridge may touch — so even with the token, a caller cannot read or
write arbitrary files in your Google account.

Set them either in **Project Settings → Script Properties**, or by editing the
`setup()` function at the top of `ContentOpsAgent.gs`, running it once from the
editor, then clearing your values out of it.

| Property | Required | Purpose |
|----------|----------|---------|
| `CONTENTOPS_TOKEN` | yes | long random shared secret (must match `agent/.env`) |
| `ALLOWED_SHEET_IDS` | yes | comma-separated allowlist of spreadsheet IDs the bridge may access |
| `ALLOWED_FOLDER_IDS` | yes | comma-separated allowlist of Drive folder IDs readable by the bridge |
| `DEFAULT_SHEET_ID` | optional | used when a request omits `sheetId` |
| `DEFAULT_FOLDER_ID` | optional | used when a request omits `folderId` |

Generate a token:

```bash
openssl rand -hex 32
```

Use the same value in `agent/.env`, and make sure your `CONTENTOPS_SHEET_ID` and
`GOOGLE_DRIVE_FOLDER_ID` are listed in the allowlists above:

```bash
GOOGLE_AUTH_MODE=apps_script
GOOGLE_APPS_SCRIPT_TOKEN=<same-token>
CONTENTOPS_SHEET_ID=<must be in ALLOWED_SHEET_IDS>
GOOGLE_DRIVE_FOLDER_ID=<must be in ALLOWED_FOLDER_IDS>
```

> Security: requests are rejected if `sheetId`/`folderId` are not in the
> allowlist, the token is compared in constant time, and error responses never
> include stack traces. A `GET` to the web-app URL returns a tokenless health
> probe.

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

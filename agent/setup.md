# Agent Setup Guide

## 1) Install and env

```bash
cd agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp authz.example.yaml authz.yaml
```

Fill `agent/.env` values.
Fill `agent/authz.yaml` with Slack user IDs and roles.

## 2) OpenAI and Anthropic keys

Required for model calls:

- `ANTHROPIC_API_KEY` (primary)
- `OPENAI_API_KEY` (fallback)
- `AI_PROVIDER=claude` (recommended default)

If these are missing or invalid, Slack and Google can still work. Commands that generate content (`plan-week`, `draft-from-idea`, `repurpose-blog`) will fail until a provider key is valid.

## 3) Google auth option A: Apps Script bridge

Use this when you cannot use Google Cloud service accounts.

1. Open Google Apps Script from the Google account that owns or can access the tracker and Drive folder.
2. Paste `google-apps-script/ContentOpsAgent.gs`.
3. Set a long random `CONTENTOPS_TOKEN` in the script.
4. Deploy as a Web App.
5. Set access to the appropriate workspace/user scope.
6. Copy the Web App `/exec` URL.
7. In `agent/.env`, set:

```bash
GOOGLE_AUTH_MODE=apps_script
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
GOOGLE_APPS_SCRIPT_TOKEN=your_long_random_token
CONTENTOPS_SHEET_ID=your_google_sheet_id_here
CONTENTOPS_SHEET_NAME=Sheet1
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id_here
```

Details: `google-apps-script/README.md`

## 4) Google auth option B: service account

1. In Google Cloud, create/select project.
2. Enable APIs:
- Google Sheets API
- Google Drive API
- Google Docs API
3. Create service account and JSON key.
4. Set `GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/to/key.json`.
5. Run `python main.py google-email`.
6. Share your Google Sheet with the printed service account email as Editor.
7. Share your Drive source folder with the printed service account email as Viewer/Commenter.
7. Set:
- `CONTENTOPS_SHEET_ID`
- `CONTENTOPS_SHEET_NAME=Sheet1`
- `GOOGLE_DRIVE_FOLDER_ID`

Use:

```bash
GOOGLE_AUTH_MODE=service_account
```

## 5) Slack app (Socket Mode)

Create Slack app and configure:

1. **Socket Mode**: enable.
2. **App-level token**: create token with `connections:write` -> set `SLACK_APP_TOKEN`.
3. **Bot token scopes**:
- `app_mentions:read`
- `channels:read`
- `chat:write`
- `groups:history` (if private channels)
- `groups:read` (if private channels)
4. **Event Subscriptions**: enable and subscribe to bot events:
- `app_mention`
- `message.groups` (if using a private review channel)
Optional for public channels:
- `message.channels`
5. Install or reinstall app to workspace after adding scopes/events.
6. Invite the bot to the review channel:

```text
/invite @contentops
```

7. Set:
- `SLACK_BOT_TOKEN`
- `SLACK_REVIEW_CHANNEL` (e.g. `#contentops-review`)

## 6) RBAC (team-friendly auth)

The bot checks Slack user IDs against `agent/authz.yaml`.

- `admin`: all actions
- `editor`: draft/plan/repurpose
- `reviewer`: approve/revise/reject
- `viewer`: help only

Set strict mode in `.env`:

- `AUTHZ_STRICT=true` (recommended)
- optional bootstrap admins: `AUTHZ_ADMIN_USERS=U123...,U456...`

To add a teammate:

1. Ask them to run `@contentops whoami` in Slack.
2. Add their returned Slack user ID to local `agent/authz.yaml`.
3. Restart the bot.

Do not commit `agent/authz.yaml`.

## 7) Verify setup

```bash
python main.py doctor
```

Target result before provider keys:

- Slack checks `[OK]`
- Google Sheets/Drive checks `[OK]`
- AuthZ checks `[OK]`
- Provider key checks may fail until valid keys are added

Target result after provider keys: all checks show `[OK]`.

## 8) First functional test (no Slack bot mode)

```bash
python main.py draft-from-idea "Most enterprise teams think they need a better model. They usually need a better handoff."
```

## 9) Start Slack bot

```bash
python main.py bot
```

In Slack:

- `@contentops whoami`  # get your Slack user ID
- `@contentops draft-from-idea <idea>`
- reply in thread with `approve`, `revise: <notes>`, or `reject: <reason>`

## 10) No-key starter content

Until provider keys work, import:

```text
contentops/templates/week-1-starter-content.csv
```

Those rows match the tracker schema and are ready for manual review.

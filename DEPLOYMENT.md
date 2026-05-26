# Deployment Runbook

## Current Runtime

The current runtime is the Python agent running in Slack Socket Mode.

Primary command:

```bash
cd /Users/apple/Desktop/newtuple-contentops/agent
source .venv/bin/activate
python main.py bot
```

## Required Local Files

These are intentionally not committed:

- `agent/.env`
- `agent/authz.yaml`

## Required External Setup

- Slack app installed in the Newtuple workspace
- Slack Socket Mode app token configured
- Slack bot token configured
- Google Apps Script web app deployed
- Google Sheet tracker available
- Google Drive source folder available

## Apps Script Redeploy

When `agent/google-apps-script/ContentOpsAgent.gs` changes:

1. Open the existing Google Apps Script project.
2. Replace the full script with `agent/google-apps-script/ContentOpsAgent.gs`.
3. Keep the existing `CONTENTOPS_TOKEN` value.
4. Deploy a new web app version.
5. Copy the `/exec` URL.
6. Update `GOOGLE_APPS_SCRIPT_URL` in `agent/.env` if it changed.
7. Run `python main.py doctor`.

## Local Validation

```bash
cd agent
source .venv/bin/activate
python main.py doctor
```

Expected before model keys are fixed:

- Slack auth: OK
- Google Sheets read: OK
- Google Drive list: OK
- Anthropic/OpenAI: may fail or skip

## Docker Validation

```bash
docker build -t newtuple-contentops-agent:ci .
docker run --env-file agent/.env newtuple-contentops-agent:ci python main.py doctor
```

## Rollback

If a new bot version breaks:

1. Stop the running process with `Ctrl+C`.
2. Revert to the previous Git commit:

```bash
git log --oneline -5
git switch main
git checkout <previous_commit> -- agent contentops APPS_SCRIPT_CODE.js
```

3. Restart the bot:

```bash
cd agent
source .venv/bin/activate
python main.py bot
```

If Apps Script breaks, use Apps Script deployment history and redeploy the previous working version.

## Container Authz

The Docker image intentionally does not include local `agent/authz.yaml`.

For container runs, pass admin Slack user IDs with `AUTHZ_ADMIN_USERS`:

```bash
docker run --env-file agent/.env \
  -e AUTHZ_ADMIN_USERS=U0B327XCG68 \
  newtuple-contentops-agent:ci python main.py doctor
```

For multi-user production roles, mount a managed authz file instead:

```bash
docker run --env-file agent/.env \
  -v /secure/path/authz.yaml:/app/authz.yaml:ro \
  newtuple-contentops-agent:ci python main.py bot
```

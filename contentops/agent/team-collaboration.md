# Team Collaboration Guide

## What Teammates Need

Each teammate needs:

- access to the Newtuple Slack workspace
- access to the content tracker Google Sheet
- access to the source Google Drive folder
- a local `agent/.env` file if they will run the bot or CLI
- a local `agent/authz.yaml` role mapping if strict auth is enabled

They do not need provider keys to review starter content.

## Roles

- `admin`: can run all commands and manage local setup
- `editor`: can generate plans, drafts, and blog repurposing
- `reviewer`: can approve, revise, and reject
- `viewer`: can run `help` and `whoami`

Use Slack to get a teammate's user ID:

```text
@contentops whoami
```

Then add the returned ID to local `agent/authz.yaml`.

Example:

```yaml
users:
  U1234567890: editor
  U2345678901: reviewer
```

Do not commit `agent/authz.yaml`.

## Weekly Operating Flow

1. Import or create rows in the Google Sheets tracker.
2. Set new rows to `needs_review`.
3. Review drafts in the tracker or Slack.
4. Use final statuses consistently:
- `Approved`
- `Needs Revision`
- `Rejected`
- `scheduled`
- `published`
5. Post manually to LinkedIn during MVP.
6. Update `published_url` after posting.
7. Add engagement metrics later when available.

## No-Key Mode

If model keys are not configured:

1. Use `contentops/templates/week-1-starter-content.csv`.
2. Import the rows into the tracker.
3. Review and approve manually.
4. Do not run generation commands yet.

Working commands in no-key mode:

```text
@contentops whoami
@contentops help
```

Local connectivity check:

```bash
cd agent
source .venv/bin/activate
python main.py doctor
```

## Model-Key Mode

After adding a valid provider key:

```text
@contentops plan-week
@contentops draft-from-idea <idea>
@contentops repurpose-blog <google_doc_url>
```

The bot still does not publish. It drafts and routes review.

## Change Rules

Commit changes to:

- prompts
- examples
- templates
- brand rules
- runbooks
- workflow specs
- agent code

Do not commit:

- `agent/.env`
- `agent/authz.yaml`
- API keys
- Slack tokens
- Apps Script tokens
- downloaded Google credentials
- local virtual environments

## Handoff Checklist

Before handing off to another teammate:

- `python main.py doctor` has Slack and Google checks passing
- review channel has invited `@contentops`
- teammate ran `@contentops whoami`
- teammate role was added locally
- tracker columns match `contentops/templates/content-tracker-fields.md`
- starter rows or generated drafts are in `needs_review`

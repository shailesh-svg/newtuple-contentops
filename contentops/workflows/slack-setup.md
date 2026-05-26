# Slack Setup (Primary Approval Callback)

Use a Slack Slash Command to send review decisions to n8n.

## 1) Create Slack App

- Slack API -> Your Apps -> Create App
- Enable `Slash Commands`
- Create command: `/content-review`

## 2) Set Request URL

Set Request URL to n8n webhook:

`https://<your-n8n-domain>/webhook/content-review`

## 3) Install App

Install to workspace and grant required scope.

## 4) Command Format

`/content-review <idea_id> approve|revise|reject <notes>`

Examples:

- `/content-review CNT-001 approve publish-ready`
- `/content-review CNT-001 revise tighten hook`
- `/content-review CNT-001 reject off-bucket`

## 5) Status Mapping

- `approve` -> `Approved`
- `revise` -> `Needs Revision`
- `reject` -> `Rejected`

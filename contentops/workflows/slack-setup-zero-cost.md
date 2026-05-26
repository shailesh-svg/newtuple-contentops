# Slack Setup (Zero-Cost Approval Callback)

Use a Slack Slash Command to send review decisions to n8n.

## 1) Create Slack App

- Go to Slack API > Your Apps > Create App
- Enable `Slash Commands`
- Create command: `/content-review`

## 2) Set Request URL

Set Request URL to your n8n production webhook URL:

`https://<your-n8n-domain>/webhook/content-review`

If running local-only, use a tunnel (for example, Cloudflare Tunnel or ngrok free tier) so Slack can reach n8n.

## 3) Install App to Workspace

Install the app and allow the command scope.

## 4) Command Format

Use command in Slack channel:

`/content-review <idea_id> approve|revise|reject <notes>`

Examples:

- `/content-review CNT-001 approve publish-ready`
- `/content-review CNT-001 revise tighten hook`
- `/content-review CNT-001 reject off-bucket`

## 5) Sheet Status Mapping

- `approve` -> `Approved`
- `revise` -> `Needs Revision`
- `reject` -> `Rejected`

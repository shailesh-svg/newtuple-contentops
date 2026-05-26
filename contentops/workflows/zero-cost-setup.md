# Zero-Cost Setup (Local)

This optional setup avoids paid SaaS and keeps everything on free/local tooling.

## Stack

- n8n self-hosted (local Docker)
- Ollama local model (no per-token API billing)
- Google Sheets (free)
- Slack free workspace + Slack app
- GitHub repo (free)

## What is truly zero-cost

- No n8n Cloud bill
- No OpenAI API bill
- No Buffer bill

## Tradeoff

Local model quality can be lower than paid hosted models. Keep human review mandatory.

## 1) Start n8n + Ollama locally

`docker-compose.yml` is already included in repo root.

Start:

```bash
docker compose up -d
```

Pull model once:

```bash
docker exec -it $(docker ps --filter name=ollama --format '{{.ID}}') ollama pull llama3.1:8b
```

## 2) Configure env

Set in local shell or `.env`:

- `CONTENTOPS_SHEET_ID`
- `SLACK_WEBHOOK_URL`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3.1:8b`

## 3) Import workflows (optional fallback set)

Import these JSON files in n8n:

1. `contentops/workflows/optional-local-ollama-intake.json`
2. `contentops/workflows/slack-approval-callback-local.json`
3. `contentops/workflows/optional-local-ollama-blog-repurpose.json`
4. `contentops/workflows/optional-local-ollama-founder-notes.json`

## 4) Keep this rule active

No automatic publishing. Human approval required.

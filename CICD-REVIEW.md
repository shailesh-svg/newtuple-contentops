# CI/CD Review

Date: 2026-05-26
Project: Newtuple ContentOps Agent

## Current State

The repo now has a practical CI baseline:

- Python syntax check
- Ruff lint
- Unit tests for command parsing, authz, tracker field mapping, and Apps Script bridge payloads
- Docker image build workflow
- GHCR push on `main`

The pipeline intentionally does not deploy to production yet. The current production-like runtime is still the local/hosted Slack Socket Mode bot plus Google Apps Script bridge.

## What Is Robust Now

- Secrets are ignored by Git via `.gitignore` and `.dockerignore`.
- CI does not require real Slack, Google, Anthropic, or OpenAI credentials.
- Tests avoid live network calls.
- Docker image uses a venv under `/opt/venv`, not `/root/.local`, so it works with a non-root user.
- GitHub Actions builds Docker on PRs and pushes to GHCR only on `main` pushes.

## Known Gaps

- No hosted deployment target is configured yet.
- No staging Slack workspace or staging Google Sheet exists yet.
- No production secret manager is wired into runtime yet.
- Docker build was not locally validated because Docker Desktop was paused.
- Apps Script still needs manual redeploy after schema-bridge changes.

## Recommended Next Hardening

1. Redeploy Apps Script with `agent/google-apps-script/ContentOpsAgent.gs`.
2. Re-run `python main.py doctor` locally.
3. Unpause Docker Desktop and run `docker build -t newtuple-contentops-agent:ci .`.
4. Decide where the bot should run persistently: local Mac, small VM, Render/Fly/Railway, or container host.
5. Add environment-specific secrets to the chosen runtime, not to Git.
6. Add a staging tracker and staging Slack channel before enabling automated deploys.

## Quality Gates

Before merging future code:

```bash
agent/.venv/bin/python -m pytest agent/tests -q
agent/.venv/bin/python -m ruff check agent
agent/.venv/bin/python - <<'PY'
import ast
from pathlib import Path
paths = [p for p in Path('agent').rglob('*.py') if '.venv' not in p.parts]
for path in paths:
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
print(f'parsed={len(paths)}')
PY
```

Before running the live bot:

```bash
cd agent
source .venv/bin/activate
python main.py doctor
python main.py bot
```

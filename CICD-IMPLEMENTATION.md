# CI/CD Implementation

## Files Added

- `.github/workflows/test.yml`
- `.github/workflows/build.yml`
- `Dockerfile`
- `.dockerignore`
- `pyproject.toml`
- `agent/requirements-dev.txt`
- `agent/tests/`

## CI Workflow

`test.yml` runs on PRs and pushes to `main`:

1. Install `agent/requirements-dev.txt`
2. Parse Python files with `ast`
3. Run `ruff check agent`
4. Run `pytest --cov=agent --cov-report=term-missing`

No live credentials are required.

## Docker Workflow

`build.yml` runs on PRs and pushes touching agent/Docker files.

- PR: build only, no push
- `main`: build and push to GHCR

Image name:

```text
ghcr.io/<owner>/newtuple-contentops-agent
```

## Local Commands

Install dev tools:

```bash
cd /Users/apple/Desktop/newtuple-contentops
agent/.venv/bin/python -m pip install -r agent/requirements-dev.txt
```

Run checks:

```bash
agent/.venv/bin/python -m pytest agent/tests -q
agent/.venv/bin/python -m ruff check agent
```

Build Docker image:

```bash
docker build -t newtuple-contentops-agent:ci .
```

Run container locally with env file:

```bash
docker run --env-file agent/.env newtuple-contentops-agent:ci python main.py doctor
```

## Important

Do not commit:

- `agent/.env`
- `agent/authz.yaml`
- local service-account files
- Slack, Google, OpenAI, or Anthropic tokens

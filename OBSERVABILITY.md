# ContentOps — Pipeline, Observability & Dashboard

This document covers the operational layer added on top of the content agent: a
deterministic **quality gate** (CI for content), end-to-end **run tracking**, and
a **visual dashboard** for non-technical team members.

---

## 1. Content quality gate (the "build step")

The brand rules used to live only in the agent's prompt — the model was *asked*
to follow them. They are now **enforced in code** in `agent/quality_gate.py` and
run automatically inside `post_to_slack` whenever the agent posts a **draft**
(i.e. a message with an `idea_id`). A draft that fails is **not posted**; the
violations are returned to the agent so it revises and retries — exactly like a
failing test blocks a deploy.

| Rule | Severity | Source of truth |
|------|----------|-----------------|
| `banned_phrase` | **block** | `contentops/brand/banned-phrases.md` (Hard Bans) |
| `length_min` / `length_max` | **block** | `QUALITY_MIN_CHARS` / `QUALITY_MAX_CHARS` |
| `bucket_missing` / `bucket_invalid` | **block** | `contentops/brand/content-buckets.md` |
| `voice_score_low` | **block** when score provided | `QUALITY_MIN_VOICE_SCORE` (default 8) |
| `voice_score_missing` | warn | — |
| `enterprise_implication` | warn (heuristic) | cue-word detection |
| `actionable_takeaway` | warn (heuristic) | cue-word detection |

Blocking rules are deterministic and high-confidence. Structural checks are
heuristic, so they only **warn** (surfaced on the dashboard) to avoid false
blocks. Tune via env vars (see `agent/.env.example`); disable entirely with
`QUALITY_GATE_ENABLED=false`.

The gate is covered by unit tests **and** a dedicated CI step
("Content quality-gate self-test") that proves it still blocks a known-bad draft
— this guards the guardrail against silent regressions.

---

## 2. Run tracking / telemetry

`agent/observability.py` records every agent invocation to a local SQLite store
(`CONTENTOPS_DB`, default `agent/data/ops.db`). It uses `contextvars` so tools
record events without any signature changes, and all writes are best-effort —
**telemetry never crashes the agent**.

Captured per **run**: command, Slack user, provider + model, status
(success/error), duration, tool-call count, input/output tokens, error.

Captured as **events**: each `tool_call` (with timing + ok/fail), every `gate`
verdict (with violations), `provider_fallback` occurrences, and review
`approval` decisions.

Set `LOG_FORMAT=json` for structured logs ready for a log shipper (Fly, Datadog,
CloudWatch, …).

---

## 3. Interactive dashboard (watch / review / edit / approve, per RBAC)

`agent/dashboard.py` is a server-rendered web interface (no build step) and a
`ReviewInterface` adapter: every write goes through the platform-neutral
`review_service` — the same path the Slack bot uses — so RBAC and the audit trail
are identical on both surfaces.

Stakeholders sign in, and what they can do depends on their role (resolved via
`identity.resolve` from the same `authz.yaml` used for Slack):

- **viewer** — watch the pipeline funnel, buckets, gate pass-rate, runs, and open items.
- **reviewer** — all of the above **+ Approve / Request revision / Reject**.
- **editor** — watch + **edit** item fields (title, bucket, key message, draft).
- **admin** — everything.

### Sign-in (both built in)
- **Sign in with Slack (OpenID Connect)** — production identity. Enabled when
  `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` are set (+ redirect
  `<DASHBOARD_BASE_URL>/auth/slack/callback`).
- **Dev login** (Slack user id + `DASHBOARD_TOKEN`) — for local use before OAuth
  is configured. Auto-disabled once OAuth is set, unless `DASHBOARD_DEV_LOGIN=true`.

Sessions are signed with `DASHBOARD_SECRET_KEY` (set a stable value in prod);
all state-changing POSTs are CSRF-protected.

```bash
python agent/main.py dashboard         # → http://localhost:8080

# Routes
GET  /                       # pipeline overview (login required)
GET  /item/<content_id>      # item detail + review/edit (role-gated)
POST /item/<id>/decide       # approve|revise|reject  → review_service.decide
POST /item/<id>/edit         # field edits            → review_service.edit
GET  /login, /logout, /auth/slack/start, /auth/slack/callback
GET  /healthz                # liveness JSON (open, no auth)
GET  /api/metrics            # JSON metrics (login required)
```

---

## 4. Deployment

**Docker Compose (recommended for the dashboard)** — bot + dashboard share one
telemetry volume so the dashboard sees the bot's data:

```bash
cp agent/.env.example agent/.env   # fill in credentials
docker compose up --build
open http://localhost:8080
```

**Fly.io** — the bot runs as the primary process with a persistent volume for
telemetry:

```bash
fly volumes create contentops_data --size 1 --region sin
fly deploy
```

The dashboard needs the same DB the bot writes; run it via docker-compose or a
separate Fly app against a shared volume (see notes in `fly.toml`). Fly process
groups land on separate machines with separate volumes, so a second process in
the same app would not see the bot's data.

---

## 5. Quick verification

```bash
python agent/main.py doctor   # now also checks telemetry store + quality gate
pytest                        # unit tests incl. gate, observability, dedup
```

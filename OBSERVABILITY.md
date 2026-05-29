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

## 3. Visual dashboard (for non-technical members)

`agent/dashboard.py` is a single, self-refreshing web page (server-rendered
HTML, no build step). It shows:

- **Content pipeline funnel** — Idea → Draft → Needs Review → Approved →
  Scheduled → Published, plus off-track (Needs Revision / Rejected), read live
  from the Google Sheet tracker.
- **By content bucket** — distribution across the 5 buckets.
- **Agent health** — run success rate, avg + p95 run time, output tokens,
  provider fallbacks.
- **Quality-gate pass-rate** and the rules that block most often.
- **Recent runs** and **recent review decisions**.

```bash
# Run locally
python agent/main.py dashboard         # → http://localhost:8080

# Endpoints
GET /            # the dashboard
GET /healthz     # liveness JSON (no token)
GET /api/metrics # JSON for programmatic use
```

Protect it with `DASHBOARD_TOKEN` (then open `http://host:8080/?token=…`). It is
**read-only** — it never writes to the tracker or telemetry.

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

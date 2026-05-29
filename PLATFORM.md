# ContentOps as a Platform-Agnostic Product

ContentOps is a **content-operations engine** that runs on any stack. Nothing in
the core knows about Slack, Google, or OpenAI specifically — those are *adapters*
plugged into well-defined edges and selected entirely by configuration. Drop it
onto a different stack by swapping adapters, not by editing the engine.

```
                         ┌───────────────────────────────────────┐
                         │              NEUTRAL CORE               │
   inputs ──Source──────▶│  agentic loop · brand/prompts ·        │◀── Reasoning (LLM)
   (Drive/Notion/FS)     │  quality gate · schema · observability │    (Claude/OpenAI/Ollama)
                         │  ReviewService (RBAC + decisions)      │
                         └───────┬───────────────┬───────────────┘
                                 │               │
                          TrackerBackend     ReviewInterface          IdentityResolver
                          (Sheets/Apps        (Slack / Web /          (Principal +
                           Script/JSON)        Teams / CLI)            per-platform map)
```

## The neutral core (the product's IP — no platform inside)

- The agentic loop (`contentops_agent.py`)
- Brand voice + prompts (`prompts.py`, `contentops/brand/*`)
- The deterministic quality gate (`quality_gate.py`)
- The tracker **schema contract** (`contentops/schema/tracker.schema.json`, `schema.py`)
- Observability / audit (`observability.py`)
- The **ReviewService** — RBAC-checked approve/revise/reject/edit (`review_service.py`)

Everything below is an edge with a swappable adapter, chosen by env var.

## The five swappable edges

| Edge | Interface | Adapters shipped | Selector env |
|------|-----------|------------------|--------------|
| **Reasoning** | OpenAI/Anthropic SDK loop | Claude, OpenAI, Ollama | `AI_PROVIDER` |
| **State / tracker** | `TrackerBackend` | Sheets, Apps Script, JSON file | `TRACKER_BACKEND` |
| **Knowledge sources** | `SourceBackend` | Google Drive, Apps Script, Local FS | `SOURCE_BACKEND` |
| **Human interface** | `ReviewInterface` | Slack (`main.py bot`), Web (`main.py dashboard`) | run as a process |
| **Identity & RBAC** | `resolve()` → `Principal` | Slack IDs, web, generic | `authz.yaml` |

### Interfaces (all follow the same small-Protocol + registry pattern)

```python
# State — where content lives
class TrackerBackend(Protocol):
    def read(self, status, limit) -> dict: ...
    def update(self, content_id, fields) -> dict: ...
    def upsert(self, row) -> dict: ...
    def get_schema(self) -> dict: ...

# Knowledge — where source material comes from
class SourceBackend(Protocol):
    def list(self, query) -> dict: ...
    def read(self, doc_id) -> dict: ...

# Identity — who is acting, platform-neutral
@dataclass
class Principal:
    id: str            # canonical, e.g. "alice"
    display_name: str
    platform: str      # "slack" | "web" | "cli" | ...
    role: str          # admin | editor | reviewer | viewer
    def can(self, action: str) -> bool: ...

# Human interface — how people are notified / review
class ReviewInterface(Protocol):
    def post_for_review(self, content_id, text) -> dict: ...
    def notify(self, audience, message) -> dict: ...
```

### The keystone: one ReviewService, many interfaces

Approve / revise / reject / edit logic lives **once**, in `review_service.py`,
and is platform-neutral:

```python
review_service.decide(principal, content_id, decision, notes="", source="")
review_service.edit(principal, content_id, fields)
```

Every interface is a thin translator into these calls:

- **Slack adapter:** button click → `resolve("slack", U123)` → `decide(principal, …)`
- **Web adapter (dashboard):** HTTP POST → `resolve("web", session_user)` → `decide(principal, …)`
- **CLI / Teams / email:** same shape

RBAC, tracker writes, and the audit trail happen inside `ReviewService` — so they
are identical across every surface, and no approval logic is ever duplicated.

## Configuring ContentOps for a new stack

Everything is env-driven; no code change to repoint the system:

```bash
# Reasoning
AI_PROVIDER=claude                 # or openai | ollama

# State
TRACKER_BACKEND=jsonfile           # or sheets | apps_script (or add notion)

# Knowledge sources
SOURCE_BACKEND=localfs             # or gdrive | apps_script (or add notion/s3)
SOURCE_LOCAL_DIR=./data/sources

# Human interfaces are launched as processes (each is a ReviewInterface adapter):
#   python main.py bot         # Slack
#   python main.py dashboard   # Web
# Run one or several; they all act through the same ReviewService.

# Identity / RBAC — authz.yaml, platform-neutral (see below)
```

## How to add an adapter (same recipe everywhere)

1. Implement the interface class (`read/update/...` or `list/read`, etc.).
2. Register it in that edge's `_BACKENDS`/registry dict.
3. Select it with the edge's env var.

No changes to the agent, prompts, schema, ReviewService, or any other adapter.
`JsonFileBackend` (tracker) and `LocalFsSource` (knowledge) are complete,
credential-free worked examples.

## Identity & RBAC, platform-neutral

Roles attach to a **canonical principal**, not to a Slack ID. A principal can
have identities on many platforms:

```yaml
# authz.yaml
roles:               # role -> allowed actions (extends built-ins)
  reviewer: [help, whoami, approve, revise, reject]
identities:          # platform handle -> canonical principal
  "slack:U123ABC": alice
  "web:alice@newtuple.com": alice
users:               # canonical principal -> role
  alice: reviewer
default_role: viewer
```

Back-compatible: if a platform handle isn't mapped under `identities`, the raw
id is treated as the principal — so an existing `authz.yaml` that maps Slack
user IDs straight to roles keeps working unchanged.

## What's neutral today vs. in progress

- ✅ Reasoning, State/tracker (schema contract + backends), Identity (`Principal`),
  ReviewService, Knowledge sources (`SourceBackend`).
- 🔜 Web `ReviewInterface` (the dashboard, as an adapter); additional source/
  interface adapters (Notion, Teams, email) as needed.

See `ARCHITECTURE.md` for the schema/backend detail and `OBSERVABILITY.md` for
the gate + telemetry + audit layer.

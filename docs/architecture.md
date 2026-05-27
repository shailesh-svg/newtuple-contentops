# Newtuple ContentOps — Technical Architecture

## What This System Is

An agentic content operating system that converts Newtuple's organizational knowledge — founder thinking, workflow learnings, client observations, AI implementation patterns — into repeatable strategic LinkedIn content and GTM intelligence.

This is not a content scheduler, a LinkedIn automation tool, or a generic AI writing assistant. It is a reasoning layer over Newtuple's operational knowledge that gets smarter as more context is added.

---

## System Layers

```
┌─────────────────────────────────────────────────────────┐
│                    INTERFACE LAYER                       │
│         Slack (Socket Mode bot — @contentops)           │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    AGENT LAYER                          │
│         Python Agent (agent/)                           │
│         ├── Agentic loop (Claude / OpenAI / Ollama)     │
│         ├── Tool dispatcher                             │
│         ├── RBAC (authz.yaml)                           │
│         └── Slack approval handler                      │
└──────┬──────────┬──────────┬──────────┬────────────────┘
       │          │          │          │
┌──────▼──┐ ┌────▼────┐ ┌───▼────┐ ┌───▼──────────────┐
│ Google  │ │ Google  │ │ Slack  │ │  GitHub Repo      │
│ Sheets  │ │  Drive  │ │  API   │ │  (this repo)      │
│(tracker)│ │ (source │ │(review)│ │  (brand assets)   │
└─────────┘ │  docs)  │ └────────┘ └──────────────────┘
            └─────────┘
┌─────────────────────────────────────────────────────────┐
│                   CONTROL PLANE                         │
│         contentops/ (this repository)                   │
│         ├── brand/          voice, narrative, buckets   │
│         ├── prompts/        system prompts              │
│         ├── examples/       hooks, posts, patterns      │
│         ├── templates/      tracker schema, post format │
│         └── analytics/      performance fields          │
└─────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Control Plane (`contentops/`)

The repository itself is the agent's long-term memory and brand intelligence. Every time the agent runs, it reads from this folder.

| Folder | Contents | Purpose |
|---|---|---|
| `brand/` | voice-guide, narrative-engine, content-buckets, banned-phrases | Defines what Newtuple sounds like |
| `prompts/` | system prompts for each command | Tells the agent how to behave |
| `examples/` | hooks, sample posts, founder observations, repurposed blogs | Gives the agent real patterns to follow |
| `templates/` | tracker schema, post format, slack approval template | Structural consistency |
| `analytics/` | performance field definitions | Foundation for future learning loop |

This folder is versioned in Git. Any change to brand voice, examples, or prompts is a code change with a review process — not a config in some dashboard.

### 2. Agent Layer (`agent/`)

The Python process that runs the system.

**`main.py`** — Entry point. Two modes:
- `python main.py bot` — starts the Slack Socket Mode bot (primary mode)
- `python main.py <command>` — one-shot CLI execution

**`contentops_agent.py`** — The agentic reasoning loop:
1. Loads the full system prompt (voice guide + narrative engine + content buckets + banned phrases, all assembled from `contentops/`)
2. Sends the user's request to the AI model with tool definitions
3. Executes tool calls as the model requests them (read tracker, read Drive docs, post to Slack, etc.)
4. Loops until the model produces a final response
5. Returns the result

**`prompts.py`** — Assembles the system prompt by reading markdown files from `contentops/brand/` and `contentops/prompts/`. This is how the agent always has Newtuple's voice context, regardless of which command is running.

**`tools/`** — Tool implementations the agent can call:
- `sheets.py` — Read and write the Google Sheets content tracker
- `drive.py` — Read Google Docs and list Drive files
- `repo_tools.py` — Read any file from this repo
- `slack_client.py` — Post messages and read thread replies

**`authz.py` + `authz.yaml`** — Role-based access control. Slack users are assigned roles (admin, editor, reviewer, viewer). The bot checks permissions before executing any command.

**`apps_script_bridge.py`** — HTTP bridge to Google Apps Script. Lets the agent read/write Google Sheets without a Google Cloud service account — simpler setup for Newtuple's workspace.

**`doctor.py`** — Health check that validates all credentials and runs live connectivity tests. Run with `python main.py doctor`.

### 3. AI Provider Layer

The agent supports three providers, switchable via `AI_PROVIDER` in `.env`:

| Provider | Use case | Quality |
|---|---|---|
| `claude` | Primary — strategy, voice, long-form reasoning | Highest |
| `openai` | Alternative — good tool use, structured output | High |
| `ollama` | Local testing — no API cost, runs on device | Variable (model-dependent) |

The agent has automatic fallback: if Claude fails, it tries OpenAI; if OpenAI fails, it tries Claude. Ollama has no fallback (it's for testing only).

### 4. Google Integration (Apps Script Mode)

The agent connects to Google Sheets and Drive via a deployed Google Apps Script web app (`agent/google-apps-script/ContentOpsAgent.gs`). This script:
- Accepts POST requests with a shared token
- Reads and writes the content tracker
- Lists and reads Drive files
- Runs as the Google account owner — no OAuth setup required for the agent

### 5. Slack Integration (Socket Mode)

The bot connects to Slack via WebSocket (Socket Mode) — no public URL or webhook required. It:
- Listens for `@contentops` mentions
- Parses commands or passes natural language to the agent
- Posts draft output to the review channel
- Listens for `approve` / `revise: notes` / `reject: reason` replies in threads
- Updates the tracker automatically on approval decisions

---

## Data Flow: `draft-from-idea`

```
User: @contentops Teams think they need better prompts.
      They usually need better orchestration. Draft a post.
        │
        ▼
Slack bot receives app_mention event
        │
        ▼
RBAC check — is user an editor or admin?
        │
        ▼
Agent starts — loads system prompt from contentops/brand/ files
        │
        ▼
Model (Claude/OpenAI/Ollama) receives: system prompt + user message + tool list
        │
        ├── Tool call: read_tracker(status="published") 
        │   → checks what was recently published (avoid repetition)
        │
        ├── Tool call: read_repo_file("contentops/examples/hooks.md")
        │   → loads hook patterns
        │
        ├── Tool call: read_repo_file("contentops/examples/opening-patterns.md")
        │   → loads opening patterns
        │
        ▼
Model generates draft (Hook → Operational reality → Enterprise implication → Next step)
        │
        ├── Tool call: post_to_slack(text=draft, idea_id="CNT-...")
        │   → posts draft to #contentops-review with approval instructions
        │
        ├── Tool call: append_idea(idea_id, title, bucket, raw_input, status="needs_review")
        │   → saves idea to Google Sheets tracker
        │
        ▼
Bot posts result in Slack thread
        │
        ▼
Reviewer replies: "approve" / "revise: make it shorter" / "reject: off-brand"
        │
        ▼
Bot reads reply → calls write_tracker(idea_id, {status: "Approved", reviewer: user_id})
        │
        ▼
Tracker updated. Human posts to LinkedIn manually.
```

---

## Commands

| Command | Trigger | What happens |
|---|---|---|
| `@contentops draft-from-idea <idea>` | Slack mention | Drafts one post, posts to Slack for review, saves to tracker |
| `@contentops plan-week` | Slack mention | Reads tracker + Drive, produces 5 ideas + 3 full drafts + gap analysis |
| `@contentops repurpose-blog <url>` | Slack mention | Reads a Google Doc, produces 2-3 post drafts from it |
| `@contentops update-status <id> <status>` | Slack mention | Updates a tracker row directly |
| `@contentops <anything>` | Slack mention | Natural language — agent reasons about the request |
| `approve` | Thread reply | Marks draft Approved in tracker |
| `revise: <notes>` | Thread reply | Marks Needs Revision, logs notes |
| `reject: <reason>` | Thread reply | Marks Rejected, logs reason |
| `python main.py doctor` | CLI | Health check — validates all credentials |
| `python main.py bot` | CLI | Starts the Slack bot |

---

## Quality Gate

Every draft must pass before it is shown for review:

- Voice score ≥ 8/10
- Zero banned phrases
- At least one concrete enterprise implication
- At least one actionable takeaway
- One content bucket assigned
- 150–280 words

The agent self-scores. If a draft scores below 8, it revises once before posting.

---

## Content Buckets

The five strategic content categories that keep Newtuple's output balanced:

1. **Shipping Production-Ready Intelligence** — reliability, monitoring, incident prevention
2. **Workflow Wins** — practical breakdowns, failure mode fixes
3. **What Changed In AI** — market updates through an operational lens
4. **Founder Notes** — grounded lessons from delivery and client conversations
5. **Building Your Agentic Enterprise** — strategy, org design, governance

---

## RBAC (Access Control)

Defined in `agent/authz.yaml`:

| Role | Permissions |
|---|---|
| `admin` | Everything |
| `editor` | draft-from-idea, plan-week, repurpose-blog |
| `reviewer` | approve, revise, reject |
| `viewer` | help, whoami only |

Add teammates: they run `@contentops whoami` to get their Slack user ID, you add it to `authz.yaml`.

---

## Dialogtuple Integration

A parallel deployment on Newtuple's own agent platform. Uses the same brand context from `contentops/` but implemented as a 5-agent visual workflow:

- **ContentOps Commander** (SuperAgent) — orchestrates
- **Research & Source Agent** — retrieves context via MCP
- **LinkedIn Drafting Agent** — writes in Newtuple voice
- **Brand QA Agent** — scores against quality gate
- **TrackerOps** — reads/writes the Sheet

System prompts for all 5 agents live in `contentops/prompts/dialogtuple/`.

---

## File Reference

```
newtuple-contentops/
├── CLAUDE.md                        project context for Claude Code
├── README.md                        repo overview
├── docker-compose.yml               Ollama local setup
├── docs/
│   ├── architecture.md              this file
│   └── eli12.md                     executive overview
├── contentops/                      control plane
│   ├── brand/                       voice, narrative, buckets, banned phrases
│   ├── examples/                    hooks, sample posts, patterns
│   ├── prompts/                     agent system prompts
│   │   └── dialogtuple/             Dialogtuple agent prompts
│   ├── templates/                   tracker schema, post templates
│   ├── analytics/                   performance field definitions
│   └── workflows/                   reference workflow specs
└── agent/                           Python agent
    ├── main.py                      CLI + Slack bot entry
    ├── contentops_agent.py          agentic loop
    ├── prompts.py                   system prompt builder
    ├── config.py                    env var config
    ├── authz.py                     RBAC logic
    ├── authz.yaml                   user → role mappings
    ├── apps_script_bridge.py        Google Apps Script HTTP client
    ├── doctor.py                    health check
    ├── requirements.txt             Python dependencies
    ├── .env                         credentials (not committed)
    ├── .env.example                 template
    ├── google-apps-script/
    │   └── ContentOpsAgent.gs       deployed Google Apps Script
    ├── tools/
    │   ├── sheets.py                Google Sheets read/write
    │   ├── drive.py                 Google Drive read
    │   ├── repo_tools.py            repo file read
    │   └── slack_client.py          Slack post + thread read
    └── tests/                       test suite
```

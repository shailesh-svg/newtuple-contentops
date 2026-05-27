# ContentOps on Dialogtuple — Setup Guide

## Workflow architecture

```
Slack / Channel
      |
      v
ContentOps Commander   (SuperAgent — orchestrates everything)
      |
      |-- Research & Source Agent  (Tool Agent — retrieves context)
      |-- LinkedIn Drafting Agent  (Tool Agent — writes drafts)
      |-- Brand QA Agent           (Tool Agent — scores and gates)
      |-- TrackerOps               (Tool Agent — reads/writes Sheet)
```

The Commander is the only agent that talks to the user. All others are tools — they receive structured inputs and return structured outputs.

---

## Agent configuration

### 1. ContentOps Commander (SuperAgent)

| Setting | Value |
|---|---|
| Type | SuperAgent |
| System Prompt | `01-commander.md` |
| Model | claude-opus-4-7 or gpt-5.5 |
| Temperature | 0.2 |
| Max Output Tokens | 4096 |
| Parallel Tool Calls | OFF (sequential orchestration) |
| Tool Choice | auto |
| MCP Tools | None directly — calls sub-agents as tools |

**Channel Persona Profile (Slack):**
- Name: ContentOps
- Intro message: "ContentOps ready. Commands: `draft-from-idea`, `plan-week`, `repurpose-blog`, `update-status`, `help`"
- Respond in threads: yes

---

### 2. Research & Source Agent (Tool Agent)

| Setting | Value |
|---|---|
| Type | Tool Agent (Add as Tool when adding to workflow) |
| System Prompt | `02-research-source.md` |
| Model | gpt-5.5 or claude-sonnet-4-6 |
| Temperature | 0.1 |
| Max Output Tokens | 8192 |
| Parallel Tool Calls | ON |
| Tool Choice | auto |

**MCP Tools to connect:**
- **GitHub MCP** — to read `contentops/brand/`, `contentops/examples/`, `contentops/prompts/`
- **Google Docs MCP** — to read Drive source documents (blogs, founder notes)
- **Google Sheets / Apps Script MCP** — to read the content tracker

---

### 3. LinkedIn Drafting Agent (Tool Agent)

| Setting | Value |
|---|---|
| Type | Tool Agent |
| System Prompt | `03-linkedin-drafting.md` |
| Model | claude-opus-4-7 (recommended for voice quality) |
| Temperature | 0.4 |
| Max Output Tokens | 2048 |
| Parallel Tool Calls | OFF |
| Tool Choice | none (no tools — pure reasoning) |

**MCP Tools:** None. All context is passed from the Commander via the Research agent output.

---

### 4. Brand QA Agent (Tool Agent)

| Setting | Value |
|---|---|
| Type | Tool Agent |
| System Prompt | `04-brand-qa.md` |
| Model | gpt-5.5 or gpt-4o |
| Temperature | 0.1 |
| Max Output Tokens | 1024 |
| Parallel Tool Calls | OFF |
| Tool Choice | none (no tools) |

**MCP Tools:** None. Receives draft text directly from Commander.

---

### 5. TrackerOps (Tool Agent)

| Setting | Value |
|---|---|
| Type | Tool Agent |
| System Prompt | `05-trackerops.md` |
| Model | gpt-4o-mini or gpt-5.5 |
| Temperature | 0.0 |
| Max Output Tokens | 512 |
| Parallel Tool Calls | OFF |
| Tool Choice | auto |

**MCP Tools to connect:**
- **Google Sheets / Apps Script MCP** — read and write the content tracker

---

## MCP servers needed

| MCP Server | Used by | Purpose |
|---|---|---|
| GitHub MCP | Research & Source Agent | Read brand assets, examples, prompts from this repo |
| Google Docs MCP | Research & Source Agent | Read Drive source docs (blogs, notes, transcripts) |
| Google Sheets / Apps Script MCP | Research & Source Agent, TrackerOps | Read and write content tracker |
| newtuple-atlassian-remote | Optional | Jira/Confluence integration for future roadmap posts |

You already have GitHub MCP, Google Docs MCP, and newtuple-atlassian-remote connected in the platform. Confirm Google Sheets access is working via TrackerOps before running the full workflow.

---

## Workflow order in the canvas

```
[ContentOps Commander] → [Research & Source Agent] → [LinkedIn Drafting Agent] → [Brand QA Agent] → [TrackerOps] → [End]
```

In Dialogtuple's canvas:
- Add ContentOps Commander as SuperAgent first
- Add each subsequent agent using "Add as Tool" (not "Add as Agent")
- Connect in the sequence above
- The Commander will invoke them in the right order based on the command

---

## Testing the workflow

### Step 1 — Test TrackerOps alone
Ask the Commander: `update-status CNT-TEST-001 Approved`
Confirm the tracker row updates correctly.

### Step 2 — Test Research agent
Ask: `draft-from-idea test` and check the research output in telemetry.
Confirm GitHub files are being read and tracker snapshot is returned.

### Step 3 — Test full draft flow
Ask: `draft-from-idea Most enterprise teams think they need a better model. They usually need a better handoff.`
Expected: draft posted with QA score >= 8 and approval prompt.

### Step 4 — Test approval
Reply `approve` to the draft thread.
Confirm TrackerOps updates the row to `Approved`.

### Step 5 — Test weekly plan
Ask: `plan-week`
Expected: 5 ideas, 5 hooks, 3 full drafts, gap analysis, publish schedule.

---

## Difference from the Python agent

| Python Agent | Dialogtuple |
|---|---|
| Runs locally / on a server | Runs on Dialogtuple's managed platform |
| Code-level tool calls | MCP server connections via UI |
| Single agentic loop | Multi-agent canvas with typed tool calls |
| Slack Socket Mode bot | Native Slack channel connector |
| Requires deployment | No-ops — configure and run |

Both systems share the same brand context from `contentops/`. The Dialogtuple version is the primary user-facing interface. The Python agent remains useful for local testing and one-off CLI operations.

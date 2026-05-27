# Newtuple ContentOps — Executive Overview

## The one-line version

We built a system that takes Newtuple's knowledge — things we've learned from client work, delivery, AI experiments, and founder thinking — and turns it into consistent, on-brand LinkedIn content automatically.

---

## The problem it solves

Every week, valuable insights get lost.

A founder has a sharp observation in a client meeting. A delivery team solves a hard problem. An AI workflow breaks in an interesting way and gets fixed. A prospect asks a question that reveals a market gap.

This knowledge never becomes content. It never sharpens Newtuple's positioning. It never compounds into a body of thought that makes Newtuple look like the authority it actually is.

The reason is simple: turning raw insight into polished, on-brand content takes time, skill, and consistency. All three are scarce.

ContentOps is the system that does this work.

---

## How it works — the simple version

Think of it as a very smart assistant that knows everything about how Newtuple communicates.

1. **You share an idea** — in Slack, however it comes to you. Could be a full sentence, a half-baked thought, or a link to a blog post you wrote.

2. **The assistant does the research** — it checks what Newtuple has already posted (so it doesn't repeat), reads Newtuple's voice rules, looks at real examples of posts that performed well.

3. **It writes a draft** — in Newtuple's voice. Not generic AI content. Not motivational fluff. Workflow-first, enterprise-grounded, specific.

4. **It checks its own work** — before showing the draft to anyone, it scores it against Newtuple's quality standards. If it doesn't pass, it rewrites until it does.

5. **It asks for approval** — posts the draft in Slack with a simple prompt: reply `approve`, `revise: your notes`, or `reject: reason`.

6. **You approve, it updates the tracker** — the Google Sheet that tracks every content idea, draft, and published post updates automatically.

7. **You post manually** — the system never posts to LinkedIn on your behalf. That stays human.

---

## What it's connected to

| System | What it does |
|---|---|
| Slack | Where you talk to it and approve drafts |
| Google Sheets | The content tracker — all ideas, drafts, statuses |
| Google Drive | Where source material lives (blogs, notes, transcripts) |
| This GitHub repo | Where Newtuple's brand voice and rules are stored |
| Claude / OpenAI | The AI brain that does the reasoning and writing |

---

## What you can ask it

From Slack, just mention `@contentops`:

| What you say | What happens |
|---|---|
| `@contentops draft-from-idea Most teams need better orchestration, not better prompts` | Writes a LinkedIn post from that idea |
| `@contentops plan-week` | Produces next week's full content plan: 5 ideas, 3 full drafts, gap analysis |
| `@contentops repurpose-blog <link to doc>` | Reads a blog and turns it into 2-3 LinkedIn posts |
| `@contentops <anything in plain English>` | The system figures out what you want and does it |

---

## Why this is different from just using ChatGPT

ChatGPT doesn't know Newtuple.

It doesn't know that Newtuple writes about orchestration, not prompts. That Newtuple never uses phrases like "AI will change everything." That every post needs a concrete enterprise implication, not just a general insight. That Newtuple's voice is calm, grounded, and practitioner-led — not motivational.

ContentOps has all of that knowledge built in. Every draft it produces has already been checked against Newtuple's voice guide, narrative principles, quality gate, and banned phrases. It also knows what Newtuple has already published — so it doesn't repeat the same angles.

---

## The bigger picture

Short term: consistent weekly LinkedIn content, less manual drafting, Newtuple voice maintained across all posts.

Medium term: the system learns what works. High-performing posts inform future drafts. Narrative gaps get surfaced. Blog repurposing becomes routine.

Long term: this becomes Newtuple's GTM intelligence layer — not just content, but positioning analysis, campaign planning, and a reusable framework that could be productized for clients.

---

## What humans still do

The system drafts. Humans decide.

- **Approval** — every post gets a human yes/no before it's used
- **Publishing** — manual LinkedIn posting, always
- **Strategy** — what to focus on, which ideas matter, what clients need to hear
- **Source material** — founder notes, blog posts, and observations come from humans

The system handles the translation from insight to draft. The judgment stays with the team.

---

## The two places it runs

**1. Slack bot (primary)** — runs on your MacBook or a server, responds to `@contentops` in Slack. This is the main day-to-day interface.

**2. Dialogtuple (parallel)** — a visual version running on Newtuple's own agent platform, with five specialized agents working together. Same brand rules, different interface.

---

## One number that matters

The content tracker currently has **999 rows** of content ideas and history. That is the organizational memory the system reasons over every time it drafts something new.

Every approved post, every revision note, every rejected draft makes the system more useful — because it knows what has already been said and what direction to take next.

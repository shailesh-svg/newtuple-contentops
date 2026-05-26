from config import CONTENTOPS_DIR


def _read(relative_path: str) -> str:
    path = CONTENTOPS_DIR / relative_path
    if path.exists():
        return path.read_text().strip()
    return f"[{relative_path} not found]"


def build_system_prompt() -> str:
    voice = _read("brand/voice-guide.md")
    narrative = _read("brand/newtuple-narrative-engine.md")
    buckets = _read("brand/content-buckets.md")
    banned = _read("brand/banned-phrases.md")
    base = _read("prompts/contentops-agent-system-prompt.md")

    return f"""{base}

---

## VOICE GUIDE
{voice}

---

## NARRATIVE ENGINE
{narrative}

---

## CONTENT BUCKETS
{buckets}

---

## BANNED PHRASES — NEVER USE THESE
{banned}

---

## TOOLS AVAILABLE
You have tools to retrieve live context and write back results:
- read_tracker: get content ideas and drafts from Google Sheets
- write_tracker: update status, drafts, notes in Google Sheets
- append_idea: add a new idea row to the tracker
- read_drive_doc: read a Google Doc (blogs, founder notes, transcripts)
- list_drive_files: list files in the source Drive folder
- read_repo_file: read any file from this repo (brand assets, examples, templates)
- post_to_slack: post a draft for human review in Slack
- read_slack_thread: read approval replies from a Slack thread

## HARD RULES
1. Never publish directly. Post to Slack for human review only.
2. Never use banned phrases.
3. Always assign a content bucket.
4. Always include one concrete enterprise implication.
5. Always include one actionable next step.
6. Confidence score must be honest. If context is weak, say so and return a "context missing" list.
"""


def build_weekly_plan_prompt() -> str:
    examples = _read("examples/high-performing-posts.md")
    hooks = _read("examples/hooks.md")
    return f"""Generate this week's ContentOps plan for Newtuple.

Steps:
1. Read the tracker to understand what's already in pipeline (new, needs_review, approved).
2. List recent published posts to avoid repetition.
3. Check which content buckets are underrepresented this week.
4. Read 1-2 recent Drive docs for fresh source material.
5. Produce:
   - 5 post ideas (one per bucket if possible)
   - 5 hooks (one per idea)
   - 3 full draft candidates (best 3 ideas)
   - Gap analysis (missing narrative themes, underused buckets)
   - Recommended publish days (Mon–Fri)
6. Post the full plan to Slack for review.
7. For each approved draft, update the tracker.

HIGH-PERFORMING POST EXAMPLES (for reference):
{examples}

STRONG HOOK EXAMPLES:
{hooks}
"""


def build_draft_from_idea_prompt(idea: str) -> str:
    opening = _read("examples/opening-patterns.md")
    return f"""Draft a LinkedIn post from this idea:

IDEA: {idea}

Steps:
1. Read the tracker to check if a similar idea was recently covered (avoid repetition).
2. Use the voice guide and narrative engine to frame the post.
3. Follow the required post skeleton: Hook → Operational reality → Enterprise implication → Practical next step.
4. Assign a content bucket.
5. Self-score voice alignment (1–10). If below 8, revise.
6. Post the draft to Slack for review with a reviewer note explaining why it fits Newtuple voice.
7. Append the idea to the tracker with status `needs_review`.

OPENING PATTERN EXAMPLES:
{opening}
"""


def build_repurpose_blog_prompt(doc_id: str) -> str:
    repurposed = _read("examples/repurposed-blog-posts.md")
    return f"""Repurpose this blog/document into 2–3 LinkedIn posts.

DOCUMENT ID / URL: {doc_id}

Steps:
1. Read the document using read_drive_doc.
2. Identify the 2–3 strongest insights, workflow lessons, or enterprise implications.
3. Draft one LinkedIn post per insight in Newtuple voice.
4. Assign each post to a content bucket.
5. Self-score each draft (1–10). Only include drafts scoring 8+.
6. Post all drafts to Slack as a single review thread.
7. Append each as a new row in the tracker with status `needs_review`.

REPURPOSED BLOG EXAMPLES (for style reference):
{repurposed}
"""

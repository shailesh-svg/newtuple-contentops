# Manual MVP Test Plan (3 Ideas)

Goal: prove one full loop works.

Flow:

`Google Sheet row -> n8n -> OpenAI/Claude draft -> sheet update -> Slack review message`

Primary workflow to test:

`contentops/workflows/content-intake-openai.json`

## Test Rows

Add 3 rows with `status = new`.

1. Workflow Wins idea
- `source_type`: workflow_lesson
- `raw_input`: "An AI intake workflow fails because no one owns exception handling across agent handoffs."

2. Founder Notes idea
- `source_type`: founder_note
- `raw_input`: "In client calls, teams ask for autonomous agents, but rollout slows down due to missing ownership and guardrails."

3. Blog repurposing idea
- `source_type`: blog
- `source_link`: your blog URL
- `raw_input`: "Repurpose this blog into operationally grounded LinkedIn drafts."

## Pass Criteria

- row is picked up when `status = new`
- draft fields populated (`title`, `draft_text`, `bucket`)
- `status` changes to `needs_review`
- Slack review message appears with readable formatting

## Gap Checklist

1. Column mapping correct
- fields land in right columns
- no duplicated/misaligned cells

2. JSON quality
- model response parses without fallback errors
- no markdown wrappers around JSON

3. Voice quality
- hook uses Newtuple pattern
- includes operational implication
- avoids banned phrases

4. Slack readability
- clear Idea ID and bucket
- draft formatting scannable on mobile

5. Status integrity
- only expected transitions happen
- no rows stuck between states

6. Tracker hygiene
- one idea_id = one canonical row
- notes appended, not overwritten blindly

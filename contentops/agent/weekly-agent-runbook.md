# Weekly Agent Runbook

Use this runbook to operate ContentOps without heavy automation.

## Goal

Generate a weekly content plan and draft set based on retrieved context, not fixed workflows.

## Inputs To Retrieve (MCP)

1. Repo control-plane assets (voice, buckets, examples, prompts)
2. Tracker rows (new, Needs Revision, Approved, published)
3. Latest source knowledge (blogs, notes, transcripts)
4. Performance metrics from recent posts
5. Reviewer feedback patterns

## Agent Task

Produce:

- 5 post ideas for next week
- 5 hooks
- 3 full draft candidates
- bucket coverage check
- gap analysis (what narrative is missing)
- recommended publish days

## Review Step

Human reviewer checks:

- voice alignment
- operational clarity
- enterprise implication
- non-repetition vs recent posts

## Save Step

Write approved items to tracker with status `Approved`.

Keep rejected items with notes for learning.

## Publish Step

Manual LinkedIn posting for MVP stage.

## Escalation Rule

If agent confidence is low or source context is weak, do not draft aggressively.

Return a "context missing" list and request specific inputs.

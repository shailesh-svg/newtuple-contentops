# Primary Setup: OpenAI/Claude + n8n + Sheets + Slack

This is the main Newtuple setup.

## Stack

- ContentOps repo (control plane)
- Google Sheets (tracker)
- n8n (automation)
- Slack (approval)
- OpenAI and/or Claude APIs (generation)
- ContentOps Agent (strategy and final polish)

## Build Order

1. `content-intake-openai.json`
2. `slack-approval-callback.json`
3. `blog-repurpose-openai.json`
4. `founder-notes-openai.json`

## Core Rule

Use APIs only when needed:

- draft once per idea
- avoid repeated regeneration loops
- run blog repurposing manually/batch-triggered
- use smaller model for classification/light transforms
- use stronger model for final draft quality

## Suggested Model Split

- Intake drafting: `gpt-5-mini` (cost control)
- Founder notes final tone: `gpt-5` or Claude Sonnet
- Blog repurposing long-context: `gpt-5` or Claude Sonnet

## Approval Rule

No auto-publishing.

`needs_review -> Approved/Needs Revision/Rejected`

Publishing remains manual LinkedIn posting until operations are stable.

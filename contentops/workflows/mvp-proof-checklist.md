# MVP Proof Checklist (Core Loop Only)

Scope for proof:

1. `content-intake-openai.json`
2. `slack-approval-callback.json`

Do not test other workflows yet.

## Objective

Prove one idea can move end-to-end without manual copying:

`new -> needs_review -> Approved` (or `Needs Revision` / `Rejected`)

## Preflight

1. Sheet exists with template columns from `contentops/templates/content-calendar-template.csv`.
2. n8n credentials connected:
- Google Sheets OAuth
- OpenAI API key
- Slack webhook URL
3. Slack slash command configured per `contentops/workflows/slack-setup.md`.
4. Both workflows imported and active in n8n.

## Test Data

Insert 3 rows with status `new` using:

- `contentops/templates/mvp-test-ideas.csv`

## Test A: Intake Workflow

Workflow: `content-intake-openai.json`

1. Run manually in n8n.
2. Verify for each `idea_id`:
- `title` populated
- `draft_text` populated
- `bucket` populated
- `status` changed to `needs_review`
3. Verify Slack message includes:
- Idea ID
- bucket
- hook
- draft body
- slash-command usage hint

Pass if all 3 rows update and all 3 Slack messages arrive clearly formatted.

## Test B: Approval Callback Workflow

Workflow: `slack-approval-callback.json`

Run these commands in Slack:

1. `/content-review CNT-T1 approve publish-ready`
2. `/content-review CNT-T2 revise tighten operational implication`
3. `/content-review CNT-T3 reject off-bucket`

Verify Sheet updates:

- `CNT-T1` -> `status = Approved`
- `CNT-T2` -> `status = Needs Revision`
- `CNT-T3` -> `status = Rejected`
- `reviewer` populated
- `review_notes` captured

Pass if all 3 status transitions are correct and notes are written to correct rows.

## Failure Checks

If any fail, stop and fix before next workflows.

1. Column mapping mismatch
- Symptom: fields written to wrong columns
- Fix: re-open Google Sheets node mapping and reselect match column `idea_id`

2. JSON parse warning in drafts
- Symptom: title contains parse warning or raw JSON dump
- Fix: tighten prompt to strict JSON; reduce output length

3. Slack command rejected
- Symptom: "Action must be approve, revise, or reject"
- Fix: ensure command format is exactly `/content-review <idea_id> <action> <notes>`

4. Row not updating
- Symptom: webhook success but Sheet unchanged
- Fix: confirm `idea_id` exists exactly and matching column is configured

## MVP Success Definition

MVP is proven only when at least one row completes:

`new -> needs_review -> Approved`

with no manual copy-paste between systems.

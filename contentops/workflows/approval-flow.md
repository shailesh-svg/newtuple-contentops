# Approval Flow

## Status State Machine

- `new`
- `needs_review`
- `Approved`
- `Needs Revision`
- `Rejected`
- `scheduled`
- `published`

## Slack Review Commands

- `approve`
- `revise: <notes>`
- `reject: <reason>`

## Handling Rules

- `approve` -> set `status = approved`, store `reviewer`, timestamp
- `approve` -> set `status = Approved`, store `reviewer`, timestamp
- `revise` -> set `status = Needs Revision`, append notes to `review_notes`
- `reject` -> set `status = Rejected`, store reason

## Safety Rule

No automatic publishing unless `status = approved` and `voice_score >= 8`.

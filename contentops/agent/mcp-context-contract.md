# MCP Context Contract

This defines the minimum context the ContentOps Agent should retrieve before generating output.

## Required Pulls Per Session

1. Voice and narrative guardrails from repo
- `contentops/brand/voice-guide.md`
- `contentops/brand/banned-phrases.md`
- `contentops/brand/newtuple-narrative-engine.md`
- `contentops/brand/content-buckets.md`

2. Live tracker snapshot
- latest rows from Sheet where status is `new` or `Needs Revision`
- recent `Approved` and `published` rows for pattern continuity

3. Source knowledge
- latest blog/article/transcript inputs relevant to requested deliverable

4. Performance signal
- recent engagement fields from tracker (`likes`, `comments`, `shares`, `reach`, `ctr`)

5. Review context
- latest reviewer notes from Slack or tracker fields

## Output Requirements

Every generated artifact must include:

- bucket assignment
- hook style type
- operational implication
- practical next step
- reviewer note for why it fits Newtuple voice

## Hard Constraints

- no banned phrases
- no generic hype claims
- no autonomous publishing without human approval

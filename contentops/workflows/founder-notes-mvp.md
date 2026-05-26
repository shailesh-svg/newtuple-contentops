# n8n Workflow 3: Founder Notes Pipeline

## Goal

`Voice note/transcript -> insight extraction -> 2 founder-note drafts -> Slack review`

## Node Flow

1. Trigger: new transcript row in Sheet
2. OpenAI: extract 3 operational insights
3. OpenAI: rewrite in Founder Notes voice
4. Google Sheets: append/update drafts
5. Slack: request approval

## Guardrails

- preserve original claim intent
- avoid invented metrics
- require one implementation lesson per draft

# n8n Workflow 2: Blog Repurposing Pipeline

## Goal

`New blog URL -> extract key sections -> generate multi-asset set -> save to tracker -> Slack review`

## Outputs Per Blog

- 5 LinkedIn posts
- 2 Founder Notes
- 1 carousel outline
- 10 hooks

## Suggested Node Flow

1. Trigger: RSS, Webhook, or Manual URL input
2. HTTP Request: fetch page content
3. HTML Extract or AI extraction step
4. OpenAI: section distillation
5. OpenAI: multi-asset generation
6. Google Sheets: append rows (`status = needs_review`)
7. Slack: send grouped review notification

## Notes

- Keep source excerpt in tracker for auditability.
- Tag rows with `source_type = blog` and shared `source_link`.

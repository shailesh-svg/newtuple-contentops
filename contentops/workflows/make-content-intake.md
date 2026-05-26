# Make.com Alternative: Content Intake

If you prefer Make.com over n8n, mirror the same sequence:

1. Google Sheets watch rows where `status = new`
2. OpenAI completion using `linkedin-draft-prompt.md`
3. Parse JSON response
4. Update row with draft and `status = needs_review`
5. Send Slack review message

Use the same tracker schema and prompt assets from this repo.

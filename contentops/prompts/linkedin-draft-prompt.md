# LinkedIn Draft Prompt

Use this prompt with the system prompt.

## Input

- idea_title: {{idea_title}}
- source_type: {{source_type}}  (founder_note | blog | ai_news | workflow_lesson)
- source_text: {{source_text}}
- target_bucket: {{target_bucket}}
- target_length: {{target_length}} (short | medium)

## Task

Generate one LinkedIn post draft in Newtuple voice.

Requirements:

1. Opening must follow Newtuple hook pattern (tension, misconception, shift, or observation).
2. Explain what breaks or scales when AI meets real operations.
3. Translate into enterprise implication (risk, reliability, ownership, speed, cost).
4. End with a practical CTA.
5. Keep it skimmable with short paragraphs.
6. No emojis.

## Output JSON

{
  "title": "",
  "hook": "",
  "post_body": "",
  "cta": "",
  "bucket": "",
  "hashtags": ["", "", ""],
  "review_notes": ""
}

# Review Scorecard Prompt

Score a draft against Newtuple standards.

## Input

- draft_text: {{draft_text}}
- bucket: {{bucket}}

## Criteria (1-10 each)

1. Hook strength
2. Operational clarity
3. Enterprise translation
4. Voice alignment
5. Practicality

## Output JSON

{
  "hook_strength": 0,
  "operational_clarity": 0,
  "enterprise_translation": 0,
  "voice_alignment": 0,
  "practicality": 0,
  "overall": 0,
  "must_fix": [""],
  "nice_to_improve": [""]
}

# Content Tracker Fields

The live Google Sheet is the operational database. Its current primary tab is:

- Sheet tab: `Content Tracker`
- Header row: row `3`
- Primary key: `Content ID`

## Live Required Columns

- `Week`
- `Publish Date`
- `Weekday`
- `Bucket`
- `Series Theme`
- `Working Title / Hook`
- `Audience Intent`
- `Key Message`
- `Format`
- `Channel`
- `Owner`
- `Status`
- `Priority`
- `Source / Input Link`
- `CTA Type`
- `Repurpose Notes`
- `Published URL`
- `Content ID`
- `Draft Text`
- `Review Notes`
- `Approved By`
- `Approval Timestamp`

## Status Values

- `Idea`
- `Draft`
- `Needs Review`
- `Needs Revision`
- `Approved`
- `Rejected`
- `Scheduled`
- `Published`

## Compatibility Mapping

The Python agent still accepts older tool fields and maps them into the live schema:

- `idea_id` -> `Content ID`
- `title` -> `Working Title / Hook`
- `bucket` -> `Bucket`
- `raw_input` -> `Key Message`
- `draft_text` -> `Draft Text`
- `status` -> `Status`
- `reviewer` -> `Approved By`
- `review_notes` -> `Review Notes`
- `review_action_ts` -> `Approval Timestamp`
- `source_link` -> `Source / Input Link`
- `platform` -> `Channel`
- `published_url` -> `Published URL`

## Rule

Do not add new automation against the old CSV-only schema without also updating this mapping.

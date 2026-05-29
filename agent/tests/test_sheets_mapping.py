"""Field + status normalisation now lives in the canonical schema (agent/schema.py).
These tests pin the legacy-alias → live-tracker mapping at its source of truth.
"""

from schema import normalize_fields, normalize_status


def test_normalize_fields_maps_legacy_schema_to_live_tracker_schema():
    fields = normalize_fields(
        {
            "idea_id": "CNT-1",
            "title": "Hook",
            "draft_text": "Draft",
            "bucket": "Workflow Wins",
            "status": "needs_review",
            "reviewer": "U123",
            "review_notes": "Looks good",
        }
    )

    assert fields["Content ID"] == "CNT-1"
    assert fields["Working Title / Hook"] == "Hook"
    assert fields["Draft Text"] == "Draft"
    assert fields["Bucket"] == "Workflow Wins"
    assert fields["Status"] == "needs_review"
    assert fields["Approved By"] == "U123"
    assert fields["Review Notes"] == "Looks good"


def test_normalize_status_maps_to_live_tracker_values():
    assert normalize_status("new") == "Idea"
    assert normalize_status("needs_review") == "Needs Review"
    assert normalize_status("approved") == "Approved"
    assert normalize_status("published") == "Published"

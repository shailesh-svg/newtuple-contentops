from tools.sheets import _normalize_fields, _normalize_status


def test_normalize_fields_maps_legacy_schema_to_live_tracker_schema():
    fields = _normalize_fields(
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
    assert _normalize_status("new") == "Idea"
    assert _normalize_status("needs_review") == "Needs Review"
    assert _normalize_status("approved") == "Approved"
    assert _normalize_status("published") == "Published"

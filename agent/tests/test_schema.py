import schema


def test_aliases_resolve_to_canonical_columns():
    assert schema.normalize_field_name("idea_id") == "Content ID"
    assert schema.normalize_field_name("title") == "Working Title / Hook"
    assert schema.normalize_field_name("reviewer") == "Approved By"
    assert schema.normalize_field_name("raw_input") == "Key Message"
    # Unknown names pass through unchanged.
    assert schema.normalize_field_name("Totally Custom") == "Totally Custom"


def test_status_normalisation():
    assert schema.normalize_status("new") == "Idea"
    assert schema.normalize_status("NEEDS-REVISION") == "Needs Revision"
    assert schema.normalize_status("approve") == "Approved"
    # Already-canonical values are preserved.
    assert schema.normalize_status("Published") == "Published"


def test_build_create_row_applies_defaults_and_fallbacks():
    row = schema.build_create_row(
        {"idea_id": "CNT-1", "title": "Hook", "bucket": "Workflow Wins",
         "raw_input": "the body", "status": "new"}
    )
    assert row["Content ID"] == "CNT-1"
    assert row["Working Title / Hook"] == "Hook"
    assert row["Key Message"] == "the body"
    assert row["Draft Text"] == "the body"          # falls back to Key Message
    assert row["Status"] == "Idea"                   # normalised
    assert row["Channel"] == "LinkedIn"              # create default
    assert row["Audience Intent"] == "Educate and build trust"
    assert set(row.keys()) == set(schema.column_names())  # full, ordered row


def test_header_detection():
    assert schema.is_header_row(["Content ID", "Status", "Bucket"]) is True
    assert schema.is_header_row(["Week", "Working Title / Hook"]) is True
    assert schema.is_header_row(["random", "columns", "here"]) is False


def test_primary_key_and_version():
    assert schema.primary_key() == "Content ID"
    assert schema.schema_version() == "1.0.0"


def test_contract_validates():
    # load_schema runs _validate; should not raise.
    data = schema.load_schema()
    assert data["primary_key"] in [f["name"] for f in data["fields"]]

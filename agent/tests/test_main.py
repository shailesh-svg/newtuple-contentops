from main import _extract_content_id, _normalize_status, _parse_and_run


def test_normalize_status_variants():
    assert _normalize_status("approve") == "Approved"
    assert _normalize_status("needs revision") == "Needs Revision"
    assert _normalize_status("needs_review") == "Needs Review"
    assert _normalize_status("reject") == "Rejected"
    assert _normalize_status("published") == "Published"


def test_extract_content_id_variants():
    assert _extract_content_id("Content ID: CNT-2026-06-29-026") == "CNT-2026-06-29-026"
    assert _extract_content_id("idea_id=WK1-001") == "WK1-001"
    assert _extract_content_id("Review item `CNT-2026-07-03-030` please") == "CNT-2026-07-03-030"
    assert _extract_content_id("No identifier here") == ""


def test_help_and_unknown_commands_do_not_call_llm():
    assert "ContentOps Agent" in _parse_and_run("help", [])
    assert "Unknown command" in _parse_and_run("missing", [])
    assert "Usage" in _parse_and_run("draft-from-idea", [])

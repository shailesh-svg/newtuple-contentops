from tools.slack_client import _build_draft_blocks, _build_plan_blocks, _chunk_text


def test_chunk_text_passthrough_for_short_text():
    assert _chunk_text("short text") == ["short text"]


def test_chunk_text_splits_at_paragraph_boundary():
    # three paragraphs of 1600 chars each — should split since 1600*2 > 3000
    para = "word " * 320  # ~1600 chars
    text = f"{para}\n\n{para}\n\n{para}"
    chunks = _chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= 3000 for c in chunks)


def test_chunk_text_never_exceeds_limit():
    # pathological case: no paragraph breaks in a very long string
    text = "x" * 5000
    chunks = _chunk_text(text)
    assert all(len(c) <= 3000 for c in chunks)


def test_build_draft_blocks_structure():
    blocks = _build_draft_blocks("Draft content here.", "CNT-001")
    types = [b["type"] for b in blocks]

    assert types[0] == "header"
    assert "actions" in types
    assert "section" in types
    assert "context" in types


def test_build_draft_blocks_buttons_have_correct_action_ids():
    blocks = _build_draft_blocks("Draft content.", "CNT-001")
    action_block = next(b for b in blocks if b["type"] == "actions")
    action_ids = {e["action_id"] for e in action_block["elements"]}

    assert action_ids == {"approve_draft", "revise_draft", "reject_draft"}


def test_build_draft_blocks_approve_is_primary_reject_is_danger():
    blocks = _build_draft_blocks("Draft.", "CNT-001")
    action_block = next(b for b in blocks if b["type"] == "actions")
    by_id = {e["action_id"]: e for e in action_block["elements"]}

    assert by_id["approve_draft"].get("style") == "primary"
    assert by_id["reject_draft"].get("style") == "danger"
    assert "style" not in by_id["revise_draft"]  # default (grey)


def test_build_draft_blocks_button_value_is_idea_id():
    blocks = _build_draft_blocks("Draft.", "CNT-999")
    action_block = next(b for b in blocks if b["type"] == "actions")
    for element in action_block["elements"]:
        assert element["value"] == "CNT-999"


def test_build_draft_blocks_context_contains_idea_id():
    blocks = _build_draft_blocks("Draft.", "CNT-002")
    context_block = next(b for b in blocks if b["type"] == "context")
    assert "CNT-002" in context_block["elements"][0]["text"]


def test_build_draft_blocks_long_text_is_chunked_into_sections():
    long_text = "word " * 1000  # ~5000 chars
    blocks = _build_draft_blocks(long_text, "CNT-003")
    section_blocks = [b for b in blocks if b["type"] == "section"]

    assert len(section_blocks) > 1
    assert all(len(b["text"]["text"]) <= 3000 for b in section_blocks)


def test_build_plan_blocks_has_no_action_buttons():
    blocks = _build_plan_blocks("## Week Plan\n\nIdea 1\n\nIdea 2")
    types = [b["type"] for b in blocks]

    assert "actions" not in types
    assert "header" in types
    assert "section" in types


def test_build_plan_blocks_header_is_contentops():
    blocks = _build_plan_blocks("some plan text")
    header = next(b for b in blocks if b["type"] == "header")
    assert "ContentOps" in header["text"]["text"]

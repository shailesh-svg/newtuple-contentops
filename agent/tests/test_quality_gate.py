import quality_gate as qg

GOOD = (
    "Most teams treat a model demo as if it were a production system. "
    "It isn't. The operational reality is that reliability, monitoring, and "
    "clear workflow ownership decide whether an enterprise rollout survives "
    "contact with real users. The implication for any organization scaling "
    "agents is that governance and human review checkpoints matter more than "
    "raw capability. Start this week: audit one workflow and define who owns "
    "each handoff before you ship anything to production."
)


def test_clean_draft_passes():
    result = qg.evaluate_draft(GOOD, bucket="Workflow Wins", voice_score=9)
    assert result["passed"] is True
    assert result["violations"] == []


def test_banned_phrase_blocks():
    text = GOOD + " This is a total game changer."
    result = qg.evaluate_draft(text, bucket="Workflow Wins", voice_score=9)
    assert result["passed"] is False
    assert any(v["rule"] == "banned_phrase" for v in result["violations"])


def test_missing_bucket_blocks():
    result = qg.evaluate_draft(GOOD, bucket="", voice_score=9)
    assert result["passed"] is False
    assert any(v["rule"] == "bucket_missing" for v in result["violations"])


def test_invalid_bucket_blocks():
    result = qg.evaluate_draft(GOOD, bucket="Random Bucket", voice_score=9)
    assert result["passed"] is False
    assert any(v["rule"] == "bucket_invalid" for v in result["violations"])


def test_bucket_match_is_normalised():
    # Case / spacing differences should still match a valid bucket.
    result = qg.evaluate_draft(GOOD, bucket="workflow  wins", voice_score=9)
    assert result["passed"] is True


def test_low_voice_score_blocks():
    result = qg.evaluate_draft(GOOD, bucket="Workflow Wins", voice_score=6)
    assert result["passed"] is False
    assert any(v["rule"] == "voice_score_low" for v in result["violations"])


def test_too_short_blocks():
    result = qg.evaluate_draft("too short", bucket="Workflow Wins", voice_score=9)
    assert result["passed"] is False
    assert any(v["rule"] == "length_min" for v in result["violations"])


def test_missing_voice_score_is_warning_not_block():
    result = qg.evaluate_draft(GOOD, bucket="Workflow Wins", voice_score=None)
    assert result["passed"] is True
    assert any(w["rule"] == "voice_score_missing" for w in result["warnings"])


def test_banned_phrases_loaded_from_brand_file():
    phrases = qg.load_banned_phrases()
    assert "game changer" in phrases
    assert len(phrases) >= 5

from authz import AuthZ


def test_admin_can_run_any_command():
    authz = AuthZ()
    authz.strict = True
    authz.user_roles = {"UADMIN123": "admin"}

    assert authz.can_run_command("UADMIN123", "plan-week")
    assert authz.can_review("UADMIN123", "approve")


def test_viewer_is_limited():
    authz = AuthZ()
    authz.strict = True
    authz.user_roles = {"UVIEWER123": "viewer"}

    assert authz.can_run_command("UVIEWER123", "help")
    assert authz.can_run_command("UVIEWER123", "whoami")
    assert not authz.can_run_command("UVIEWER123", "plan-week")
    assert not authz.can_review("UVIEWER123", "approve")


def test_reviewer_can_review_but_not_draft():
    authz = AuthZ()
    authz.strict = True
    authz.user_roles = {"UREVIEWER123": "reviewer"}

    assert authz.can_review("UREVIEWER123", "approve")
    assert authz.can_review("UREVIEWER123", "revise")
    assert not authz.can_run_command("UREVIEWER123", "draft-from-idea")

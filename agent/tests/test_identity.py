from authz import AuthZ
from identity import Principal


def _authz(strict=True, identities=None, users=None):
    az = AuthZ()
    az.strict = strict
    az.identities = identities or {}
    az.user_roles = users or {}
    return az


def test_raw_id_is_principal_when_no_identity_map():
    az = _authz(users={"U123": "reviewer"})
    p = az.resolve_principal("slack", "U123")
    assert p.id == "U123"
    assert p.role == "reviewer"
    assert p.can("approve") and not p.can("draft-from-idea")


def test_identity_map_resolves_platform_handle_to_principal():
    az = _authz(
        identities={"slack:U123": "alice", "web:alice@co": "alice"},
        users={"alice": "editor"},
    )
    p_slack = az.resolve_principal("slack", "U123")
    p_web = az.resolve_principal("web", "alice@co", display_name="Alice")
    assert p_slack.id == "alice" and p_slack.role == "editor"
    assert p_web.id == "alice" and p_web.role == "editor"
    assert p_web.display_name == "Alice"
    # Same person across two platforms → same permissions.
    assert p_slack.permissions == p_web.permissions
    assert p_slack.can("draft-from-idea")


def test_unknown_principal_gets_default_role():
    az = _authz(strict=True)
    az.default_role = "viewer"
    p = az.resolve_principal("web", "stranger@co")
    assert p.role == "viewer"
    assert p.can("help") and not p.can("approve")


def test_non_strict_allows_everything():
    p = Principal(id="x", display_name="x", platform="cli", role="viewer",
                  permissions=frozenset(), strict=False)
    assert p.can("approve")
    assert p.can("anything")


def test_legacy_can_methods_honour_identity_map():
    az = _authz(identities={"slack:U123": "alice"}, users={"alice": "reviewer"})
    # The legacy Slack-keyed API still works and now honours the identity map.
    assert az.can_review("U123", "approve")
    assert not az.can_run_command("U123", "draft-from-idea")

from modules.collab import create_session_share, join_session, list_collaborators


def test_collab_invite_join_roundtrip():
    token = create_session_share("s1")
    result = join_session(token, "user_b")
    assert result["status"] == "ok"
    members = list_collaborators("s1")
    assert any(m["user_id"] == "user_b" for m in members)

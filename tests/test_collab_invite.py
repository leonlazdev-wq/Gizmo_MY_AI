from modules.collab import create_session_share, join_session, list_collaborators


def test_collab_invite_join_flow():
    token = create_session_share("s1", owner_id="owner")
    data = join_session(token, "user2")
    assert data["session_id"] == "s1"
    users = list_collaborators("s1")
    names = {u["name"] for u in users}
    assert "owner" in names
    assert "user2" in names

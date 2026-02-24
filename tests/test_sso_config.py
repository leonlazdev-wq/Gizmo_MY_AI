from modules.sso import test_connection


def test_sso_mock_success():
    result = test_connection("Google", "cid", "secret", mock_mode=True)
    assert result["status"] == "ok"

from modules.sso import run_sso_test


def test_sso_mock_success():
    result = run_sso_test("Google", "id", "secret", mock_mode=True)
    assert result["ok"] == "true"

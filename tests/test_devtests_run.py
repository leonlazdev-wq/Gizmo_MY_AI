from modules.devtests import run_smoke_tests


def test_smoke_runner_returns_result_dict():
    result = run_smoke_tests()
    assert "ok" in result
    assert "output" in result

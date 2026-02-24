from modules.devtests import run_smoke_tests


def test_devtests_runner_executes():
    result = run_smoke_tests(timeout=120)
    assert "code" in result
    assert isinstance(result["stdout"], str)

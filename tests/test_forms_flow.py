from modules.forms import run_form


def test_bug_report_form_submit():
    result = run_form(
        session_id="s1",
        template_id="bug_report",
        values={
            "title": "Crash on upload",
            "email": "qa@example.com",
            "date": "2026-01-01",
            "severity": "high",
        },
    )
    assert result["status"] == "ok"

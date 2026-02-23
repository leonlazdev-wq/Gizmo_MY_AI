from pathlib import Path

from modules.forms import run_form


def test_bug_report_form_submit():
    out = run_form(
        "s1",
        "bug_report",
        {
            "title": "Crash",
            "email": "a@b.com",
            "date": "2026-01-01",
            "severity": "high",
            "details": "Stack trace...",
        },
    )
    assert Path(out).exists()

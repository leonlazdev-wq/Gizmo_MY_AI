"""Developer test runner utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict


def _run_pytest(args: list[str], timeout: int = 600) -> Dict[str, str]:
    cmd = ["pytest"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    report = Path("user_data/cache/test-report.txt")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    return {
        "ok": str(proc.returncode == 0).lower(),
        "returncode": str(proc.returncode),
        "output": (proc.stdout + "\n" + proc.stderr)[-4000:],
        "report_path": str(report),
    }


def run_smoke_tests() -> Dict[str, str]:
    return _run_pytest(["-q", "tests/test_workflow_run.py", "tests/test_forms_flow.py"])


def run_full_suite() -> Dict[str, str]:
    return _run_pytest(["-q", "tests"])

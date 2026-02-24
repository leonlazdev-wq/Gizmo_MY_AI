"""Developer test runner helpers."""

from __future__ import annotations

import subprocess


def run_smoke_tests(timeout: int = 600) -> dict[str, str | int]:
    """Run smoke tests and capture output."""
    cmd = ["pytest", "-q", "tests/test_workflow_run.py", "tests/test_collab_invite.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    return {"code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def run_full_suite(timeout: int = 600) -> dict[str, str | int]:
    """Run full tests and capture output."""
    proc = subprocess.run(["pytest", "-q", "tests"], capture_output=True, text=True, timeout=timeout, check=False)
    return {"code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}

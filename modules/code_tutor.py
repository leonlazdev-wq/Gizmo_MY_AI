"""Code Tutor & Sandbox Execution module.

Provides `execute_code` which sends code to the public Piston API sandbox
for safe, isolated execution. No code ever runs on the local machine.
"""

from __future__ import annotations

import logging
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

# Public Piston API — no auth required for basic use
PISTON_API_URL = "https://emkc.org/api/v2/piston/execute"

# Map friendly language names to Piston runtime/version strings
_LANGUAGE_MAP = {
    "python":     ("python",     "3.10"),
    "javascript": ("javascript", "18.15.0"),
    "typescript": ("typescript", "5.0.3"),
    "go":         ("go",         "1.16.2"),
    "rust":       ("rust",       "1.50.0"),
    "bash":       ("bash",       "5.2.0"),
}


def execute_code(language: str, code: str, stdin: str = "") -> Tuple[str, str, int, bool]:
    """Execute code in the Piston sandbox.

    Args:
        language: One of "python", "javascript", "typescript", "go", "rust", "bash"
        code:     Source code to execute.
        stdin:    Optional standard input to feed to the program.

    Returns:
        (stdout, stderr, exit_code, success_flag)
        success_flag is False only if the *API call* itself failed (network/timeout),
        not if the user's code produced an error.
    """
    lang_key = language.lower().strip()
    runtime, version = _LANGUAGE_MAP.get(lang_key, ("python", "3.10"))

    payload = {
        "language": runtime,
        "version":  version,
        "files": [{"name": f"main.{_ext(lang_key)}", "content": code}],
        "stdin":    stdin,
    }

    try:
        resp = requests.post(PISTON_API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return "Execution timed out.", "API timeout after 30 seconds.", -1, False
    except requests.exceptions.RequestException as exc:
        return "", f"Piston API error: {exc}", -1, False

    run = data.get("run", {})
    stdout    = run.get("stdout", "") or ""
    stderr    = run.get("stderr", "") or ""
    exit_code = run.get("code", 0) if run.get("code") is not None else 0

    return stdout, stderr, exit_code, True


def _ext(language: str) -> str:
    return {
        "python":     "py",
        "javascript": "js",
        "typescript": "ts",
        "go":         "go",
        "rust":       "rs",
        "bash":       "sh",
    }.get(language, "txt")

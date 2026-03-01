"""Code Tutor & Sandbox Execution module.

Provides `execute_code` which sends code to the public Piston API sandbox
for safe, isolated execution. No code ever runs on the local machine.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

# Public export for UI — dict so that LANGUAGES.keys() works in ui_code_tutor
LANGUAGES: Dict[str, str] = {
    "Python":     "python",
    "JavaScript": "javascript",
    "TypeScript": "typescript",
    "Go":         "go",
    "Rust":       "rust",
    "Bash":       "bash",
}

# Directory for persisted session JSON files
_SESSIONS_DIR = Path("user_data") / "code_tutor_sessions"


def execute_code(language: str, code: str, stdin: str = "") -> Tuple[str, str, str]:
    """Execute code in the Piston sandbox.

    Args:
        language: Display name (e.g. "Python") or internal key (e.g. "python").
        code:     Source code to execute.
        stdin:    Optional standard input to feed to the program.

    Returns:
        (status_string, stdout, stderr)
    """
    # Resolve display name to internal key
    lang_key = LANGUAGES.get(language, language).lower().strip()
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
        return "⚠️ Execution timed out.", "Execution timed out.", "API timeout after 30 seconds."
    except requests.exceptions.RequestException as exc:
        return f"⚠️ API error: {exc}", "", f"Piston API error: {exc}"

    run = data.get("run", {})
    stdout    = run.get("stdout", "") or ""
    stderr    = run.get("stderr", "") or ""
    exit_code = run.get("code", 0) if run.get("code") is not None else 0

    icon = "✅" if exit_code == 0 else "⚠️"
    status = f"{icon} Finished (exit code {exit_code})"
    return status, stdout, stderr


def _ext(language: str) -> str:
    return {
        "python":     "py",
        "javascript": "js",
        "typescript": "ts",
        "go":         "go",
        "rust":       "rs",
        "bash":       "sh",
    }.get(language, "txt")


# ---------------------------------------------------------------------------
# AI Tutor stubs — connect an LLM model here for full functionality
# ---------------------------------------------------------------------------

def explain_concept(concept: str, language: str) -> Tuple[str, str]:
    """Return a placeholder explanation until an LLM is connected."""
    status = "ℹ️ AI model not connected."
    explanation = (
        f"Connect an LLM model to get a full explanation of '{concept}' in {language}.\n"
        "See the model configuration in settings."
    )
    return status, explanation


def get_ai_feedback(code: str, stdout: str, stderr: str, language: str, question: str) -> Tuple[str, str]:
    """Return placeholder feedback until an LLM is connected."""
    status = "ℹ️ AI model not connected."
    feedback = (
        "Connect an LLM model to receive AI-powered code feedback.\n"
        "See the model configuration in settings."
    )
    return status, feedback


def get_ai_hint(code: str, language: str) -> Tuple[str, str]:
    """Return a placeholder hint until an LLM is connected."""
    status = "ℹ️ AI model not connected."
    hint = (
        "Connect an LLM model to get AI-powered hints.\n"
        "See the model configuration in settings."
    )
    return status, hint


# ---------------------------------------------------------------------------
# Session persistence — JSON files under user_data/code_tutor_sessions/
# ---------------------------------------------------------------------------

def list_sessions() -> List[str]:
    """Return session names sorted by modification time (newest first)."""
    if not _SESSIONS_DIR.exists():
        return []
    files = sorted(
        _SESSIONS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [p.stem for p in files]


def save_session(code: str, language: str, stdout: str, stderr: str) -> str:
    """Persist the current session to a JSON file."""
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"session_{timestamp}"
    path = _SESSIONS_DIR / f"{name}.json"
    data = {
        "code":      code,
        "language":  language,
        "stdout":    stdout,
        "stderr":    stderr,
        "timestamp": timestamp,
    }
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return f"✅ Session saved as '{name}'."
    except OSError as exc:
        logger.error("Failed to save session: %s", exc)
        return f"⚠️ Failed to save session: {exc}"


def load_session(name: str) -> Tuple[str, Optional[dict]]:
    """Load a session from its JSON file.

    Returns:
        (status_string, data_dict) where data_dict has keys: code, language, stdout, stderr
        or (error_status, None) on failure.
    """
    path = _SESSIONS_DIR / f"{name}.json"
    if not path.exists():
        return f"⚠️ Session '{name}' not found.", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return f"✅ Session '{name}' loaded.", data
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load session '%s': %s", name, exc)
        return f"⚠️ Failed to load session: {exc}", None

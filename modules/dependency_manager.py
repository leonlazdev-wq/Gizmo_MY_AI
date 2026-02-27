"""Automatic dependency installer for Gizmo integrations.

When an integration (YouTube, Google Docs, PDF, TTS, etc.) needs a library
that isn't installed, call ``ensure_packages()`` instead of showing a manual
``pip install`` error.  The function will:

1.  Check which packages are already importable.
2.  Install the missing ones via ``pip`` in the running interpreter.
3.  Return a user-friendly status string.

All install logs are saved to ``user_data/dep_install.log``.
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_LOG_PATH = os.path.join("user_data", "dep_install.log")

# ---------------------------------------------------------------
#  Registry of known integrations → required pip packages
#  Key   = human-readable integration name
#  Value = list of  (pip_package, import_name)  tuples
#          pip_package  → what to ``pip install``
#          import_name  → what to ``import`` to check availability
# ---------------------------------------------------------------
INTEGRATION_DEPS: Dict[str, List[Tuple[str, str]]] = {
    "YouTube": [
        ("youtube-transcript-api", "youtube_transcript_api"),
        ("pytube", "pytube"),
    ],
    "Google Docs": [
        ("google-api-python-client", "googleapiclient"),
        ("google-auth", "google.auth"),
        ("google-auth-httplib2", "google_auth_httplib2"),
        ("google-auth-oauthlib", "google_auth_oauthlib"),
    ],
    "Google Slides": [
        ("google-api-python-client", "googleapiclient"),
        ("google-auth", "google.auth"),
        ("google-auth-httplib2", "google_auth_httplib2"),
        ("google-auth-oauthlib", "google_auth_oauthlib"),
    ],
    "Google Sheets": [
        ("google-api-python-client", "googleapiclient"),
        ("google-auth", "google.auth"),
        ("google-auth-httplib2", "google_auth_httplib2"),
        ("google-auth-oauthlib", "google_auth_oauthlib"),
    ],
    "Google Calendar": [
        ("google-api-python-client", "googleapiclient"),
        ("google-auth", "google.auth"),
        ("google-auth-httplib2", "google_auth_httplib2"),
        ("google-auth-oauthlib", "google_auth_oauthlib"),
    ],
    "Google Drive": [
        ("google-api-python-client", "googleapiclient"),
        ("google-auth", "google.auth"),
        ("google-auth-httplib2", "google_auth_httplib2"),
        ("google-auth-oauthlib", "google_auth_oauthlib"),
    ],
    "PDF Reader": [
        ("PyPDF2", "PyPDF2"),
        ("fpdf2", "fpdf"),
    ],
    "Voice Chat": [
        ("pyttsx3", "pyttsx3"),
        ("SpeechRecognition", "speech_recognition"),
    ],
    "Text-to-Speech": [
        ("gTTS", "gtts"),
        ("pyttsx3", "pyttsx3"),
    ],
    "Notion": [
        ("requests", "requests"),
    ],
    "Study Planner": [
        ("icalendar", "icalendar"),
    ],
    "Code Tutor": [
        ("requests", "requests"),
    ],
}


def _is_installed(import_name: str) -> bool:
    """Check whether a package is importable."""
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def _log(message: str) -> None:
    """Append a message to the install log file."""
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {message}\n")
    except Exception:
        pass


def ensure_packages(
    integration: str,
    extra_packages: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[bool, str]:
    """Make sure every package needed by *integration* is available.

    Parameters
    ----------
    integration : str
        Key in ``INTEGRATION_DEPS``, e.g. ``"YouTube"``.
    extra_packages : list of (pip_name, import_name), optional
        Additional packages to check beyond the registry.

    Returns
    -------
    (success, message) : (bool, str)
        ``success`` is True when all packages are importable (either they
        already were, or they were installed successfully).
    """
    packages = list(INTEGRATION_DEPS.get(integration, []))
    if extra_packages:
        packages.extend(extra_packages)

    if not packages:
        return True, f"No dependencies listed for '{integration}'."

    missing: List[Tuple[str, str]] = []
    for pip_name, import_name in packages:
        if not _is_installed(import_name):
            missing.append((pip_name, import_name))

    if not missing:
        return True, "✅ All dependencies already installed."

    pip_names = [p[0] for p in missing]
    display = ", ".join(pip_names)
    _log(f"Installing for {integration}: {display}")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", *pip_names],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            _log(f"FAILED: {err}")
            return False, (
                f"❌ Failed to install {display}.\n"
                f"Error: {err}\n"
                f"Try manually: pip install {' '.join(pip_names)}"
            )

        # Verify the packages are now importable
        still_missing = [p for p in missing if not _is_installed(p[1])]
        if still_missing:
            names = ", ".join(p[0] for p in still_missing)
            _log(f"PARTIAL: {names} still not importable after install")
            return False, f"⚠️ Installed but {names} still can't be imported. Try restarting."

        _log(f"SUCCESS: {display}")
        return True, f"✅ Installed: {display}"

    except subprocess.TimeoutExpired:
        _log("TIMEOUT")
        return False, f"❌ Installation timed out for {display}. Try manually."
    except Exception as exc:
        _log(f"ERROR: {exc}")
        return False, f"❌ Installation error: {exc}"


def ensure_single(pip_name: str, import_name: str) -> Tuple[bool, str]:
    """Convenience wrapper: ensure a single package is installed."""
    return ensure_packages("_custom", extra_packages=[(pip_name, import_name)])


def check_integration_status() -> Dict[str, Dict]:
    """Return the install status for every registered integration.

    Returns a dict like::

        {
            "YouTube": {
                "installed": ["pytube"],
                "missing":   ["youtube-transcript-api"],
                "ready":     False,
            },
            ...
        }
    """
    status = {}
    for integration, packages in INTEGRATION_DEPS.items():
        installed = [p[0] for p in packages if _is_installed(p[1])]
        missing = [p[0] for p in packages if not _is_installed(p[1])]
        status[integration] = {
            "installed": installed,
            "missing": missing,
            "ready": len(missing) == 0,
        }
    return status


def get_install_log() -> str:
    """Return the contents of the install log file."""
    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "(no install log yet)"
    except Exception as exc:
        return f"Error reading log: {exc}"

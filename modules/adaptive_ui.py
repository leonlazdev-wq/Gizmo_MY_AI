"""Adaptive contextual toolbar suggestions."""

from __future__ import annotations

import re
from typing import Dict


def suggest_actions(text: str, has_attachment: bool = False) -> Dict[str, bool]:
    """Return visibility flags for action buttons."""
    clean = (text or "").strip()
    long_message = len(clean) > 50
    has_code = bool(re.search(r"```|\b(def |class |SELECT |function )", clean, re.IGNORECASE))
    return {
        "summarize": long_message,
        "action_items": long_message,
        "find_bugs": has_code,
        "create_task": long_message or has_attachment,
    }


def summarize_text(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    top = lines[:3] if lines else [text[:160]]
    return "\n".join(f"- {l[:140]}" for l in top)

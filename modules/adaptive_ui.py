"""Adaptive toolbar suggestion logic."""

from __future__ import annotations

import re


def suggest_actions(message_text: str, has_attachments: bool = False) -> list[str]:
    """Return action suggestions for a message."""
    text = (message_text or "").strip()
    suggestions: list[str] = []
    if len(text) > 50:
        suggestions.extend(["summarize", "action_items"])
    if has_attachments:
        suggestions.append("create_task")
    if re.search(r"```|def\s+\w+\(|class\s+\w+", text):
        suggestions.append("find_bugs")
    return list(dict.fromkeys(suggestions))


def summarize_text(message_text: str) -> str:
    """Create a simple 3-line summary."""
    words = message_text.split()
    if not words:
        return ""
    chunk = max(1, len(words) // 3)
    lines = [
        " ".join(words[:chunk]),
        " ".join(words[chunk: 2 * chunk]),
        " ".join(words[2 * chunk:]),
    ]
    return "\n".join(line.strip() for line in lines if line.strip())

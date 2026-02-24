"""Message-level actions for chat history."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

USER_DATA_DIR = Path("user_data")
SNIPPETS_FILE = USER_DATA_DIR / "saved_snippets.json"
OUTPUTS_DIR = USER_DATA_DIR / "outputs"


class MessageActions:
    """Handles message actions for editing, branching, snippets, and export."""

    def __init__(self) -> None:
        self.message_branches: Dict[str, Dict[str, Any]] = {}
        self.saved_snippets: List[Dict[str, Any]] = self._load_snippets()

    def _load_snippets(self) -> List[Dict[str, Any]]:
        if not SNIPPETS_FILE.exists():
            return []
        try:
            return json.loads(SNIPPETS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_snippets(self) -> None:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        SNIPPETS_FILE.write_text(json.dumps(self.saved_snippets, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize_history(history: Dict[str, Any]) -> Tuple[List[List[Any]], List[List[Any]], Dict[str, Any]]:
        return history.get("internal", []), history.get("visible", []), history.get("metadata", {})

    def edit_message(self, history: Dict[str, Any], msg_index: int, new_content: str) -> tuple[Dict[str, Any], str]:
        internal, visible, metadata = self._normalize_history(history)
        if msg_index < 0 or msg_index >= len(visible):
            return history, "❌ Invalid message index"

        current = visible[msg_index]
        if len(current) != 2:
            return history, "❌ Message format is invalid"

        role_idx = 1 if current[0] in (None, "") else 0
        visible[msg_index][role_idx] = new_content
        if msg_index < len(internal) and len(internal[msg_index]) > role_idx:
            internal[msg_index][role_idx] = new_content

        return {"internal": internal, "visible": visible, "metadata": metadata}, f"✅ Message {msg_index + 1} edited"

    def branch_conversation(self, history: Dict[str, Any], branch_point: int) -> tuple[Dict[str, Any], str]:
        internal, visible, metadata = self._normalize_history(history)
        if branch_point < 0:
            branch_point = 0
        branch_point = min(branch_point, len(visible))

        branch_id = f"branch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        branch_history = {
            "internal": internal[:branch_point],
            "visible": visible[:branch_point],
            "metadata": {**metadata, "branch_id": branch_id},
        }
        self.message_branches[branch_id] = branch_history
        return branch_history, f"🌿 Created branch: {branch_id}"

    def save_snippet(self, history: Dict[str, Any], msg_index: int, category: str = "general") -> str:
        visible = history.get("visible", [])
        if msg_index < 0 or msg_index >= len(visible):
            return "❌ Invalid message index"

        snippet = {
            "id": len(self.saved_snippets),
            "message": visible[msg_index],
            "category": category,
            "timestamp": datetime.now().isoformat(),
        }
        self.saved_snippets.append(snippet)
        self._save_snippets()
        return f"💾 Saved snippet #{snippet['id']}"

    def export_selection(self, history: Dict[str, Any], start_idx: int, end_idx: int, export_format: str = "markdown") -> str:
        visible = history.get("visible", [])
        if not visible:
            return "❌ No messages to export"

        if end_idx < 0 or end_idx > len(visible):
            end_idx = len(visible)
        start_idx = max(0, start_idx)
        if start_idx >= end_idx:
            return "❌ Invalid export range"

        segment = visible[start_idx:end_idx]
        exported_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

        if export_format == "json":
            content = json.dumps({"conversation": segment, "exported_at": exported_at}, indent=2)
            suffix = "json"
        elif export_format == "txt":
            content = "\n\n".join([f"User: {m[0]}\nAssistant: {m[1]}" for m in segment])
            suffix = "txt"
        else:
            content = "# Conversation Export\n\n"
            for idx, msg in enumerate(segment, start=1):
                content += f"## Message {idx}\n**User:** {msg[0]}\n\n**Assistant:** {msg[1]}\n\n---\n\n"
            suffix = "md"

        path = OUTPUTS_DIR / f"chat_export_{exported_at}.{suffix}"
        path.write_text(content, encoding="utf-8")
        return f"✅ Exported to {path.as_posix()}"

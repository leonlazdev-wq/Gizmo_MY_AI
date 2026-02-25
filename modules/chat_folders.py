"""
chat_folders.py — Backend logic for organising chats into named folders.

Storage: user_data/chat_folders.json
Schema:
{
    "folders": [
        {"id": "f1", "name": "Math", "color": "#4CAF50", "created": "2026-02-25"}
    ],
    "assignments": {
        "20260225-14-30-00": "f1"
    }
}
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

FOLDERS_FILE = Path("user_data/chat_folders.json")


def load_folders() -> dict:
    """Load folder structure from file."""
    if FOLDERS_FILE.exists():
        return json.loads(FOLDERS_FILE.read_text(encoding='utf-8'))
    return {"folders": [], "assignments": {}}


def save_folders(data: dict):
    """Save folder structure to file."""
    FOLDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FOLDERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def create_folder(name: str, color: str = "#4F46E5") -> dict:
    """Create a new folder and return the folder dict."""
    data = load_folders()
    folder = {
        "id": str(uuid.uuid4())[:8],
        "name": name.strip(),
        "color": color,
        "created": datetime.now().strftime("%Y-%m-%d"),
    }
    data["folders"].append(folder)
    save_folders(data)
    return folder


def delete_folder(folder_id: str):
    """Delete a folder. Chats become unassigned but are not deleted."""
    data = load_folders()
    data["folders"] = [f for f in data["folders"] if f["id"] != folder_id]
    data["assignments"] = {
        chat_id: fid
        for chat_id, fid in data["assignments"].items()
        if fid != folder_id
    }
    save_folders(data)


def rename_folder(folder_id: str, new_name: str):
    """Rename a folder."""
    data = load_folders()
    for folder in data["folders"]:
        if folder["id"] == folder_id:
            folder["name"] = new_name.strip()
            break
    save_folders(data)


def assign_chat_to_folder(chat_id: str, folder_id: str):
    """Assign a chat to a folder."""
    data = load_folders()
    data["assignments"][chat_id] = folder_id
    save_folders(data)


def unassign_chat(chat_id: str):
    """Remove a chat from its folder."""
    data = load_folders()
    data["assignments"].pop(chat_id, None)
    save_folders(data)


def get_chats_in_folder(folder_id: str) -> list:
    """Return all chat IDs assigned to a folder."""
    data = load_folders()
    return [
        chat_id
        for chat_id, fid in data["assignments"].items()
        if fid == folder_id
    ]


def get_folder_for_chat(chat_id: str):
    """Return the folder ID for a chat, or None if unassigned."""
    data = load_folders()
    return data["assignments"].get(chat_id)


def get_folder_list() -> list:
    """Return a list of folder names for use in dropdowns."""
    data = load_folders()
    return [f["name"] for f in data["folders"]]

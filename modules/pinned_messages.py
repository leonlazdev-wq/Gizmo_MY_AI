"""
pinned_messages.py — Backend logic for pinning/unpinning chat messages.

Pins are stored in two places:
1. The chat's `metadata` dict (inline, per-message flag).
2. A cross-chat index at user_data/pinned_messages.json for quick lookup.
"""

import json
from datetime import datetime
from pathlib import Path

PINS_FILE = Path("user_data/pinned_messages.json")


def _load_pins() -> dict:
    if PINS_FILE.exists():
        return json.loads(PINS_FILE.read_text(encoding='utf-8'))
    return {"pins": []}


def _save_pins(data: dict):
    PINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PINS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def _meta_key(message_index: int, role: str) -> str:
    return f"{role}_{message_index}"


def pin_message(
    history: dict,
    chat_id: str,
    character: str,
    mode: str,
    message_index: int,
    role: str,
    note: str = "",
) -> dict:
    """Pin a message and update the cross-chat index. Returns updated history."""
    history = dict(history)
    metadata = dict(history.get("metadata", {}))
    key = _meta_key(message_index, role)
    entry = dict(metadata.get(key, {}))
    entry["pinned"] = True
    if note:
        entry["pin_note"] = note
    metadata[key] = entry
    history["metadata"] = metadata

    # Derive preview text
    preview = ""
    internal = history.get("internal", [])
    if 0 <= message_index < len(internal):
        pair = internal[message_index]
        text = pair[1] if role == "assistant" else pair[0]
        preview = (text or "")[:100]

    # Update cross-chat index
    pins_data = _load_pins()
    # Remove existing entry for this message if present
    pins_data["pins"] = [
        p for p in pins_data["pins"]
        if not (
            p["chat_id"] == chat_id
            and p["message_index"] == message_index
            and p["role"] == role
        )
    ]
    pins_data["pins"].append({
        "chat_id": chat_id,
        "character": character,
        "mode": mode,
        "message_index": message_index,
        "role": role,
        "preview": preview,
        "note": note,
        "pinned_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    _save_pins(pins_data)
    return history


def unpin_message(history: dict, chat_id: str, message_index: int, role: str) -> dict:
    """Unpin a message. Returns updated history."""
    history = dict(history)
    metadata = dict(history.get("metadata", {}))
    key = _meta_key(message_index, role)
    entry = dict(metadata.get(key, {}))
    entry.pop("pinned", None)
    entry.pop("pin_note", None)
    metadata[key] = entry
    history["metadata"] = metadata

    # Remove from cross-chat index
    pins_data = _load_pins()
    pins_data["pins"] = [
        p for p in pins_data["pins"]
        if not (
            p["chat_id"] == chat_id
            and p["message_index"] == message_index
            and p["role"] == role
        )
    ]
    _save_pins(pins_data)
    return history


def get_pinned_messages(chat_id: str = None) -> list:
    """Return pinned messages, optionally filtered by chat."""
    pins_data = _load_pins()
    pins = pins_data["pins"]
    if chat_id is not None:
        pins = [p for p in pins if p["chat_id"] == chat_id]
    return pins


def is_pinned(history: dict, message_index: int, role: str) -> bool:
    """Return True if the specified message is pinned."""
    metadata = history.get("metadata", {})
    key = _meta_key(message_index, role)
    return bool(metadata.get(key, {}).get("pinned", False))


def update_pin_note(chat_id: str, message_index: int, role: str, note: str):
    """Update the note on a pinned message in the cross-chat index."""
    pins_data = _load_pins()
    for pin in pins_data["pins"]:
        if (
            pin["chat_id"] == chat_id
            and pin["message_index"] == message_index
            and pin["role"] == role
        ):
            pin["note"] = note
            break
    _save_pins(pins_data)

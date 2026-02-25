"""Chat Memory backend – persist user facts across sessions."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from modules.logging_colors import logger

_MEMORY_PATH = Path("user_data/memory.json")
_CATEGORIES = ["personal", "preferences", "academic", "work", "other"]


def _load_memories() -> list[dict]:
    if not _MEMORY_PATH.exists():
        return []
    try:
        return json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_memories(memories: list[dict]) -> None:
    _MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY_PATH.write_text(json.dumps(memories, indent=2, ensure_ascii=False), encoding="utf-8")


def add_memory(fact: str, category: str = "other") -> tuple[str, list[list]]:
    """Add a new memory fact."""
    fact = (fact or "").strip()
    if not fact:
        return "⚠️ Enter a fact to save.", get_memory_table()

    memories = _load_memories()
    # Simple dedup
    existing_facts = {m["fact"].lower() for m in memories}
    if fact.lower() in existing_facts:
        return "ℹ️ This fact is already in memory.", get_memory_table()

    memories.append({
        "fact": fact,
        "category": category or "other",
        "created": datetime.utcnow().isoformat() + "Z",
        "source": "manual"
    })
    _save_memories(memories)
    return f"✅ Saved: \"{fact}\"", get_memory_table()


def delete_memory(fact: str) -> tuple[str, list[list]]:
    """Delete a memory fact by exact match."""
    fact = (fact or "").strip()
    memories = _load_memories()
    before = len(memories)
    memories = [m for m in memories if m["fact"] != fact]
    _save_memories(memories)
    removed = before - len(memories)
    return f"✅ Removed {removed} fact(s).", get_memory_table()


def get_memory_table(search: str = "") -> list[list]:
    """Return memories as a list of rows for Dataframe display."""
    memories = _load_memories()
    if search:
        search_lower = search.lower()
        memories = [m for m in memories if search_lower in m["fact"].lower() or search_lower in m.get("category", "").lower()]
    return [
        [m["fact"], m.get("category", "other"), m.get("created", "")[:10], m.get("source", "manual")]
        for m in memories
    ]


def get_memory_stats() -> str:
    memories = _load_memories()
    if not memories:
        return "No memories saved yet."
    total = len(memories)
    cats: dict[str, int] = {}
    for m in memories:
        c = m.get("category", "other")
        cats[c] = cats.get(c, 0) + 1
    breakdown = ", ".join(f"{c}: {n}" for c, n in sorted(cats.items()))
    return f"Total facts: {total} | {breakdown}"


def get_memory_context() -> str:
    """Build the memory injection block for system prompt prepending."""
    memories = _load_memories()
    if not memories:
        return ""
    lines = "\n".join(f"- {m['fact']} ({m.get('category', 'other')})" for m in memories)
    return f"[User Memory]\n{lines}\n"


def export_memories() -> str | None:
    """Return path to memory.json for download."""
    if _MEMORY_PATH.exists():
        return str(_MEMORY_PATH)
    return None


def import_memories(file_path: str) -> tuple[str, list[list]]:
    """Import memories from an uploaded JSON file."""
    try:
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return "⚠️ Invalid format. Expected a JSON array.", get_memory_table()
        existing = _load_memories()
        existing_facts = {m["fact"].lower() for m in existing}
        added = 0
        for item in data:
            if isinstance(item, dict) and "fact" in item:
                if item["fact"].lower() not in existing_facts:
                    existing.append(item)
                    existing_facts.add(item["fact"].lower())
                    added += 1
        _save_memories(existing)
        return f"✅ Imported {added} new facts.", get_memory_table()
    except Exception as exc:
        return f"❌ Import failed: {exc}", get_memory_table()


def auto_extract_memories(conversation_text: str) -> tuple[str, list[list]]:
    """Ask the AI to extract personal facts from recent conversation."""
    try:
        from modules import shared
        from modules.text_generation import generate_reply

        if shared.model is None:
            return "⚠️ No model loaded.", get_memory_table()

        prompt = (
            "Extract any personal facts or preferences the user mentioned in the following conversation. "
            "Return ONLY a JSON array of objects with 'fact' and 'category' keys (categories: personal, preferences, academic, work, other). "
            "Return an empty array [] if no facts are present.\n\n"
            f"Conversation:\n{conversation_text}\n\nJSON:"
        )
        state = {"max_new_tokens": 256, "temperature": 0.3}
        response = ""
        for chunk in generate_reply(prompt, state):
            if isinstance(chunk, str):
                response = chunk
            elif isinstance(chunk, list):
                response = chunk[0] if chunk else response

        # Extract JSON from response
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if not match:
            return "ℹ️ No facts extracted.", get_memory_table()

        facts = json.loads(match.group())
        if not isinstance(facts, list):
            return "ℹ️ No facts extracted.", get_memory_table()

        existing = _load_memories()
        existing_facts = {m["fact"].lower() for m in existing}
        added = 0
        for item in facts:
            if isinstance(item, dict) and "fact" in item:
                if item["fact"].lower() not in existing_facts:
                    item["source"] = "auto"
                    item["created"] = datetime.utcnow().isoformat() + "Z"
                    existing.append(item)
                    existing_facts.add(item["fact"].lower())
                    added += 1
        _save_memories(existing)
        return f"✅ Auto-extracted {added} new facts.", get_memory_table()
    except Exception as exc:
        logger.error(f"Auto-extract error: {exc}")
        return f"❌ Error: {exc}", get_memory_table()

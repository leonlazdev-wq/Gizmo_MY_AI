"""Flashcard generator backend for Gizmo."""

from __future__ import annotations

import csv
import json
import os
from typing import Dict, List, Optional, Tuple

_FLASHCARDS_DIR = os.path.join("user_data", "flashcards")


def _ensure_dirs() -> None:
    """Create user_data/flashcards/ directory if it doesn't exist."""
    os.makedirs(_FLASHCARDS_DIR, exist_ok=True)


def _call_ai(prompt: str):
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = 1024
        from modules.text_generation import generate_reply
        output = ""
        for chunk in generate_reply(prompt, state, stopping_strings=[], is_chat=False):
            if isinstance(chunk, str):
                output = chunk
            elif isinstance(chunk, (list, tuple)) and len(chunk) > 0:
                output = chunk[0] if isinstance(chunk[0], str) else str(chunk[0])
        return output.strip(), None
    except Exception as exc:
        return None, f"❌ AI error: {exc}"


def _parse_flashcards(ai_output: str, difficulty: str = "medium") -> List[Dict]:
    """Parse AI output into a list of flashcard dicts."""
    flashcards: List[Dict] = []
    lines = [line.strip() for line in ai_output.splitlines() if line.strip()]

    current_q: Optional[str] = None
    current_a: Optional[str] = None

    for line in lines:
        # Match patterns like "Q: ..." / "A: ..." or "1. Q: ..." / "1. A: ..."
        q_match = False
        a_match = False

        lower = line.lower()
        if lower.startswith("q:") or lower.startswith("question:"):
            q_match = True
            current_q = line.split(":", 1)[1].strip()
        elif lower.startswith("a:") or lower.startswith("answer:"):
            a_match = True
            current_a = line.split(":", 1)[1].strip()
        else:
            # Try numbered format: "1. question text" / "   answer text"
            import re
            num_match = re.match(r'^\d+[\.\)]\s*(.+)', line)
            if num_match:
                if current_q is None:
                    current_q = num_match.group(1)
                elif current_a is None:
                    current_a = num_match.group(1)

        if current_q and current_a:
            flashcards.append({
                "front": current_q,
                "back": current_a,
                "tags": [],
                "difficulty": difficulty,
            })
            current_q = None
            current_a = None

    return flashcards


def generate_flashcards(
    text_or_topic: str,
    count: int = 10,
    difficulty: str = "medium",
) -> Tuple[str, List[Dict]]:
    """Generate flashcards from a topic or text using AI."""
    prompt = (
        f"Generate {count} flashcard question-answer pairs about the following topic or text. "
        f"Format each pair as:\nQ: <question>\nA: <answer>\n\n"
        f"Difficulty level: {difficulty}\n\n"
        f"Topic/Text:\n{text_or_topic[:4000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, []

    flashcards = _parse_flashcards(output, difficulty)
    if not flashcards:
        return "⚠️ Could not parse flashcards from AI output. Try again.", []

    return f"✅ Generated {len(flashcards)} flashcard(s).", flashcards


def generate_from_pdf(file_path: str, count: int = 10) -> Tuple[str, List[Dict]]:
    """Load PDF text and generate flashcards from it."""
    try:
        from modules.pdf_reader import get_all_text
        msg, text = get_all_text(file_path)
        if not text:
            return msg, []
    except Exception as exc:
        return f"❌ Failed to read PDF: {exc}", []

    return generate_flashcards(text[:5000], count=count)


def generate_from_notes(notes_text: str, count: int = 10) -> Tuple[str, List[Dict]]:
    """Generate flashcards from notes text."""
    return generate_flashcards(notes_text, count=count)


def export_anki(flashcards: List[Dict], output_path: str) -> str:
    """Export flashcards as an Anki-compatible TSV file (front\\tback per line)."""
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            for card in flashcards:
                f.write(f"{card['front']}\t{card['back']}\n")
        return f"✅ Exported {len(flashcards)} flashcard(s) to Anki TSV: {output_path}"
    except Exception as exc:
        return f"❌ Failed to export Anki file: {exc}"


def export_json(flashcards: List[Dict], output_path: str) -> str:
    """Export flashcards as a JSON file."""
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(flashcards, f, indent=2, ensure_ascii=False)
        return f"✅ Exported {len(flashcards)} flashcard(s) to JSON: {output_path}"
    except Exception as exc:
        return f"❌ Failed to export JSON: {exc}"


def export_csv(flashcards: List[Dict], output_path: str) -> str:
    """Export flashcards as a CSV file."""
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["front", "back", "tags", "difficulty"])
            writer.writeheader()
            for card in flashcards:
                row = dict(card)
                row["tags"] = ",".join(card.get("tags", []))
                writer.writerow(row)
        return f"✅ Exported {len(flashcards)} flashcard(s) to CSV: {output_path}"
    except Exception as exc:
        return f"❌ Failed to export CSV: {exc}"


def save_deck(name: str, flashcards: List[Dict]) -> str:
    """Save a flashcard deck to user_data/flashcards/{name}.json."""
    _ensure_dirs()
    # Sanitize name for file system
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    if not safe_name:
        return "❌ Invalid deck name."

    file_path = os.path.join(_FLASHCARDS_DIR, f"{safe_name}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(flashcards, f, indent=2, ensure_ascii=False)
        return f"✅ Saved deck '{safe_name}' ({len(flashcards)} cards) to {file_path}."
    except Exception as exc:
        return f"❌ Failed to save deck: {exc}"


def load_deck(name: str) -> Tuple[str, List[Dict]]:
    """Load a flashcard deck from user_data/flashcards/{name}.json."""
    _ensure_dirs()
    file_path = os.path.join(_FLASHCARDS_DIR, f"{name}.json")
    if not os.path.isfile(file_path):
        return f"❌ Deck '{name}' not found at {file_path}.", []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            flashcards = json.load(f)
        return f"✅ Loaded deck '{name}' ({len(flashcards)} cards).", flashcards
    except Exception as exc:
        return f"❌ Failed to load deck: {exc}", []


def list_decks() -> List[str]:
    """Return a list of deck names from user_data/flashcards/."""
    _ensure_dirs()
    try:
        files = [f for f in os.listdir(_FLASHCARDS_DIR) if f.endswith(".json")]
        return [os.path.splitext(f)[0] for f in sorted(files)]
    except Exception:
        return []

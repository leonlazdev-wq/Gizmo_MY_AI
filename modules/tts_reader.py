"""Text-to-Speech Reader backend for Gizmo."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, List, Optional, Tuple

_TTS_SETTINGS_FILE = os.path.join("user_data", "tts_settings.json")

TTS_LANGUAGES = [
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Chinese (Simplified)", "zh-CN"),
    ("Chinese (Traditional)", "zh-TW"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Arabic", "ar"),
    ("Russian", "ru"),
    ("Hindi", "hi"),
    ("Dutch", "nl"),
    ("Swedish", "sv"),
    ("Polish", "pl"),
    ("Turkish", "tr"),
    ("Vietnamese", "vi"),
    ("Thai", "th"),
    ("Indonesian", "id"),
]

READING_MODES = ["Full document", "Paragraph by paragraph", "Flashcard mode"]


def _ensure_dirs() -> None:
    os.makedirs(os.path.dirname(_TTS_SETTINGS_FILE), exist_ok=True)


def _default_settings() -> Dict:
    return {
        "engine": "gtts",
        "language": "en",
        "speed": 1.0,
        "auto_play": False,
        "reading_mode": "Full document",
    }


def load_settings() -> Dict:
    """Load TTS settings from file."""
    if os.path.isfile(_TTS_SETTINGS_FILE):
        try:
            with open(_TTS_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _default_settings()


def save_settings(settings: Dict) -> str:
    """Save TTS settings to file."""
    _ensure_dirs()
    try:
        with open(_TTS_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return "✅ Settings saved."
    except Exception as exc:
        return f"❌ Failed to save settings: {exc}"


def detect_tts_engine() -> Tuple[str, str]:
    """Detect available TTS engine. Returns (engine_name, status_message)."""
    try:
        import gtts  # noqa: F401
        return "gtts", "✅ gTTS (Google Text-to-Speech) available."
    except ImportError:
        pass
    try:
        import pyttsx3  # noqa: F401
        return "pyttsx3", "✅ pyttsx3 (offline TTS) available."
    except ImportError:
        pass
    return "none", (
        "❌ No TTS engine found.\n"
        "Install gTTS: `pip install gTTS`\n"
        "Or install pyttsx3: `pip install pyttsx3`"
    )


def generate_audio(
    text: str,
    language_code: str = "en",
    speed: float = 1.0,
    engine: str = "auto",
) -> Tuple[Optional[str], str]:
    """Generate audio from text. Returns (audio_file_path, status_message)."""
    if not text.strip():
        return None, "❌ No text provided."

    if engine == "auto":
        engine, _ = detect_tts_engine()

    if engine == "none":
        return None, "❌ No TTS engine available. Install gTTS or pyttsx3."

    try:
        tmp_path = os.path.join(tempfile.gettempdir(), "gizmo_tts_output.mp3")

        if engine == "gtts":
            from gtts import gTTS
            # gTTS doesn't support speed directly; we use slow=True for 0.5x
            slow = speed < 0.8
            tts = gTTS(text=text[:5000], lang=language_code, slow=slow)
            tts.save(tmp_path)
            return tmp_path, "✅ Audio generated with gTTS."

        elif engine == "pyttsx3":
            import pyttsx3
            engine_obj = pyttsx3.init()
            # Set rate: default ~200 wpm, scale by speed
            rate = engine_obj.getProperty('rate')
            engine_obj.setProperty('rate', int(rate * speed))
            engine_obj.save_to_file(text[:5000], tmp_path)
            engine_obj.runAndWait()
            return tmp_path, "✅ Audio generated with pyttsx3."

    except Exception as exc:
        return None, f"❌ TTS error: {exc}"

    return None, "❌ Unknown TTS engine."


def extract_text_from_file(file_path: str) -> Tuple[str, str]:
    """Extract text from a PDF, TXT, or MD file. Returns (text, status)."""
    if not file_path:
        return "", "❌ No file provided."

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        try:
            from modules.pdf_reader import get_all_text
            status, text = get_all_text(file_path)
            return text or "", status
        except Exception as exc:
            return "", f"❌ Failed to read PDF: {exc}"

    elif ext in (".txt", ".md"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            return text, f"✅ Loaded {ext.upper()} file ({len(text)} characters)."
        except Exception as exc:
            return "", f"❌ Failed to read file: {exc}"

    return "", f"❌ Unsupported file type: {ext}"


def split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    return paragraphs


def load_from_notes() -> Tuple[List[str], str]:
    """Load available note titles from user_data/notes/."""
    notes_dir = os.path.join("user_data", "notes")
    if not os.path.isdir(notes_dir):
        return [], "No notes found."
    try:
        files = [f for f in os.listdir(notes_dir) if f.endswith((".txt", ".md", ".json"))]
        return sorted(files), f"Found {len(files)} note(s)."
    except Exception:
        return [], "Could not read notes directory."


def load_note_text(note_filename: str) -> Tuple[str, str]:
    """Load text from a note file."""
    notes_dir = os.path.join("user_data", "notes")
    fpath = os.path.join(notes_dir, note_filename)
    if not os.path.isfile(fpath):
        return "", f"❌ Note '{note_filename}' not found."
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            if note_filename.endswith(".json"):
                data = json.load(f)
                text = data.get("content", data.get("text", str(data)))
            else:
                text = f.read()
        return text, f"✅ Loaded note '{note_filename}'."
    except Exception as exc:
        return "", f"❌ Failed to load note: {exc}"


def load_from_flashcards(deck_name: str) -> Tuple[str, str]:
    """Load flashcard deck content as readable text."""
    try:
        from modules.flashcard_generator import load_deck
        msg, cards = load_deck(deck_name)
        if not cards:
            return "", msg
        lines = []
        for i, card in enumerate(cards, 1):
            front = card.get("front", card.get("question", ""))
            back = card.get("back", card.get("answer", ""))
            lines.append(f"Card {i}: {front}")
            lines.append(f"Answer: {back}")
            lines.append("")
        return "\n".join(lines), f"✅ Loaded {len(cards)} flashcards from '{deck_name}'."
    except Exception as exc:
        return "", f"❌ Failed to load flashcards: {exc}"

"""Multi-Language Translation backend for Gizmo."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

_TRANSLATIONS_DIR = os.path.join("user_data", "translations")

LANGUAGES = [
    "Auto-detect",
    "English",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Japanese",
    "Korean",
    "Arabic",
    "Russian",
    "Hindi",
    "Dutch",
    "Swedish",
    "Polish",
    "Turkish",
    "Vietnamese",
    "Thai",
    "Indonesian",
]

TARGET_LANGUAGES = [lang for lang in LANGUAGES if lang != "Auto-detect"]


def _ensure_dirs() -> None:
    """Create user_data/translations/ directory if it doesn't exist."""
    os.makedirs(_TRANSLATIONS_DIR, exist_ok=True)


def _call_ai(prompt: str) -> Tuple[Optional[str], Optional[str]]:
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


def detect_language(text: str) -> Tuple[str, Optional[str]]:
    """Detect the language of the given text using the AI model."""
    if not text.strip():
        return "", "❌ No text provided."
    prompt = (
        "Identify the language of the following text. "
        "Reply with only the language name (e.g. English, Spanish, French).\n\n"
        f"Text:\n{text[:500]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return "", error
    return output or "", None


def translate_text(
    text: str,
    source_lang: str,
    target_lang: str,
) -> Tuple[str, Optional[str]]:
    """Translate text from source_lang to target_lang using AI."""
    if not text.strip():
        return "", "❌ No text provided."
    if not target_lang or target_lang == "Auto-detect":
        return "", "❌ Please select a valid target language."

    if source_lang and source_lang != "Auto-detect":
        lang_hint = f"from {source_lang} "
    else:
        lang_hint = ""

    prompt = (
        f"Translate the following text {lang_hint}to {target_lang}. "
        "Provide only the translation, no explanations or extra text.\n\n"
        f"Text:\n{text[:4000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return "", error
    return output or "", None


def explain_grammar(translated_text: str, target_lang: str) -> Tuple[str, Optional[str]]:
    """Explain grammar structures used in the translated text."""
    if not translated_text.strip():
        return "", "❌ No translated text provided."
    prompt = (
        f"Explain the grammar structures, verb conjugations, and sentence patterns "
        f"used in the following {target_lang} text. "
        "Format your explanation clearly for a language learner.\n\n"
        f"Text:\n{translated_text[:2000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return "", error
    return output or "", None


def extract_vocabulary(translated_text: str, target_lang: str) -> Tuple[str, Optional[str]]:
    """Extract key vocabulary from the translated text with definitions."""
    if not translated_text.strip():
        return "", "❌ No translated text provided."
    prompt = (
        f"Extract key words and phrases from the following {target_lang} text. "
        "For each word/phrase provide:\n"
        "- The word/phrase\n"
        "- Its definition\n"
        "- An example sentence\n\n"
        f"Text:\n{translated_text[:2000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return "", error
    return output or "", None


def pronunciation_guide(translated_text: str, target_lang: str) -> Tuple[str, Optional[str]]:
    """Provide phonetic/romanized pronunciation for the translated text."""
    if not translated_text.strip():
        return "", "❌ No translated text provided."
    prompt = (
        f"Provide a pronunciation guide for the following {target_lang} text. "
        "Include phonetic spelling or romanization for each word/phrase. "
        "Format it clearly so a learner can follow along.\n\n"
        f"Text:\n{translated_text[:2000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return "", error
    return output or "", None


def save_translation(
    source_text: str,
    translated_text: str,
    source_lang: str,
    target_lang: str,
) -> str:
    """Save a translation to user_data/translations/ as JSON."""
    _ensure_dirs()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now().isoformat(),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "source_text": source_text,
        "translated_text": translated_text,
    }
    file_path = os.path.join(_TRANSLATIONS_DIR, f"{entry['id']}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        return f"✅ Translation saved (id: {entry['id']})."
    except Exception as exc:
        return f"❌ Failed to save translation: {exc}"


def list_translations() -> List[Dict]:
    """Return a list of saved translations sorted by timestamp (newest first)."""
    _ensure_dirs()
    results = []
    try:
        for fname in os.listdir(_TRANSLATIONS_DIR):
            if fname.endswith(".json"):
                fpath = os.path.join(_TRANSLATIONS_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append(data)
                except Exception:
                    pass
    except Exception:
        pass
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results


def delete_translation(translation_id: str) -> str:
    """Delete a saved translation by its ID."""
    _ensure_dirs()
    file_path = os.path.join(_TRANSLATIONS_DIR, f"{translation_id}.json")
    if not os.path.isfile(file_path):
        return f"❌ Translation '{translation_id}' not found."
    try:
        os.remove(file_path)
        return f"✅ Translation '{translation_id}' deleted."
    except Exception as exc:
        return f"❌ Failed to delete: {exc}"


def word_count(text: str) -> str:
    """Return a word/character count summary for the given text."""
    words = len(text.split()) if text.strip() else 0
    chars = len(text)
    return f"{words} words, {chars} characters"

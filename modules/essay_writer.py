"""Essay Outliner & Writing Coach backend for Gizmo."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

_ESSAYS_DIR = os.path.join("user_data", "essays")

ESSAY_TYPES = [
    "Argumentative",
    "Persuasive",
    "Expository",
    "Narrative",
    "Compare & Contrast",
    "Research Paper",
]

ACADEMIC_LEVELS = [
    "High School",
    "Undergraduate",
    "Graduate",
]


def _ensure_dirs() -> None:
    """Create user_data/essays/ directory if it doesn't exist."""
    os.makedirs(_ESSAYS_DIR, exist_ok=True)


def _call_ai(prompt: str, max_tokens: int = 1024) -> Tuple[Optional[str], Optional[str]]:
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = max_tokens
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


def generate_outline(
    topic: str,
    essay_type: str,
    word_count: int,
    academic_level: str,
) -> Tuple[str, Optional[str]]:
    """Generate a structured essay outline using AI."""
    if not topic.strip():
        return "", "❌ Please enter an essay topic."
    prompt = (
        f"Create a detailed outline for a {academic_level} level {essay_type} essay.\n"
        f"Topic: {topic}\n"
        f"Target word count: approximately {word_count} words\n\n"
        "Include:\n"
        "1. Three thesis statement options (numbered)\n"
        "2. Introduction outline (hook, background, thesis)\n"
        "3. Body paragraphs (each with topic sentence and 2-3 supporting points)\n"
        "4. Conclusion outline (restate thesis, summary, closing thought)\n\n"
        "Format the outline clearly with headers and bullet points."
    )
    output, error = _call_ai(prompt, max_tokens=1500)
    if error:
        return "", error
    return output or "", None


def generate_thesis_options(topic: str, essay_type: str, academic_level: str) -> Tuple[str, Optional[str]]:
    """Generate three thesis statement options for the given topic."""
    if not topic.strip():
        return "", "❌ Please enter an essay topic."
    prompt = (
        f"Generate 3 strong thesis statements for a {academic_level} level "
        f"{essay_type} essay on the topic: {topic}\n\n"
        "Number each thesis statement (1, 2, 3) and make each one distinct in approach."
    )
    output, error = _call_ai(prompt)
    if error:
        return "", error
    return output or "", None


def write_paragraph(
    outline_point: str,
    essay_type: str,
    academic_level: str,
    context: str = "",
) -> Tuple[str, Optional[str]]:
    """Write a draft paragraph based on an outline point."""
    if not outline_point.strip():
        return "", "❌ Please provide an outline point."
    context_hint = f"\n\nContext from outline:\n{context[:500]}" if context else ""
    prompt = (
        f"Write a well-developed paragraph for a {academic_level} level {essay_type} essay.\n"
        f"Outline point / section: {outline_point}{context_hint}\n\n"
        "Write a complete paragraph with a clear topic sentence, supporting evidence, "
        "analysis, and a concluding sentence."
    )
    output, error = _call_ai(prompt, max_tokens=600)
    if error:
        return "", error
    return output or "", None


def improve_paragraph(
    paragraph: str,
    essay_type: str,
    academic_level: str,
) -> Tuple[str, Optional[str]]:
    """Improve an existing paragraph."""
    if not paragraph.strip():
        return "", "❌ No paragraph provided."
    prompt = (
        f"Improve the following paragraph from a {academic_level} level {essay_type} essay. "
        "Enhance clarity, flow, vocabulary, and argument strength. "
        "Return only the improved paragraph.\n\n"
        f"Original:\n{paragraph[:1500]}"
    )
    output, error = _call_ai(prompt, max_tokens=600)
    if error:
        return "", error
    return output or "", None


def analyze_writing(full_essay: str) -> Tuple[str, Optional[str]]:
    """Provide detailed feedback on the essay."""
    if not full_essay.strip():
        return "", "❌ No essay text provided."
    prompt = (
        "Analyze the following essay and provide detailed feedback on:\n"
        "1. Clarity and coherence\n"
        "2. Argument strength\n"
        "3. Grammar and mechanics\n"
        "4. Flow and transitions\n"
        "5. Vocabulary level\n"
        "6. Overall effectiveness\n\n"
        "Be specific with examples from the text.\n\n"
        f"Essay:\n{full_essay[:4000]}"
    )
    output, error = _call_ai(prompt, max_tokens=1000)
    if error:
        return "", error
    return output or "", None


def check_arguments(full_essay: str) -> Tuple[str, Optional[str]]:
    """Identify logical fallacies or weak arguments in the essay."""
    if not full_essay.strip():
        return "", "❌ No essay text provided."
    prompt = (
        "Analyze the following essay for logical fallacies, weak arguments, "
        "unsupported claims, or gaps in reasoning. "
        "Identify specific issues and suggest improvements.\n\n"
        f"Essay:\n{full_essay[:4000]}"
    )
    output, error = _call_ai(prompt, max_tokens=800)
    if error:
        return "", error
    return output or "", None


def word_count_stats(text: str) -> Dict:
    """Return word count, sentence count, and estimated reading level."""
    import re
    words = len(text.split()) if text.strip() else 0
    sentences = len(re.split(r'[.!?]+', text)) - 1 if text.strip() else 0
    chars = len(text)
    avg_words_per_sentence = round(words / max(sentences, 1), 1)
    # Simple Flesch-Kincaid approximation
    if words > 0 and sentences > 0:
        syllables = sum(
            max(1, len(re.findall(r'[aeiouAEIOU]', w)))
            for w in text.split()
        )
        fk_grade = (0.39 * (words / sentences)) + (11.8 * (syllables / words)) - 15.59
        reading_level = f"Grade {max(1, round(fk_grade))}"
    else:
        reading_level = "N/A"
    return {
        "words": words,
        "sentences": sentences,
        "characters": chars,
        "avg_words_per_sentence": avg_words_per_sentence,
        "reading_level": reading_level,
    }


def save_essay(title: str, data: Dict) -> str:
    """Save an essay to user_data/essays/ as JSON."""
    _ensure_dirs()
    if not title.strip():
        title = f"Essay_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
    essay_id = str(uuid.uuid4())[:8]
    entry = {
        "id": essay_id,
        "title": safe_title,
        "saved_at": datetime.now().isoformat(),
        **data,
    }
    file_path = os.path.join(_ESSAYS_DIR, f"{essay_id}_{safe_title}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        return f"✅ Essay '{safe_title}' saved (id: {essay_id})."
    except Exception as exc:
        return f"❌ Failed to save essay: {exc}"


def list_essays() -> List[Dict]:
    """Return a list of saved essays sorted by date (newest first)."""
    _ensure_dirs()
    results = []
    try:
        for fname in os.listdir(_ESSAYS_DIR):
            if fname.endswith(".json"):
                fpath = os.path.join(_ESSAYS_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append(data)
                except Exception:
                    pass
    except Exception:
        pass
    results.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return results


def load_essay(essay_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Load an essay by ID or title fragment."""
    _ensure_dirs()
    for fname in os.listdir(_ESSAYS_DIR):
        if fname.endswith(".json") and essay_id in fname:
            fpath = os.path.join(_ESSAYS_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f), None
            except Exception as exc:
                return None, f"❌ Failed to load essay: {exc}"
    return None, f"❌ Essay '{essay_id}' not found."


def export_essay_markdown(essay_data: Dict) -> str:
    """Export essay as Markdown text."""
    lines = [f"# {essay_data.get('title', 'Essay')}\n"]
    if essay_data.get("topic"):
        lines.append(f"**Topic:** {essay_data['topic']}\n")
    if essay_data.get("essay_type"):
        lines.append(f"**Type:** {essay_data['essay_type']}\n")
    lines.append("")
    if essay_data.get("full_essay"):
        lines.append(essay_data["full_essay"])
    elif essay_data.get("paragraphs"):
        for section, text in essay_data["paragraphs"].items():
            lines.append(f"## {section}\n")
            lines.append(text)
            lines.append("")
    return "\n".join(lines)

"""Reading List / Literature Review backend for Gizmo."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

_LISTS_DIR = os.path.join("user_data", "reading_lists")

STATUS_OPTIONS = ["to read", "in progress", "read"]
DIFFICULTY_OPTIONS = ["beginner", "intermediate", "advanced"]


def _ensure_dirs() -> None:
    os.makedirs(_LISTS_DIR, exist_ok=True)


def _call_ai(prompt: str, max_tokens: int = 2048):
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


def generate_reading_list(topic: str, count: int = 10) -> Tuple[str, List[Dict]]:
    """Use AI to generate a curated reading list for a topic."""
    if not topic or not topic.strip():
        return "❌ Please provide a topic.", []

    prompt = (
        f"Generate a curated reading list of {count} resources about '{topic}'. "
        "Include books, articles, papers, or online resources. "
        "For each entry, provide:\n"
        "- Title\n"
        "- Author (or 'Unknown' if N/A)\n"
        "- Brief description (1-2 sentences)\n"
        "- Difficulty: beginner / intermediate / advanced\n"
        "- Estimated reading time (e.g., '2 hours', '30 minutes')\n\n"
        "Return a JSON array with objects having keys: "
        "title, author, description, difficulty, reading_time.\n"
        "Return ONLY the JSON array, no extra text."
    )
    output, error = _call_ai(prompt)
    if error:
        return error, []

    # Try to parse JSON
    try:
        json_match = re.search(r'\[.*\]', output, re.DOTALL)
        if json_match:
            items = json.loads(json_match.group(0))
            result = []
            for item in items:
                result.append({
                    "title": str(item.get("title", "")),
                    "author": str(item.get("author", "Unknown")),
                    "description": str(item.get("description", "")),
                    "difficulty": str(item.get("difficulty", "intermediate")),
                    "reading_time": str(item.get("reading_time", "")),
                    "status": "to read",
                })
            return f"✅ Generated reading list with {len(result)} item(s).", result
    except Exception:
        pass

    # Fallback: return as plain text entry
    return "✅ Reading list generated (plain text).", [{
        "title": f"Reading List: {topic}",
        "author": "AI-generated",
        "description": output,
        "difficulty": "intermediate",
        "reading_time": "",
        "status": "to read",
    }]


def generate_literature_review(reading_list: List[Dict]) -> Tuple[str, str]:
    """Generate a literature review summary from a reading list."""
    if not reading_list:
        return "❌ Reading list is empty.", ""

    items_text = "\n".join(
        f"- {item.get('title', '?')} by {item.get('author', 'Unknown')}: "
        f"{item.get('description', '')}"
        for item in reading_list[:20]
    )
    prompt = (
        "Based on the following reading list, write a comprehensive literature review. "
        "Synthesize the key themes, discuss the progression from introductory to advanced material, "
        "and highlight any notable gaps or connections between the works.\n\n"
        f"READING LIST:\n{items_text}\n\n"
        "Write a 3-5 paragraph literature review."
    )
    output, error = _call_ai(prompt, max_tokens=1500)
    if error:
        return error, ""
    return "✅ Literature review generated.", output


def save_reading_list(name: str, items: List[Dict]) -> str:
    """Save a reading list to user_data/reading_lists/{name}.json."""
    _ensure_dirs()
    if not name:
        return "❌ Please provide a list name."
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    if not safe_name:
        return "❌ Invalid name."
    file_path = os.path.join(_LISTS_DIR, f"{safe_name}.json")
    try:
        data = {
            "name": name,
            "items": items,
            "updated_at": datetime.now().isoformat(),
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return f"✅ Reading list '{safe_name}' saved ({len(items)} items)."
    except Exception as exc:
        return f"❌ Failed to save: {exc}"


def load_reading_list(name: str) -> Tuple[str, List[Dict]]:
    """Load a saved reading list."""
    _ensure_dirs()
    file_path = os.path.join(_LISTS_DIR, f"{name}.json")
    if not os.path.isfile(file_path):
        return f"❌ List '{name}' not found.", []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return f"✅ Loaded '{name}' ({len(data.get('items', []))} items).", data.get("items", [])
    except Exception as exc:
        return f"❌ Failed to load: {exc}", []


def list_reading_lists() -> List[str]:
    """Return names of all saved reading lists."""
    _ensure_dirs()
    try:
        files = [f for f in os.listdir(_LISTS_DIR) if f.endswith(".json")]
        return [os.path.splitext(f)[0] for f in sorted(files)]
    except Exception:
        return []


def render_reading_list_html(items: List[Dict], filter_difficulty: str = "All", filter_status: str = "All") -> str:
    """Render reading list as HTML table."""
    import html as html_lib

    if not items:
        return "<div style='color:#888;padding:16px'>No items. Generate or load a reading list.</div>"

    filtered = items
    if filter_difficulty != "All":
        filtered = [i for i in filtered if i.get("difficulty", "") == filter_difficulty]
    if filter_status != "All":
        filtered = [i for i in filtered if i.get("status", "") == filter_status]

    status_colors = {
        "to read": "#fef3c7",
        "in progress": "#dbeafe",
        "read": "#d1fae5",
    }
    difficulty_colors = {
        "beginner": "#d1fae5",
        "intermediate": "#fef3c7",
        "advanced": "#fee2e2",
    }

    rows = ""
    for i, item in enumerate(filtered):
        sc = status_colors.get(item.get("status", "to read"), "#fff")
        dc = difficulty_colors.get(item.get("difficulty", "intermediate"), "#fff")
        rows += (
            f"<tr style='border-bottom:1px solid #eee'>"
            f"<td style='padding:8px;font-weight:bold'>{html_lib.escape(item.get('title',''))}</td>"
            f"<td style='padding:8px'>{html_lib.escape(item.get('author',''))}</td>"
            f"<td style='padding:8px;font-size:0.85em'>{html_lib.escape(item.get('description',''))}</td>"
            f"<td style='padding:8px'><span style='background:{dc};padding:2px 8px;border-radius:12px;font-size:0.8em'>"
            f"{html_lib.escape(item.get('difficulty',''))}</span></td>"
            f"<td style='padding:8px'>{html_lib.escape(item.get('reading_time',''))}</td>"
            f"<td style='padding:8px'><span style='background:{sc};padding:2px 8px;border-radius:12px;font-size:0.8em'>"
            f"{html_lib.escape(item.get('status','to read'))}</span></td>"
            f"</tr>"
        )

    return f"""
<div style="font-family:'Segoe UI',Arial,sans-serif;overflow-x:auto">
  <table style="width:100%;border-collapse:collapse">
    <thead>
      <tr style="background:#f3f4f6;font-size:0.85em">
        <th style="text-align:left;padding:8px">Title</th>
        <th style="text-align:left;padding:8px">Author</th>
        <th style="text-align:left;padding:8px">Description</th>
        <th style="text-align:left;padding:8px">Difficulty</th>
        <th style="text-align:left;padding:8px">Reading Time</th>
        <th style="text-align:left;padding:8px">Status</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <div style="margin-top:8px;color:#888;font-size:0.8em">{len(filtered)} of {len(items)} items shown</div>
</div>"""

"""AI Note-Taker / Cornell Notes Generator backend for Gizmo."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

_NOTES_DIR = os.path.join("user_data", "notes")


def _ensure_dirs() -> None:
    """Create user_data/notes/ directory if it doesn't exist."""
    os.makedirs(_NOTES_DIR, exist_ok=True)


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


def extract_text_from_file(file_path: str) -> Tuple[str, str]:
    """Extract text from a .txt, .md, or .pdf file. Returns (status, text)."""
    if not file_path or not os.path.isfile(file_path):
        return "❌ File not found.", ""

    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".txt", ".md"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            return f"✅ Extracted text from {os.path.basename(file_path)}.", text
        except Exception as exc:
            return f"❌ Failed to read file: {exc}", ""

    if ext == ".pdf":
        try:
            from modules.pdf_reader import get_all_text
            return get_all_text(file_path)
        except Exception as exc:
            return f"❌ Failed to read PDF: {exc}", ""

    return f"❌ Unsupported file type: {ext}", ""


def _build_cornell_prompt(text: str, detail_level: str = "Standard") -> str:
    detail_instructions = {
        "Brief": "Keep notes concise — 1-2 bullet points per cue, 2-3 sentence summary.",
        "Standard": "Provide balanced notes — 2-4 bullet points per cue, 4-5 sentence summary.",
        "Detailed": "Be thorough — 4-6 bullet points per cue with examples, 5-7 sentence summary.",
    }
    detail_hint = detail_instructions.get(detail_level, detail_instructions["Standard"])

    return (
        f"You are an expert study assistant. Convert the following lecture/study content into Cornell Notes format.\n\n"
        f"Detail level: {detail_level}. {detail_hint}\n\n"
        "Return your response in EXACTLY this format (preserve these exact headers):\n\n"
        "=== CUE COLUMN ===\n"
        "List key questions, terms, and prompts — one per line, prefixed with '- '\n\n"
        "=== NOTES COLUMN ===\n"
        "For each cue, provide detailed notes, explanations, and examples.\n"
        "Format as: CUE: <cue item>\nNOTES: <detailed explanation>\n\n"
        "=== SUMMARY ===\n"
        "Write a concise paragraph summarizing the entire content.\n\n"
        f"CONTENT TO CONVERT:\n{text[:6000]}"
    )


def _parse_cornell_sections(ai_output: str) -> Dict[str, str]:
    """Parse AI output into cue, notes, and summary sections."""
    sections: Dict[str, str] = {"cue": "", "notes": "", "summary": ""}

    # Try to find the three sections
    cue_match = re.search(r"=== CUE COLUMN ===\s*(.*?)(?:=== NOTES COLUMN ===|$)", ai_output, re.DOTALL)
    notes_match = re.search(r"=== NOTES COLUMN ===\s*(.*?)(?:=== SUMMARY ===|$)", ai_output, re.DOTALL)
    summary_match = re.search(r"=== SUMMARY ===\s*(.*?)$", ai_output, re.DOTALL)

    if cue_match:
        sections["cue"] = cue_match.group(1).strip()
    if notes_match:
        sections["notes"] = notes_match.group(1).strip()
    if summary_match:
        sections["summary"] = summary_match.group(1).strip()

    # Fallback: if parsing failed, put everything in notes
    if not any(sections.values()):
        sections["notes"] = ai_output

    return sections


def generate_cornell_notes(
    text: str,
    detail_level: str = "Standard",
    subject_tag: str = "",
    language: str = "English",
) -> Tuple[str, Dict]:
    """Generate Cornell Notes from text using AI."""
    if not text or not text.strip():
        return "❌ Please provide some content to convert to notes.", {}

    lang_hint = f" Respond in {language}." if language and language != "English" else ""
    prompt = _build_cornell_prompt(text, detail_level) + lang_hint

    output, error = _call_ai(prompt, max_tokens=2048)
    if error:
        return error, {}

    sections = _parse_cornell_sections(output)
    result = {
        "cue": sections["cue"],
        "notes": sections["notes"],
        "summary": sections["summary"],
        "raw_input": text,
        "detail_level": detail_level,
        "subject_tag": subject_tag,
        "language": language,
        "generated_at": datetime.now().isoformat(),
    }
    return "✅ Cornell Notes generated.", result


def extract_key_terms(text: str) -> Tuple[str, str]:
    """Use AI to identify and define key terms from the text."""
    if not text or not text.strip():
        return "❌ No content provided.", ""

    prompt = (
        "Identify and define the most important terms and concepts from the following text. "
        "Format your response as a numbered list:\n"
        "1. **Term**: Definition\n"
        "2. **Term**: Definition\n"
        "(and so on)\n\n"
        f"TEXT:\n{text[:4000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Key terms extracted.", output


def generate_review_questions(text: str) -> Tuple[str, str]:
    """Use AI to generate study/review questions from the text."""
    if not text or not text.strip():
        return "❌ No content provided.", ""

    prompt = (
        "Generate 8-12 review/study questions based on the following content. "
        "Include a mix of recall, comprehension, and application questions. "
        "Format as a numbered list.\n\n"
        f"CONTENT:\n{text[:4000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Review questions generated.", output


def summarize_notes(text: str) -> Tuple[str, str]:
    """Generate a standalone summary paragraph from the text."""
    if not text or not text.strip():
        return "❌ No content provided.", ""

    prompt = (
        "Write a clear, comprehensive summary of the following content in 3-5 paragraphs. "
        "Cover the main ideas, key concepts, and important conclusions.\n\n"
        f"CONTENT:\n{text[:5000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Summary generated.", output


def export_markdown(note_data: Dict) -> str:
    """Export Cornell Notes as Markdown string."""
    title = note_data.get("title", "Notes")
    date_str = note_data.get("date", note_data.get("generated_at", ""))[:10]
    subject = note_data.get("subject_tag", "")
    cue = note_data.get("cue", "")
    notes = note_data.get("notes", "")
    summary = note_data.get("summary", "")
    key_terms = note_data.get("key_terms", "")
    review_questions = note_data.get("review_questions", "")

    lines = [
        f"# {title}",
        f"**Date:** {date_str}",
    ]
    if subject:
        lines.append(f"**Subject:** {subject}")
    lines += [
        "",
        "---",
        "",
        "## 📝 Cornell Notes",
        "",
        "### Cue Column",
        cue,
        "",
        "### Notes Column",
        notes,
        "",
        "### Summary",
        summary,
    ]
    if key_terms:
        lines += ["", "---", "", "## 🔑 Key Terms", "", key_terms]
    if review_questions:
        lines += ["", "---", "", "## ❓ Review Questions", "", review_questions]

    return "\n".join(lines)


def export_html(note_data: Dict) -> str:
    """Export Cornell Notes as a self-contained styled HTML string."""
    import html as html_lib

    title = html_lib.escape(note_data.get("title", "Notes"))
    date_str = note_data.get("date", note_data.get("generated_at", ""))[:10]
    subject = html_lib.escape(note_data.get("subject_tag", ""))
    cue_raw = note_data.get("cue", "")
    notes_raw = note_data.get("notes", "")
    summary_raw = note_data.get("summary", "")
    key_terms_raw = note_data.get("key_terms", "")
    review_raw = note_data.get("review_questions", "")

    def nl2br(s: str) -> str:
        return html_lib.escape(s).replace("\n", "<br>")

    key_terms_section = ""
    if key_terms_raw:
        key_terms_section = f"""
        <div class="section">
            <h2>🔑 Key Terms</h2>
            <div class="content">{nl2br(key_terms_raw)}</div>
        </div>"""

    review_section = ""
    if review_raw:
        review_section = f"""
        <div class="section">
            <h2>❓ Review Questions</h2>
            <div class="content">{nl2br(review_raw)}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 24px; color: #222; }}
  h1 {{ border-bottom: 3px solid #3b82f6; padding-bottom: 8px; }}
  .meta {{ color: #666; font-size: 0.9em; margin-bottom: 16px; }}
  .cornell {{ display: grid; grid-template-columns: 1fr 2fr; gap: 0; border: 2px solid #333; border-radius: 6px; overflow: hidden; margin: 16px 0; }}
  .cue-col {{ background: #f0f4ff; padding: 16px; border-right: 2px solid #333; }}
  .notes-col {{ background: #fff; padding: 16px; }}
  .summary-box {{ background: #fffbeb; border: 2px solid #333; border-top: none; border-radius: 0 0 6px 6px; padding: 16px; }}
  .cornell h3, .summary-box h3 {{ margin-top: 0; color: #1e40af; }}
  .section {{ margin-top: 24px; padding: 16px; background: #f9f9f9; border-radius: 6px; border: 1px solid #ddd; }}
  .content {{ white-space: pre-wrap; line-height: 1.6; }}
  pre {{ white-space: pre-wrap; margin: 0; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">Date: {date_str}{' &nbsp;|&nbsp; Subject: ' + subject if subject else ''}</div>
<div class="cornell">
  <div class="cue-col">
    <h3>📌 Cue Column</h3>
    <div class="content">{nl2br(cue_raw)}</div>
  </div>
  <div class="notes-col">
    <h3>📝 Notes Column</h3>
    <div class="content">{nl2br(notes_raw)}</div>
  </div>
</div>
<div class="summary-box">
  <h3>📋 Summary</h3>
  <div class="content">{nl2br(summary_raw)}</div>
</div>
{key_terms_section}
{review_section}
</body>
</html>"""


def export_json_note(note_data: Dict) -> str:
    """Export note data as a JSON string."""
    return json.dumps(note_data, indent=2, ensure_ascii=False)


def save_note(title: str, note_data: Dict) -> str:
    """Save a note to user_data/notes/{safe_title}.json."""
    _ensure_dirs()
    if not title:
        return "❌ Please provide a note title."

    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
    if not safe_title:
        return "❌ Invalid note title."

    note_data = dict(note_data)
    note_data["title"] = title
    note_data["date"] = note_data.get("date", datetime.now().strftime("%Y-%m-%d"))

    file_path = os.path.join(_NOTES_DIR, f"{safe_title}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(note_data, f, indent=2, ensure_ascii=False)
        return f"✅ Note '{safe_title}' saved."
    except Exception as exc:
        return f"❌ Failed to save note: {exc}"


def load_note(title: str) -> Tuple[str, Dict]:
    """Load a note from user_data/notes/{title}.json."""
    _ensure_dirs()
    file_path = os.path.join(_NOTES_DIR, f"{title}.json")
    if not os.path.isfile(file_path):
        return f"❌ Note '{title}' not found.", {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return f"✅ Loaded note '{title}'.", data
    except Exception as exc:
        return f"❌ Failed to load note: {exc}", {}


def list_notes() -> List[str]:
    """Return a list of saved note names."""
    _ensure_dirs()
    try:
        files = [f for f in os.listdir(_NOTES_DIR) if f.endswith(".json")]
        return [os.path.splitext(f)[0] for f in sorted(files)]
    except Exception:
        return []


def render_cornell_html(note_data: Dict) -> str:
    """Render Cornell Notes as an HTML string for display in gr.HTML."""
    import html as html_lib

    cue_raw = note_data.get("cue", "")
    notes_raw = note_data.get("notes", "")
    summary_raw = note_data.get("summary", "")

    def nl2br(s: str) -> str:
        return html_lib.escape(s).replace("\n", "<br>")

    if not any([cue_raw, notes_raw, summary_raw]):
        return "<div style='color:#888;padding:16px'>No notes generated yet. Paste content and click Generate.</div>"

    return f"""
<div style="font-family:'Segoe UI',Arial,sans-serif;max-width:100%;padding:8px">
  <div style="display:grid;grid-template-columns:1fr 2fr;gap:0;border:2px solid #555;border-radius:6px 6px 0 0;overflow:hidden">
    <div style="background:#e8eeff;padding:16px;border-right:2px solid #555">
      <h3 style="margin-top:0;color:#1e40af;font-size:1em">📌 Cue Column</h3>
      <div style="white-space:pre-wrap;line-height:1.6;font-size:0.9em">{nl2br(cue_raw)}</div>
    </div>
    <div style="background:#fff;padding:16px">
      <h3 style="margin-top:0;color:#1e40af;font-size:1em">📝 Notes Column</h3>
      <div style="white-space:pre-wrap;line-height:1.6;font-size:0.9em">{nl2br(notes_raw)}</div>
    </div>
  </div>
  <div style="background:#fffbeb;border:2px solid #555;border-top:none;border-radius:0 0 6px 6px;padding:16px">
    <h3 style="margin-top:0;color:#92400e;font-size:1em">📋 Summary</h3>
    <div style="white-space:pre-wrap;line-height:1.6;font-size:0.9em">{nl2br(summary_raw)}</div>
  </div>
</div>"""

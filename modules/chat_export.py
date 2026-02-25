"""
chat_export.py — Backend logic for exporting chat histories.

Supported formats:
  - Markdown (.md)
  - PDF (.pdf)  — requires fpdf2; degrades gracefully if not installed
  - HTML (.html)
  - Plain text (.txt)
  - JSON (.json)
"""

import html as html_module
import json
from datetime import datetime
from pathlib import Path


def export_as_markdown(
    history: dict,
    name1: str,
    name2: str,
    include_timestamps: bool = True,
    include_metadata: bool = False,
) -> str:
    """Export chat history as a Markdown string."""
    lines = [f"# Chat Export\n"]
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"**Participants:** {name1}, {name2}\n\n---\n")

    for i, (user_msg, assistant_msg) in enumerate(history.get("internal", [])):
        if user_msg and user_msg != "<|BEGIN-VISIBLE-CHAT|>":
            timestamp = ""
            if include_timestamps:
                meta = history.get("metadata", {}).get(f"user_{i}", {})
                ts = meta.get("timestamp", "")
                if ts:
                    timestamp = f" *({ts})*"
            lines.append(f"### 👤 {name1}{timestamp}\n\n{user_msg}\n")

        if assistant_msg:
            timestamp = ""
            if include_timestamps:
                meta = history.get("metadata", {}).get(f"assistant_{i}", {})
                ts = meta.get("timestamp", "")
                if ts:
                    timestamp = f" *({ts})*"
            lines.append(f"### 🤖 {name2}{timestamp}\n\n{assistant_msg}\n")

    return "\n".join(lines)


def export_as_text(history: dict, name1: str, name2: str) -> str:
    """Export chat history as plain text."""
    lines = [
        f"Chat Export — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Participants: {name1}, {name2}",
        "=" * 60,
        "",
    ]
    for i, (user_msg, assistant_msg) in enumerate(history.get("internal", [])):
        if user_msg and user_msg != "<|BEGIN-VISIBLE-CHAT|>":
            lines.append(f"[{name1}]\n{user_msg}\n")
        if assistant_msg:
            lines.append(f"[{name2}]\n{assistant_msg}\n")
    return "\n".join(lines)


def export_as_html(history: dict, name1: str, name2: str) -> str:
    """Export chat history as a self-contained HTML file."""
    rows = []
    for i, (user_msg, assistant_msg) in enumerate(history.get("internal", [])):
        if user_msg and user_msg != "<|BEGIN-VISIBLE-CHAT|>":
            rows.append(
                f'<div class="msg user"><strong>{html_module.escape(name1)}</strong>'
                f'<p>{html_module.escape(user_msg)}</p></div>'
            )
        if assistant_msg:
            rows.append(
                f'<div class="msg assistant"><strong>{html_module.escape(name2)}</strong>'
                f'<p>{html_module.escape(assistant_msg)}</p></div>'
            )

    body = "\n".join(rows)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Chat Export</title>
<style>
body{{font-family:sans-serif;max-width:800px;margin:auto;padding:1rem;}}
.msg{{margin:1rem 0;padding:0.75rem 1rem;border-radius:8px;}}
.user{{background:#e8f0fe;}}
.assistant{{background:#f1f3f4;}}
strong{{display:block;margin-bottom:0.25rem;}}
</style>
</head>
<body>
<h1>Chat Export</h1>
<p><strong>Date:</strong> {date_str}</p>
<p><strong>Participants:</strong> {html_module.escape(name1)}, {html_module.escape(name2)}</p>
<hr>
{body}
</body>
</html>"""


def export_as_json(history: dict, name1: str, name2: str) -> str:
    """Export chat history as clean JSON."""
    messages = []
    for i, (user_msg, assistant_msg) in enumerate(history.get("internal", [])):
        if user_msg and user_msg != "<|BEGIN-VISIBLE-CHAT|>":
            messages.append({"role": "user", "name": name1, "content": user_msg})
        if assistant_msg:
            messages.append({"role": "assistant", "name": name2, "content": assistant_msg})
    payload = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "participants": [name1, name2],
        "messages": messages,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def export_as_pdf(history: dict, name1: str, name2: str, output_path: str) -> str:
    """
    Export chat as a PDF file. Returns the file path on success.
    Raises ImportError with installation instructions if fpdf2 is not installed.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError(
            "PDF export requires fpdf2. Install it with: pip install fpdf2"
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Chat Export", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Participants: {name1}, {name2}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    for i, (user_msg, assistant_msg) in enumerate(history.get("internal", [])):
        if user_msg and user_msg != "<|BEGIN-VISIBLE-CHAT|>":
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, f"{name1}:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(0, 6, user_msg)
            pdf.ln(2)
        if assistant_msg:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, f"{name2}:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(0, 6, assistant_msg)
            pdf.ln(2)

    pdf.output(output_path)
    return output_path


def save_export(content: str, filename: str, directory: str = "user_data/exports") -> str:
    """Save exported content to a file and return the full path."""
    export_dir = Path(directory)
    export_dir.mkdir(parents=True, exist_ok=True)
    # Sanitise filename
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)
    path = export_dir / safe_name
    path.write_text(content, encoding="utf-8")
    return str(path)


def _auto_filename(extension: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"chat_export_{timestamp}.{extension}"

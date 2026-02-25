"""
ui_chat_export.py — Gradio UI components for exporting chat conversations.

Provides:
  create_ui()              — renders the export panel inside the chat tab
  create_event_handlers()  — wires export buttons to backend functions
"""

import gradio as gr

from modules import shared
from modules.chat_export import (
    _auto_filename,
    export_as_html,
    export_as_json,
    export_as_markdown,
    export_as_text,
    save_export,
)
from modules.utils import gradio as _gradio


def create_ui():
    """Render the export controls accordion inside the chat tab."""
    with gr.Accordion("📥 Export Chat", open=False, elem_id="chat-export-accordion"):
        with gr.Row():
            shared.gradio["export_format_choice"] = gr.Radio(
                choices=["Markdown", "HTML", "Plain Text", "JSON"],
                value="Markdown",
                label="Format",
                elem_id="export-format-choice",
            )

        with gr.Row():
            shared.gradio["export_include_timestamps"] = gr.Checkbox(
                value=True, label="Include timestamps", elem_id="export-include-ts"
            )
            shared.gradio["export_include_metadata"] = gr.Checkbox(
                value=False, label="Include metadata", elem_id="export-include-meta"
            )

        shared.gradio["export_chat_btn"] = gr.Button(
            "📥 Export Chat", elem_id="export-chat-btn", variant="primary"
        )

        shared.gradio["export_file_output"] = gr.File(
            label="Download exported file",
            interactive=False,
            elem_id="export-file-output",
        )
        shared.gradio["export_status"] = gr.Textbox(
            label="Export status",
            interactive=False,
            elem_id="export-status",
        )

        # PDF export note
        gr.Markdown(
            "_For PDF export, install [fpdf2](https://pypi.org/project/fpdf2/) "
            "(`pip install fpdf2`) and select **PDF** in the format dropdown above. "
            "PDF export is available via the Python API; the web UI currently supports "
            "Markdown, HTML, Plain Text, and JSON._"
        )


def create_event_handlers():
    """Wire the export button to the backend export logic."""

    def _do_export(history, name1, name2, fmt, include_ts, include_meta):
        if not history or not history.get("internal"):
            return None, "⚠️ No chat history to export."
        try:
            if fmt == "Markdown":
                content = export_as_markdown(history, name1, name2, include_ts, include_meta)
                ext = "md"
            elif fmt == "HTML":
                content = export_as_html(history, name1, name2)
                ext = "html"
            elif fmt == "JSON":
                content = export_as_json(history, name1, name2)
                ext = "json"
            else:
                content = export_as_text(history, name1, name2)
                ext = "txt"

            filename = _auto_filename(ext)
            path = save_export(content, filename)
            return path, f"✅ Exported as {filename}"
        except Exception as exc:
            return None, f"❌ Export failed: {exc}"

    shared.gradio["export_chat_btn"].click(
        _do_export,
        [
            shared.gradio["history"],
            shared.gradio["name1"],
            shared.gradio["name2"],
            shared.gradio["export_format_choice"],
            shared.gradio["export_include_timestamps"],
            shared.gradio["export_include_metadata"],
        ],
        [
            shared.gradio["export_file_output"],
            shared.gradio["export_status"],
        ],
    )

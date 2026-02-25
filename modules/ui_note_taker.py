"""Gradio UI tab for the AI Note-Taker / Cornell Notes Generator."""

from __future__ import annotations

import os
import tempfile

import gradio as gr

from modules import shared
from modules.note_taker import (
    export_html,
    export_json_note,
    export_markdown,
    extract_key_terms,
    extract_text_from_file,
    generate_cornell_notes,
    generate_review_questions,
    list_notes,
    load_note,
    render_cornell_html,
    save_note,
    summarize_notes,
)

_current_note: dict = {}


def _generate_notes_fn(text, file_obj, detail_level, subject_tag, language):
    global _current_note

    # If file uploaded, extract text from it
    if file_obj is not None:
        file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
        status, extracted = extract_text_from_file(file_path)
        if extracted:
            text = extracted
        else:
            return status, render_cornell_html({}), gr.update(choices=list_notes())

    if not text or not text.strip():
        return "❌ Please paste content or upload a file.", render_cornell_html({}), gr.update(choices=list_notes())

    status, note_data = generate_cornell_notes(text, detail_level, subject_tag, language)
    if note_data:
        _current_note = note_data

    html = render_cornell_html(_current_note)
    notes_list = list_notes()
    return status, html, gr.update(choices=notes_list)


def _key_terms_fn(text):
    combined = _current_note.get("notes", "") or text
    if not combined:
        return "❌ Generate notes first or provide text."
    status, result = extract_key_terms(combined)
    if result:
        _current_note["key_terms"] = result
    return result or status


def _review_questions_fn(text):
    combined = _current_note.get("notes", "") or text
    if not combined:
        return "❌ Generate notes first or provide text."
    status, result = generate_review_questions(combined)
    if result:
        _current_note["review_questions"] = result
    return result or status


def _summarize_fn(text):
    combined = _current_note.get("raw_input", "") or text
    if not combined:
        return "❌ Generate notes first or provide text."
    status, result = summarize_notes(combined)
    return result or status


def _export_fn(fmt):
    if not _current_note:
        return "❌ No notes to export. Generate notes first.", gr.update(visible=False)

    if fmt == "Markdown":
        content = export_markdown(_current_note)
        suffix = ".md"
    elif fmt == "HTML":
        content = export_html(_current_note)
        suffix = ".html"
    else:  # JSON
        content = export_json_note(_current_note)
        suffix = ".json"

    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        return f"✅ Ready to download.", gr.update(value=tmp.name, visible=True)
    except Exception as exc:
        return f"❌ Export failed: {exc}", gr.update(visible=False)


def _send_to_google_docs_fn():
    if not _current_note:
        return "❌ No notes to send."
    try:
        from modules.google_docs import create_document
        md_content = export_markdown(_current_note)
        title = _current_note.get("title", "Cornell Notes")
        result = create_document(title, md_content)
        return result if isinstance(result, str) else "✅ Sent to Google Docs."
    except Exception as exc:
        return f"❌ Google Docs error: {exc}"


def _send_to_notion_fn():
    if not _current_note:
        return "❌ No notes to send."
    try:
        from modules.notion_integration import create_page
        md_content = export_markdown(_current_note)
        title = _current_note.get("title", "Cornell Notes")
        result = create_page(title, md_content)
        return result if isinstance(result, str) else "✅ Sent to Notion."
    except Exception as exc:
        return f"❌ Notion error: {exc}"


def _save_note_fn(title):
    if not title:
        return "❌ Please enter a note title."
    if not _current_note:
        return "❌ No notes generated yet."
    return save_note(title, _current_note)


def _load_note_fn(note_name):
    global _current_note
    if not note_name:
        return "No note selected.", render_cornell_html({})
    status, note_data = load_note(note_name)
    if note_data:
        _current_note = note_data
    return status, render_cornell_html(_current_note)


def _refresh_notes_fn():
    return gr.update(choices=list_notes())


def create_ui():
    with gr.Tab("📚 AI Note-Taker", elem_id="note-taker-tab"):
        with gr.Accordion("📥 Input", open=True):
            shared.gradio['nt_text_input'] = gr.Textbox(
                label="Paste lecture content / text",
                lines=8,
                placeholder="Paste your lecture notes, textbook content, or any study material here...",
            )
            shared.gradio['nt_file_upload'] = gr.File(
                label="Or upload a file (.txt, .md, .pdf)",
                file_types=[".txt", ".md", ".pdf"],
            )
            with gr.Row():
                shared.gradio['nt_detail_level'] = gr.Dropdown(
                    label="Detail Level",
                    choices=["Brief", "Standard", "Detailed"],
                    value="Standard",
                )
                shared.gradio['nt_subject_tag'] = gr.Textbox(
                    label="Subject Tag (optional)",
                    placeholder="e.g. Biology, History",
                )
                shared.gradio['nt_language'] = gr.Dropdown(
                    label="Language",
                    choices=["English", "Spanish", "French", "German", "Portuguese", "Chinese", "Japanese"],
                    value="English",
                )
            shared.gradio['nt_generate_btn'] = gr.Button("📝 Generate Cornell Notes", variant="primary")
            shared.gradio['nt_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📖 Cornell Notes Display", open=True):
            shared.gradio['nt_cornell_display'] = gr.HTML(
                value=render_cornell_html({}),
                label="Cornell Notes",
            )

        with gr.Row():
            shared.gradio['nt_key_terms_btn'] = gr.Button("🔑 Key Terms")
            shared.gradio['nt_review_questions_btn'] = gr.Button("❓ Review Questions")
            shared.gradio['nt_summarize_btn'] = gr.Button("📋 Summarize")

        shared.gradio['nt_ai_output'] = gr.Textbox(
            label="AI Output",
            lines=8,
            interactive=False,
        )

        with gr.Accordion("📤 Export", open=False):
            with gr.Row():
                shared.gradio['nt_export_format'] = gr.Dropdown(
                    label="Format",
                    choices=["Markdown", "HTML", "JSON"],
                    value="Markdown",
                )
                shared.gradio['nt_export_btn'] = gr.Button("📥 Export")
            shared.gradio['nt_export_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['nt_export_file'] = gr.File(
                label="Download", interactive=False, visible=False
            )
            with gr.Row():
                shared.gradio['nt_gdocs_btn'] = gr.Button("📤 Send to Google Docs")
                shared.gradio['nt_notion_btn'] = gr.Button("📤 Send to Notion")
            shared.gradio['nt_integration_status'] = gr.Textbox(label="Integration Status", interactive=False)

        with gr.Accordion("💾 Saved Notes", open=False):
            with gr.Row():
                shared.gradio['nt_note_title'] = gr.Textbox(
                    label="Note Title",
                    placeholder="Enter a title to save...",
                )
                shared.gradio['nt_save_btn'] = gr.Button("💾 Save Note")
            shared.gradio['nt_save_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['nt_note_selector'] = gr.Dropdown(
                label="Load Saved Note",
                choices=list_notes(),
                interactive=True,
            )
            with gr.Row():
                shared.gradio['nt_load_btn'] = gr.Button("📂 Load Note")
                shared.gradio['nt_refresh_btn'] = gr.Button("🔄 Refresh")


def create_event_handlers():
    shared.gradio['nt_generate_btn'].click(
        _generate_notes_fn,
        inputs=[
            shared.gradio['nt_text_input'],
            shared.gradio['nt_file_upload'],
            shared.gradio['nt_detail_level'],
            shared.gradio['nt_subject_tag'],
            shared.gradio['nt_language'],
        ],
        outputs=[
            shared.gradio['nt_status'],
            shared.gradio['nt_cornell_display'],
            shared.gradio['nt_note_selector'],
        ],
        show_progress=True,
    )

    shared.gradio['nt_key_terms_btn'].click(
        _key_terms_fn,
        inputs=[shared.gradio['nt_text_input']],
        outputs=[shared.gradio['nt_ai_output']],
        show_progress=True,
    )

    shared.gradio['nt_review_questions_btn'].click(
        _review_questions_fn,
        inputs=[shared.gradio['nt_text_input']],
        outputs=[shared.gradio['nt_ai_output']],
        show_progress=True,
    )

    shared.gradio['nt_summarize_btn'].click(
        _summarize_fn,
        inputs=[shared.gradio['nt_text_input']],
        outputs=[shared.gradio['nt_ai_output']],
        show_progress=True,
    )

    shared.gradio['nt_export_btn'].click(
        _export_fn,
        inputs=[shared.gradio['nt_export_format']],
        outputs=[shared.gradio['nt_export_status'], shared.gradio['nt_export_file']],
        show_progress=True,
    )

    shared.gradio['nt_gdocs_btn'].click(
        _send_to_google_docs_fn,
        inputs=[],
        outputs=[shared.gradio['nt_integration_status']],
        show_progress=True,
    )

    shared.gradio['nt_notion_btn'].click(
        _send_to_notion_fn,
        inputs=[],
        outputs=[shared.gradio['nt_integration_status']],
        show_progress=True,
    )

    shared.gradio['nt_save_btn'].click(
        _save_note_fn,
        inputs=[shared.gradio['nt_note_title']],
        outputs=[shared.gradio['nt_save_status']],
        show_progress=True,
    )

    shared.gradio['nt_load_btn'].click(
        _load_note_fn,
        inputs=[shared.gradio['nt_note_selector']],
        outputs=[shared.gradio['nt_save_status'], shared.gradio['nt_cornell_display']],
        show_progress=True,
    )

    shared.gradio['nt_refresh_btn'].click(
        _refresh_notes_fn,
        inputs=[],
        outputs=[shared.gradio['nt_note_selector']],
        show_progress=False,
    )

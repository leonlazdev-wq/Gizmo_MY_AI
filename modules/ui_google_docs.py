"""Gradio UI tab for the Google Docs integration."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.google_docs import (
    connect_document,
    fix_grammar,
    get_current_state,
    get_document_content,
    get_document_metadata,
    insert_text,
    read_section,
    replace_text,
    summarize_document,
)

TUTORIAL_URL = "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#google-docs-integration"


def _connect(doc_url, creds_path):
    msg, info = connect_document(doc_url, creds_path)
    status_html = (
        f"<div style='color:#4CAF50;font-weight:600'>{msg}</div>"
        if "✅" in msg
        else f"<div style='color:#f44336'>{msg}</div>"
    )
    title = info.get("title", "") if isinstance(info, dict) else ""
    header = f"**{title}**" if title else ""
    return status_html, header


def _view_content():
    msg, content = get_document_content()
    return msg, content or ""


def _read_section(section_title):
    msg, content = read_section(section_title)
    return msg, content or ""


def _insert_text(text, position):
    return insert_text(text, position)


def _find_replace(old_text, new_text):
    return replace_text(old_text, new_text)


def _fix_grammar():
    return fix_grammar()


def _summarize():
    msg, summary = summarize_document()
    return msg, summary or ""


def _get_metadata():
    msg, meta = get_document_metadata()
    if not isinstance(meta, dict):
        return msg, ""
    lines = [f"**{k}:** {v}" for k, v in meta.items()]
    return msg, "\n\n".join(lines)


def create_ui():
    with gr.Tab("📝 Google Docs", elem_id="google-docs-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: How to set up Google Docs integration</a>"
            f"</div>"
        )

        with gr.Accordion("🔌 Connect to Document", open=True):
            with gr.Row():
                shared.gradio['gdocs_doc_url'] = gr.Textbox(
                    label="Document URL or ID",
                    placeholder="https://docs.google.com/document/d/... or just the ID",
                    scale=3,
                )
                shared.gradio['gdocs_creds_path'] = gr.Textbox(
                    label="Credentials JSON path",
                    placeholder="/path/to/service-account.json",
                    scale=2,
                )
            shared.gradio['gdocs_connect_btn'] = gr.Button("🔌 Connect", variant="primary")
            shared.gradio['gdocs_status_html'] = gr.HTML(
                value="<div style='color:#888'>Not connected</div>"
            )
            shared.gradio['gdocs_pres_header'] = gr.Markdown("")

        with gr.Accordion("📖 View Document", open=False):
            shared.gradio['gdocs_view_btn'] = gr.Button("📖 View Full Document")
            shared.gradio['gdocs_view_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['gdocs_view_content'] = gr.Textbox(
                label="Document Content", lines=10, interactive=False
            )

        with gr.Accordion("🔍 Read Section", open=False):
            shared.gradio['gdocs_section_title'] = gr.Textbox(
                label="Section Heading", placeholder="Section heading..."
            )
            shared.gradio['gdocs_read_section_btn'] = gr.Button("🔍 Read Section")
            shared.gradio['gdocs_section_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['gdocs_section_content'] = gr.Textbox(
                label="Section Content", lines=5, interactive=False
            )

        with gr.Accordion("✍️ Insert Text", open=False):
            shared.gradio['gdocs_insert_text'] = gr.Textbox(
                label="Text to insert", lines=3
            )
            shared.gradio['gdocs_insert_position'] = gr.Dropdown(
                label="Insert position",
                choices=["end", "beginning"],
                value="end",
            )
            shared.gradio['gdocs_insert_btn'] = gr.Button("✍️ Insert Text", variant="primary")
            shared.gradio['gdocs_insert_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("🔍 Find & Replace", open=False):
            with gr.Row():
                shared.gradio['gdocs_old_text'] = gr.Textbox(label="Find text")
                shared.gradio['gdocs_new_text'] = gr.Textbox(label="Replace with")
            shared.gradio['gdocs_replace_btn'] = gr.Button("🔄 Replace", variant="primary")
            shared.gradio['gdocs_replace_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📝 AI Actions", open=False):
            with gr.Row():
                shared.gradio['gdocs_fix_grammar_btn'] = gr.Button("📝 Fix Grammar")
                shared.gradio['gdocs_summarize_btn'] = gr.Button("📋 Summarize")
                shared.gradio['gdocs_metadata_btn'] = gr.Button("ℹ️ Document Info")
            shared.gradio['gdocs_ai_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['gdocs_ai_output'] = gr.Textbox(
                label="Output", lines=8, interactive=False
            )


def create_event_handlers():
    shared.gradio['gdocs_connect_btn'].click(
        _connect,
        inputs=[shared.gradio['gdocs_doc_url'], shared.gradio['gdocs_creds_path']],
        outputs=[shared.gradio['gdocs_status_html'], shared.gradio['gdocs_pres_header']],
        show_progress=False,
    )

    shared.gradio['gdocs_view_btn'].click(
        _view_content,
        inputs=[],
        outputs=[shared.gradio['gdocs_view_status'], shared.gradio['gdocs_view_content']],
        show_progress=True,
    )

    shared.gradio['gdocs_read_section_btn'].click(
        _read_section,
        inputs=[shared.gradio['gdocs_section_title']],
        outputs=[shared.gradio['gdocs_section_status'], shared.gradio['gdocs_section_content']],
        show_progress=True,
    )

    shared.gradio['gdocs_insert_btn'].click(
        _insert_text,
        inputs=[shared.gradio['gdocs_insert_text'], shared.gradio['gdocs_insert_position']],
        outputs=[shared.gradio['gdocs_insert_status']],
        show_progress=True,
    )

    shared.gradio['gdocs_replace_btn'].click(
        _find_replace,
        inputs=[shared.gradio['gdocs_old_text'], shared.gradio['gdocs_new_text']],
        outputs=[shared.gradio['gdocs_replace_status']],
        show_progress=True,
    )

    shared.gradio['gdocs_fix_grammar_btn'].click(
        _fix_grammar,
        inputs=[],
        outputs=[shared.gradio['gdocs_ai_status']],
        show_progress=True,
    )

    shared.gradio['gdocs_summarize_btn'].click(
        _summarize,
        inputs=[],
        outputs=[shared.gradio['gdocs_ai_status'], shared.gradio['gdocs_ai_output']],
        show_progress=True,
    )

    shared.gradio['gdocs_metadata_btn'].click(
        _get_metadata,
        inputs=[],
        outputs=[shared.gradio['gdocs_ai_status'], shared.gradio['gdocs_ai_output']],
        show_progress=True,
    )

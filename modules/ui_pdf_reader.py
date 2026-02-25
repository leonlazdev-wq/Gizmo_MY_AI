"""Gradio UI tab for the PDF Reader."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.pdf_reader import (
    answer_question,
    get_all_text,
    get_current_state,
    get_page_text,
    get_pdf_info,
    highlight_key_sections,
    load_pdf,
    search_pdf,
    summarize_page,
    summarize_pdf,
)

TUTORIAL_URL = "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#pdf-reader"


def _load_pdf(file_obj):
    if file_obj is None:
        return "No file selected.", "", gr.update(minimum=1, maximum=1, value=1)
    msg, info = load_pdf(file_obj.name)
    page_count = info.get("page_count", 1) if isinstance(info, dict) else 1
    title = info.get("title", "") if isinstance(info, dict) else ""
    lines = [f"**Pages:** {page_count}"]
    if title:
        lines.insert(0, f"**Title:** {title}")
    if isinstance(info, dict):
        for k, v in info.items():
            if k not in ("title", "page_count"):
                lines.append(f"**{k}:** {v}")
    info_md = "\n\n".join(lines)
    return msg, info_md, gr.update(minimum=1, maximum=page_count, value=1)


def _get_page(page_num):
    msg, text = get_page_text(int(page_num) - 1)
    return msg, text or ""


def _search(query):
    msg, results = search_pdf(query)
    if not results:
        return msg, ""
    if isinstance(results, list):
        lines = [f"Page {r.get('page', '?')}: {r.get('text', r)}" for r in results]
        return msg, "\n\n".join(lines)
    return msg, str(results)


def _summarize_full():
    msg, summary = summarize_pdf()
    return msg, summary or ""


def _summarize_current_page(page_num):
    msg, summary = summarize_page(int(page_num) - 1)
    return msg, summary or ""


def _ask_question(question):
    msg, answer = answer_question(question)
    return msg, answer or ""


def _key_sections():
    msg, sections = highlight_key_sections()
    return msg, sections or ""


def create_ui():
    with gr.Tab("📄 PDF Reader", elem_id="pdf-reader-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: How to use the PDF Reader</a>"
            f"</div>"
        )

        with gr.Row():
            with gr.Column(scale=1):
                shared.gradio['pdf_file_upload'] = gr.File(
                    label="Upload PDF", file_types=[".pdf"]
                )
                shared.gradio['pdf_load_btn'] = gr.Button("📂 Load PDF", variant="primary")
                shared.gradio['pdf_info_md'] = gr.Markdown("")

            with gr.Column(scale=2):
                with gr.Row():
                    shared.gradio['pdf_page_num'] = gr.Number(
                        label="Page", value=1, precision=0, minimum=1
                    )
                    shared.gradio['pdf_prev_btn'] = gr.Button("◀")
                    shared.gradio['pdf_next_btn'] = gr.Button("▶")
                shared.gradio['pdf_page_text'] = gr.Textbox(
                    label="Page Content", lines=15, interactive=False
                )

        with gr.Accordion("🔍 Search", open=False):
            shared.gradio['pdf_search_input'] = gr.Textbox(
                label="Search query", placeholder="Search for text..."
            )
            shared.gradio['pdf_search_btn'] = gr.Button("🔍 Search")
            shared.gradio['pdf_search_results'] = gr.Textbox(
                label="Results", lines=5, interactive=False
            )

        with gr.Accordion("🤖 AI Features", open=False):
            with gr.Row():
                shared.gradio['pdf_summarize_btn'] = gr.Button("📋 Summarize PDF")
                shared.gradio['pdf_summarize_page_btn'] = gr.Button("📋 Summarize Page")
                shared.gradio['pdf_key_sections_btn'] = gr.Button("🔑 Key Sections")
            shared.gradio['pdf_question_input'] = gr.Textbox(
                label="Ask a question",
                placeholder="Ask a question about the PDF...",
            )
            shared.gradio['pdf_ask_btn'] = gr.Button("❓ Ask Question", variant="primary")
            shared.gradio['pdf_ai_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['pdf_ai_output'] = gr.Textbox(
                label="Answer/Output", lines=8, interactive=False
            )


def create_event_handlers():
    shared.gradio['pdf_load_btn'].click(
        _load_pdf,
        inputs=[shared.gradio['pdf_file_upload']],
        outputs=[
            shared.gradio['pdf_ai_status'],
            shared.gradio['pdf_info_md'],
            shared.gradio['pdf_page_num'],
        ],
        show_progress=True,
    )

    shared.gradio['pdf_page_num'].change(
        _get_page,
        inputs=[shared.gradio['pdf_page_num']],
        outputs=[shared.gradio['pdf_ai_status'], shared.gradio['pdf_page_text']],
        show_progress=False,
    )

    shared.gradio['pdf_prev_btn'].click(
        lambda n: max(1, int(n) - 1),
        inputs=[shared.gradio['pdf_page_num']],
        outputs=[shared.gradio['pdf_page_num']],
        show_progress=False,
    )

    shared.gradio['pdf_next_btn'].click(
        lambda n: int(n) + 1,
        inputs=[shared.gradio['pdf_page_num']],
        outputs=[shared.gradio['pdf_page_num']],
        show_progress=False,
    )

    shared.gradio['pdf_search_btn'].click(
        _search,
        inputs=[shared.gradio['pdf_search_input']],
        outputs=[shared.gradio['pdf_ai_status'], shared.gradio['pdf_search_results']],
        show_progress=True,
    )

    shared.gradio['pdf_summarize_btn'].click(
        _summarize_full,
        inputs=[],
        outputs=[shared.gradio['pdf_ai_status'], shared.gradio['pdf_ai_output']],
        show_progress=True,
    )

    shared.gradio['pdf_summarize_page_btn'].click(
        _summarize_current_page,
        inputs=[shared.gradio['pdf_page_num']],
        outputs=[shared.gradio['pdf_ai_status'], shared.gradio['pdf_ai_output']],
        show_progress=True,
    )

    shared.gradio['pdf_key_sections_btn'].click(
        _key_sections,
        inputs=[],
        outputs=[shared.gradio['pdf_ai_status'], shared.gradio['pdf_ai_output']],
        show_progress=True,
    )

    shared.gradio['pdf_ask_btn'].click(
        _ask_question,
        inputs=[shared.gradio['pdf_question_input']],
        outputs=[shared.gradio['pdf_ai_status'], shared.gradio['pdf_ai_output']],
        show_progress=True,
    )

"""Gradio UI tab for the AI-Powered Reading List."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.reading_list import (
    DIFFICULTY_OPTIONS,
    STATUS_OPTIONS,
    generate_literature_review,
    generate_reading_list,
    list_reading_lists,
    load_reading_list,
    render_reading_list_html,
    save_reading_list,
)

_current_items: list = []


def _generate_fn(topic, count):
    global _current_items
    status, items = generate_reading_list(topic, int(count))
    if items:
        _current_items = items
    html = render_reading_list_html(_current_items)
    return status, html, gr.update(choices=list_reading_lists())


def _lit_review_fn():
    if not _current_items:
        return "❌ Generate a reading list first.", ""
    status, result = generate_literature_review(_current_items)
    return status, result or ""


def _filter_fn(filter_diff, filter_status):
    html = render_reading_list_html(_current_items, filter_diff, filter_status)
    return html


def _update_status_fn(title, new_status):
    """Update the status of an item in the current list."""
    global _current_items
    for item in _current_items:
        if item.get("title", "") == title:
            item["status"] = new_status
            break
    return render_reading_list_html(_current_items), "✅ Status updated."


def _save_fn(list_name):
    if not list_name:
        return "❌ Please enter a list name."
    if not _current_items:
        return "❌ No items to save."
    return save_reading_list(list_name, _current_items)


def _load_fn(list_name):
    global _current_items
    if not list_name:
        return "No list selected.", render_reading_list_html([])
    status, items = load_reading_list(list_name)
    if items:
        _current_items = items
    return status, render_reading_list_html(_current_items)


def _refresh_fn():
    return gr.update(choices=list_reading_lists())


def create_ui():
    with gr.Tab("📖 Reading List", elem_id="reading-list-tab"):
        with gr.Accordion("📥 Generate Reading List", open=True):
            with gr.Row():
                shared.gradio['rl_topic'] = gr.Textbox(
                    label="Topic or Course Name",
                    placeholder="e.g. Machine Learning, French Revolution, Organic Chemistry",
                )
                shared.gradio['rl_count'] = gr.Slider(
                    minimum=3, maximum=20, value=10, step=1, label="Number of Items"
                )
            shared.gradio['rl_generate_btn'] = gr.Button("📖 Generate Reading List", variant="primary")
            shared.gradio['rl_gen_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Row():
            shared.gradio['rl_filter_diff'] = gr.Dropdown(
                label="Filter by Difficulty",
                choices=["All"] + DIFFICULTY_OPTIONS,
                value="All",
            )
            shared.gradio['rl_filter_status'] = gr.Dropdown(
                label="Filter by Status",
                choices=["All"] + STATUS_OPTIONS,
                value="All",
            )

        shared.gradio['rl_list_display'] = gr.HTML(
            value=render_reading_list_html([]),
            label="Reading List",
        )

        with gr.Accordion("✏️ Update Item Status", open=False):
            with gr.Row():
                shared.gradio['rl_item_title'] = gr.Textbox(
                    label="Item Title (exact)",
                    placeholder="Paste the exact title of the item...",
                )
                shared.gradio['rl_item_status'] = gr.Dropdown(
                    label="New Status",
                    choices=STATUS_OPTIONS,
                    value="in progress",
                )
                shared.gradio['rl_update_status_btn'] = gr.Button("✅ Update Status")
            shared.gradio['rl_update_status_msg'] = gr.Textbox(label="Status", interactive=False)

        with gr.Row():
            shared.gradio['rl_lit_review_btn'] = gr.Button("📋 Generate Literature Review")
        shared.gradio['rl_lit_review_status'] = gr.Textbox(label="Status", interactive=False)
        shared.gradio['rl_lit_review_output'] = gr.Textbox(
            label="Literature Review", lines=10, interactive=False
        )

        with gr.Accordion("💾 Saved Lists", open=False):
            with gr.Row():
                shared.gradio['rl_list_name'] = gr.Textbox(
                    label="List Name",
                    placeholder="Enter a name to save...",
                )
                shared.gradio['rl_save_btn'] = gr.Button("💾 Save List")
            shared.gradio['rl_save_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['rl_list_selector'] = gr.Dropdown(
                label="Load Saved List",
                choices=list_reading_lists(),
                interactive=True,
            )
            with gr.Row():
                shared.gradio['rl_load_btn'] = gr.Button("📂 Load")
                shared.gradio['rl_refresh_btn'] = gr.Button("🔄 Refresh")


def create_event_handlers():
    shared.gradio['rl_generate_btn'].click(
        _generate_fn,
        inputs=[shared.gradio['rl_topic'], shared.gradio['rl_count']],
        outputs=[
            shared.gradio['rl_gen_status'],
            shared.gradio['rl_list_display'],
            shared.gradio['rl_list_selector'],
        ],
        show_progress=True,
    )

    shared.gradio['rl_filter_diff'].change(
        _filter_fn,
        inputs=[shared.gradio['rl_filter_diff'], shared.gradio['rl_filter_status']],
        outputs=[shared.gradio['rl_list_display']],
        show_progress=False,
    )

    shared.gradio['rl_filter_status'].change(
        _filter_fn,
        inputs=[shared.gradio['rl_filter_diff'], shared.gradio['rl_filter_status']],
        outputs=[shared.gradio['rl_list_display']],
        show_progress=False,
    )

    shared.gradio['rl_update_status_btn'].click(
        _update_status_fn,
        inputs=[shared.gradio['rl_item_title'], shared.gradio['rl_item_status']],
        outputs=[shared.gradio['rl_list_display'], shared.gradio['rl_update_status_msg']],
        show_progress=False,
    )

    shared.gradio['rl_lit_review_btn'].click(
        _lit_review_fn,
        inputs=[],
        outputs=[shared.gradio['rl_lit_review_status'], shared.gradio['rl_lit_review_output']],
        show_progress=True,
    )

    shared.gradio['rl_save_btn'].click(
        _save_fn,
        inputs=[shared.gradio['rl_list_name']],
        outputs=[shared.gradio['rl_save_status']],
        show_progress=True,
    )

    shared.gradio['rl_load_btn'].click(
        _load_fn,
        inputs=[shared.gradio['rl_list_selector']],
        outputs=[shared.gradio['rl_save_status'], shared.gradio['rl_list_display']],
        show_progress=True,
    )

    shared.gradio['rl_refresh_btn'].click(
        _refresh_fn,
        inputs=[],
        outputs=[shared.gradio['rl_list_selector']],
        show_progress=False,
    )

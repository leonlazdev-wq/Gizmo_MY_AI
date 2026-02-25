"""Memory UI tab."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.chat_memory import (
    _CATEGORIES,
    add_memory,
    auto_extract_memories,
    delete_memory,
    export_memories,
    get_memory_stats,
    get_memory_table,
    import_memories,
)
from modules.utils import gradio


def create_ui() -> None:
    with gr.Tab("Memory", elem_id="memory-tab"):
        gr.Markdown("## 🧠 Chat Memory")
        gr.Markdown("Save important facts about yourself so the AI remembers them across sessions.")

        with gr.Row():
            shared.gradio['mem_enable'] = gr.Checkbox(label="Enable Memory (inject into prompts)", value=True)
            shared.gradio['mem_auto_extract'] = gr.Checkbox(label="Auto-Extract facts from chat", value=False)

        gr.Markdown("### ➕ Add Memory")
        with gr.Row():
            shared.gradio['mem_fact'] = gr.Textbox(
                label="Fact",
                placeholder="I am studying biology in 10th grade",
                scale=4
            )
            shared.gradio['mem_category'] = gr.Dropdown(
                label="Category",
                choices=_CATEGORIES,
                value="personal",
                scale=1
            )
            shared.gradio['mem_save_btn'] = gr.Button("Save", variant="primary", scale=1)

        shared.gradio['mem_status'] = gr.Markdown("")

        gr.Markdown("### 🔍 Search & Manage Memories")
        shared.gradio['mem_search'] = gr.Textbox(
            label="Search memories",
            placeholder="Type to filter...",
        )

        shared.gradio['mem_table'] = gr.Dataframe(
            headers=["Fact", "Category", "Date", "Source"],
            datatype=["str", "str", "str", "str"],
            value=get_memory_table(),
            interactive=False,
            label="Saved Memories"
        )

        with gr.Row():
            shared.gradio['mem_delete_fact'] = gr.Textbox(
                label="Fact to delete (exact text)",
                placeholder="Paste the exact fact text to delete",
                scale=3
            )
            shared.gradio['mem_delete_btn'] = gr.Button("Delete", scale=1)

        gr.Markdown("### 📤 Import / Export")
        with gr.Row():
            shared.gradio['mem_export_btn'] = gr.Button("Export memory.json")
            shared.gradio['mem_export_file'] = gr.File(label="Download", interactive=False)

        with gr.Row():
            shared.gradio['mem_import_file'] = gr.File(label="Upload memory.json to import", type="filepath")
            shared.gradio['mem_import_btn'] = gr.Button("Import")

        gr.Markdown("### 🤖 Auto-Extract from Text")
        shared.gradio['mem_extract_text'] = gr.Textbox(
            label="Paste conversation text",
            lines=4,
            placeholder="Paste a recent chat exchange here to auto-extract facts..."
        )
        shared.gradio['mem_extract_btn'] = gr.Button("Extract Facts from Text")

        gr.Markdown("### 📊 Memory Stats")
        shared.gradio['mem_stats'] = gr.Markdown(get_memory_stats())


def create_event_handlers() -> None:
    shared.gradio['mem_save_btn'].click(
        add_memory,
        gradio('mem_fact', 'mem_category'),
        gradio('mem_status', 'mem_table'),
        show_progress=False
    )

    shared.gradio['mem_search'].change(
        lambda q: get_memory_table(q),
        gradio('mem_search'),
        gradio('mem_table'),
        show_progress=False
    )

    shared.gradio['mem_delete_btn'].click(
        delete_memory,
        gradio('mem_delete_fact'),
        gradio('mem_status', 'mem_table'),
        show_progress=False
    )

    shared.gradio['mem_export_btn'].click(
        export_memories,
        None,
        gradio('mem_export_file'),
        show_progress=False
    )

    shared.gradio['mem_import_btn'].click(
        import_memories,
        gradio('mem_import_file'),
        gradio('mem_status', 'mem_table'),
        show_progress=False
    )

    shared.gradio['mem_extract_btn'].click(
        auto_extract_memories,
        gradio('mem_extract_text'),
        gradio('mem_status', 'mem_table'),
        show_progress=True
    )

    shared.gradio['mem_stats'].change(
        lambda: get_memory_stats(),
        None,
        gradio('mem_stats'),
        show_progress=False
    )

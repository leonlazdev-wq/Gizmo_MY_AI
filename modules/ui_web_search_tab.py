"""Web Search UI tab."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.utils import gradio
from modules.web_search_engine import search_and_ask


def create_ui() -> None:
    with gr.Tab("Web Search", elem_id="web-search-tab"):
        gr.Markdown("## 🌐 Web Search")
        gr.Markdown("Search the web in real-time and let the AI synthesize an answer with citations.")

        with gr.Row():
            shared.gradio['ws_query'] = gr.Textbox(
                label="🔍 Search Query",
                placeholder="What is the latest news about AI?",
                scale=4
            )
            shared.gradio['ws_search_btn'] = gr.Button("Search & Ask AI", variant="primary", scale=1)

        shared.gradio['ws_answer'] = gr.Markdown(label="🤖 AI Answer with Citations", value="")

        with gr.Accordion("📄 Raw Search Results", open=False):
            shared.gradio['ws_raw'] = gr.Markdown(value="")

        with gr.Row():
            shared.gradio['ws_num_results'] = gr.Slider(
                label="Number of results",
                minimum=3,
                maximum=10,
                step=1,
                value=5
            )
            shared.gradio['ws_engine'] = gr.Dropdown(
                label="Search Engine",
                choices=["duckduckgo", "scraper"],
                value="duckduckgo"
            )

        gr.Markdown("### 📜 Search History")
        shared.gradio['ws_history'] = gr.Dataframe(
            headers=["Query", "Answer Preview"],
            datatype=["str", "str"],
            interactive=False,
            label="Previous searches"
        )


def create_event_handlers() -> None:
    shared.gradio['ws_search_btn'].click(
        search_and_ask,
        gradio('ws_query', 'ws_num_results', 'ws_engine'),
        gradio('ws_answer', 'ws_raw', 'ws_history'),
        show_progress=True
    )

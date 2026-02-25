"""Gradio UI tab for the Notion Integration feature."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.notion_integration import NotionManager

TUTORIAL_URL = (
    "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab"
    "/blob/main/README.md#notion-integration"
)

_notion = NotionManager()
_pages_cache: list[dict] = []


def _generate_reply(prompt: str) -> str:
    try:
        from modules.text_generation import generate_reply as _gen  # type: ignore
        full = ""
        for chunk in _gen(prompt, state={}, stopping_strings=[]):
            if isinstance(chunk, str):
                full = chunk
        return full
    except Exception as exc:
        return f"⚠️ Could not get AI response: {exc}"


def _connect(api_key: str):
    success, msg = _notion.connect(api_key)
    color = "#4CAF50" if success else "#f44336"
    html = f"<div style='color:{color};font-weight:600'>{msg}</div>"
    return html


def _fetch_pages():
    global _pages_cache
    pages, msg = _notion.list_pages()
    _pages_cache = pages
    choices = [f"{p['title']} ({p['id']})" for p in pages]
    return msg, gr.update(choices=choices, value=choices[0] if choices else None)


def _import_page(page_selector: str):
    if not page_selector:
        return "No page selected.", ""
    page_id = _parse_page_id(page_selector)
    content, msg = _notion.fetch_page_content(page_id)
    return msg, content


def _ask_ai_about_page(page_selector: str):
    if not page_selector:
        return "No page selected."
    page_id = _parse_page_id(page_selector)
    content, _ = _notion.fetch_page_content(page_id)
    if not content:
        return "Could not fetch page content."
    prompt = f"Please summarize and answer questions about the following Notion page content:\n\n{content}"
    return _generate_reply(prompt)


def _save_chat_to_notion(title: str, chat_history: list, target_page: str):
    if not chat_history:
        return "No chat history to save."
    md_lines = [f"# {title or 'AI Chat Export'}\n"]
    for user_msg, bot_msg in (chat_history or []):
        md_lines.append(f"**User:** {user_msg}\n\n**AI:** {bot_msg}\n\n---\n")
    content = "\n".join(md_lines)
    parent_id = _parse_page_id(target_page) if target_page else None
    url, msg = _notion.create_page(title or "AI Chat Export", content, parent_id)
    return msg


def _parse_page_id(selector: str) -> str:
    """Extract Notion page ID from 'Title (page_id)' formatted string."""
    if not selector:
        return ""
    if "(" in selector and selector.endswith(")"):
        return selector.rsplit("(", 1)[-1].rstrip(")")
    return selector


def create_ui():
    with gr.Tab("📓 Notion", elem_id="notion-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: Notion Integration</a>"
            f"</div>"
        )

        with gr.Row():
            shared.gradio['notion_api_key'] = gr.Textbox(
                label="Notion API Key (Internal Integration Token)",
                placeholder="secret_...",
                type="password",
                scale=4,
            )
            shared.gradio['notion_connect_btn'] = gr.Button("Connect", variant="primary", scale=1)
        shared.gradio['notion_status'] = gr.HTML("<div style='color:#888'>Not connected</div>")

        with gr.Accordion("📖 Setup Instructions", open=False):
            gr.Markdown(
                "1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)\n"
                "2. Click **+ New integration**\n"
                "3. Give it a name and select your workspace\n"
                "4. Copy the **Internal Integration Token** and paste it above\n"
                "5. Share the pages you want to access with the integration (open the page → Share → search for your integration name)"
            )

        gr.Markdown("---")
        gr.Markdown("### 📥 Read from Notion")
        with gr.Row():
            shared.gradio['notion_fetch_btn'] = gr.Button("Fetch Pages")
            shared.gradio['notion_page_selector'] = gr.Dropdown(
                label="Page", choices=[], value=None, interactive=True, scale=3
            )
        shared.gradio['notion_fetch_status'] = gr.Textbox(label="Status", interactive=False)
        with gr.Row():
            shared.gradio['notion_import_btn'] = gr.Button("Import Page")
            shared.gradio['notion_ask_btn'] = gr.Button("Ask AI About Page")
            shared.gradio['notion_summarize_btn'] = gr.Button("Summarize Page")
        shared.gradio['notion_import_status'] = gr.Textbox(label="Import Status", interactive=False)
        shared.gradio['notion_page_content'] = gr.Markdown("")
        shared.gradio['notion_ai_response'] = gr.Markdown("")

        gr.Markdown("---")
        gr.Markdown("### 📤 Write to Notion")
        shared.gradio['notion_page_title'] = gr.Textbox(
            label="Page Title", placeholder="My AI Notes"
        )
        shared.gradio['notion_target_page'] = gr.Dropdown(
            label="Target Page/Parent (optional)", choices=[], value=None, interactive=True
        )
        shared.gradio['notion_save_btn'] = gr.Button("Save Chat to Notion", variant="primary")
        shared.gradio['notion_save_status'] = gr.Textbox(label="Save Status", interactive=False)


def create_event_handlers():
    shared.gradio['notion_connect_btn'].click(
        _connect,
        inputs=[shared.gradio['notion_api_key']],
        outputs=[shared.gradio['notion_status']],
    )

    shared.gradio['notion_fetch_btn'].click(
        _fetch_pages,
        inputs=[],
        outputs=[shared.gradio['notion_fetch_status'], shared.gradio['notion_page_selector']],
    )

    shared.gradio['notion_import_btn'].click(
        _import_page,
        inputs=[shared.gradio['notion_page_selector']],
        outputs=[shared.gradio['notion_import_status'], shared.gradio['notion_page_content']],
    )

    shared.gradio['notion_ask_btn'].click(
        _ask_ai_about_page,
        inputs=[shared.gradio['notion_page_selector']],
        outputs=[shared.gradio['notion_ai_response']],
    )

    shared.gradio['notion_summarize_btn'].click(
        lambda sel: _generate_reply(
            f"Summarize the following Notion page:\n\n{_notion.fetch_page_content(_parse_page_id(sel))[0]}"
        ) if sel else "No page selected.",
        inputs=[shared.gradio['notion_page_selector']],
        outputs=[shared.gradio['notion_ai_response']],
    )

    shared.gradio['notion_save_btn'].click(
        _save_chat_to_notion,
        inputs=[
            shared.gradio['notion_page_title'],
            gr.State([]),  # placeholder — wire to actual chat history if desired
            shared.gradio['notion_target_page'],
        ],
        outputs=[shared.gradio['notion_save_status']],
    )

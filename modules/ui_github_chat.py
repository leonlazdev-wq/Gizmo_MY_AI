"""Gradio UI tab for the GitHub Repo Chat feature."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.github_repo_chat import RepoSession

TUTORIAL_URL = (
    "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab"
    "/blob/main/README.md#github-repo-chat"
)

# One RepoSession per process (stateful)
_session = RepoSession()


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


def _load_repo(url: str, token: str):
    result = _session.load_repo(url, token or None)
    if result["success"]:
        stats = result["stats"]
        lang_str = ", ".join(
            f"{ext}:{cnt}" for ext, cnt in sorted(stats.get("languages", {}).items(), key=lambda x: -x[1])[:5]
        )
        info_md = (
            f"**Files:** {stats.get('files', 0)} | "
            f"**Size:** {stats.get('size_mb', 0)} MB | "
            f"**Languages:** {lang_str}"
        )
        if stats.get("warning"):
            info_md += f"\n\n⚠️ {stats['warning']}"
        files = _session.list_files()
        return (
            result["message"],
            info_md,
            gr.update(choices=files, value=files[0] if files else None),
            "",
        )
    return (
        result["message"],
        "",
        gr.update(choices=[], value=None),
        "",
    )


def _view_file(filepath: str):
    if not filepath:
        return ""
    content = _session.get_file_content(filepath)
    return f"```\n{content[:8000]}\n```"


def _chat(question: str, history: list):
    if not question.strip():
        return history, ""
    selected_file = None  # could extend to pass current file
    context = _session.build_context(question, selected_file)
    if not context.strip():
        answer = "No repository loaded. Please load a repository first."
    else:
        answer = _generate_reply(context)
    history = history or []
    history.append([question, answer])
    return history, ""


def _quick_action(action: str, filepath: str, history: list):
    prompts = {
        "Explain": f"Explain the main purpose and functionality of the file `{filepath}`.",
        "Find Bugs": f"Identify potential bugs or issues in the file `{filepath}`.",
        "Suggest Improvements": f"Suggest code improvements for the file `{filepath}`.",
        "Generate Tests": f"Generate unit tests for the file `{filepath}`.",
    }
    question = prompts.get(action, f"Describe the file `{filepath}`.")
    return _chat(question, history)


def create_ui():
    with gr.Tab("🐙 GitHub Repo Chat", elem_id="github-repo-chat-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: GitHub Repo Chat</a>"
            f"</div>"
        )

        with gr.Row():
            shared.gradio['gh_url'] = gr.Textbox(
                label="GitHub Repo URL",
                placeholder="https://github.com/user/repo",
                scale=3,
            )
            shared.gradio['gh_token'] = gr.Textbox(
                label="Access Token (optional)",
                placeholder="ghp_...",
                type="password",
                scale=2,
            )
            shared.gradio['gh_load_btn'] = gr.Button("Load Repo", variant="primary", scale=1)

        shared.gradio['gh_load_status'] = gr.Textbox(label="Status", interactive=False)
        shared.gradio['gh_repo_info'] = gr.Markdown("")

        with gr.Row():
            shared.gradio['gh_file_browser'] = gr.Dropdown(
                label="Browse Files",
                choices=[],
                value=None,
                interactive=True,
                scale=4,
            )
            shared.gradio['gh_view_btn'] = gr.Button("View File", scale=1)

        shared.gradio['gh_code_viewer'] = gr.Markdown("")

        gr.Markdown("---")
        shared.gradio['gh_chatbot'] = gr.Chatbot(label="Chat with the Codebase", height=350)
        with gr.Row():
            shared.gradio['gh_question'] = gr.Textbox(
                label="Your Question",
                placeholder="Explain the main() function...",
                scale=4,
            )
            shared.gradio['gh_ask_btn'] = gr.Button("Ask", variant="primary", scale=1)

        with gr.Row():
            for action in ["Explain", "Find Bugs", "Suggest Improvements", "Generate Tests"]:
                btn_key = f"gh_quick_{action.lower().replace(' ', '_')}"
                shared.gradio[btn_key] = gr.Button(action, size="sm")


def create_event_handlers():
    shared.gradio['gh_load_btn'].click(
        _load_repo,
        inputs=[shared.gradio['gh_url'], shared.gradio['gh_token']],
        outputs=[
            shared.gradio['gh_load_status'],
            shared.gradio['gh_repo_info'],
            shared.gradio['gh_file_browser'],
            shared.gradio['gh_code_viewer'],
        ],
    )

    shared.gradio['gh_view_btn'].click(
        _view_file,
        inputs=[shared.gradio['gh_file_browser']],
        outputs=[shared.gradio['gh_code_viewer']],
    )

    shared.gradio['gh_ask_btn'].click(
        _chat,
        inputs=[shared.gradio['gh_question'], shared.gradio['gh_chatbot']],
        outputs=[shared.gradio['gh_chatbot'], shared.gradio['gh_question']],
    )

    for action in ["Explain", "Find Bugs", "Suggest Improvements", "Generate Tests"]:
        btn_key = f"gh_quick_{action.lower().replace(' ', '_')}"
        shared.gradio[btn_key].click(
            _quick_action,
            inputs=[
                gr.State(action),
                shared.gradio['gh_file_browser'],
                shared.gradio['gh_chatbot'],
            ],
            outputs=[shared.gradio['gh_chatbot'], shared.gradio['gh_question']],
        )

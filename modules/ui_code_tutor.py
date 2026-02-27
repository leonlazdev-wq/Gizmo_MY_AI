"""Gradio UI tab for the Code Tutor & Sandbox."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.code_tutor import (
    LANGUAGES,
    execute_code,
    explain_concept,
    get_ai_feedback,
    get_ai_hint,
    list_sessions,
    load_session,
    save_session,
)

# Module-level state so event handlers can access last run results
_last_stdout: str = ""
_last_stderr: str = ""


# ---------------------------------------------------------------------------
# Callback functions
# ---------------------------------------------------------------------------

def _run_code_fn(language, code):
    global _last_stdout, _last_stderr
    status, stdout, stderr = execute_code(language, code)
    _last_stdout = stdout
    _last_stderr = stderr

    # Build a combined console output
    console = ""
    if stdout:
        console += stdout
    if stderr:
        console += ("\n--- ERRORS ---\n" if stdout else "--- ERRORS ---\n") + stderr
    if not stdout and not stderr:
        console = "(no output)"

    return status, console


def _feedback_fn(language, code, question):
    status, feedback = get_ai_feedback(
        code, _last_stdout, _last_stderr, language, question
    )
    return status, feedback


def _hint_fn(language, code):
    status, hint = get_ai_hint(code, language)
    return hint or status


def _explain_fn(language, concept):
    status, explanation = explain_concept(concept, language)
    return explanation or status


def _save_fn(code, language):
    return save_session(code, language, _last_stdout, _last_stderr)


def _load_fn(name):
    if not name:
        return "No session selected.", "", "Python", ""
    status, data = load_session(name)
    if not data:
        return status, "", "Python", ""
    console = data.get("stdout", "")
    if data.get("stderr"):
        console += ("\n--- ERRORS ---\n" if console else "--- ERRORS ---\n") + data["stderr"]
    return status, data.get("code", ""), data.get("language", "Python"), console


def _refresh_sessions_fn():
    return gr.update(choices=list_sessions())


# ---------------------------------------------------------------------------
# UI creation
# ---------------------------------------------------------------------------

def create_ui():
    with gr.Tab("💻 Code Tutor", elem_id="code-tutor-tab"):
        gr.Markdown("### 💻 Code Tutor & Sandbox\nWrite code, run it safely in the cloud, and get AI-powered feedback.")

        with gr.Row():
            # ---- Left column: editor + console ----
            with gr.Column(scale=3):
                with gr.Row():
                    shared.gradio['ct_language'] = gr.Dropdown(
                        label="Language",
                        choices=list(LANGUAGES.keys()),
                        value="Python",
                    )
                    shared.gradio['ct_run_btn'] = gr.Button("▶ Run Code", variant="primary")

                shared.gradio['ct_code'] = gr.Code(
                    label="Code Editor",
                    language="python",
                    lines=18,
                    interactive=True,
                )

                shared.gradio['ct_status'] = gr.Textbox(label="Status", interactive=False)

                with gr.Accordion("📟 Console Output", open=True):
                    shared.gradio['ct_console'] = gr.Textbox(
                        label="Output",
                        lines=10,
                        interactive=False,
                        show_copy_button=True,
                    )

            # ---- Right column: AI tutor ----
            with gr.Column(scale=2):
                with gr.Accordion("🤖 AI Tutor", open=True):
                    shared.gradio['ct_question'] = gr.Textbox(
                        label="Ask a question (optional)",
                        placeholder="e.g. Why is my loop not terminating?",
                        lines=2,
                    )
                    with gr.Row():
                        shared.gradio['ct_feedback_btn'] = gr.Button("🤖 Get AI Feedback", variant="primary")
                        shared.gradio['ct_hint_btn'] = gr.Button("💡 Hint")

                    shared.gradio['ct_feedback'] = gr.Textbox(
                        label="Tutor Response",
                        lines=14,
                        interactive=False,
                        show_copy_button=True,
                    )

                with gr.Accordion("📖 Learn a Concept", open=False):
                    shared.gradio['ct_concept_input'] = gr.Textbox(
                        label="Concept",
                        placeholder="e.g. recursion, list comprehensions, async/await",
                    )
                    shared.gradio['ct_concept_btn'] = gr.Button("📖 Explain Concept")
                    shared.gradio['ct_concept_output'] = gr.Textbox(
                        label="Explanation",
                        lines=10,
                        interactive=False,
                        show_copy_button=True,
                    )

        # ---- Session history ----
        with gr.Accordion("💾 Session History", open=False):
            shared.gradio['ct_session_selector'] = gr.Dropdown(
                label="Load Previous Session",
                choices=list_sessions(),
                interactive=True,
            )
            with gr.Row():
                shared.gradio['ct_load_btn'] = gr.Button("📂 Load")
                shared.gradio['ct_save_btn'] = gr.Button("💾 Save Current")
                shared.gradio['ct_refresh_btn'] = gr.Button("🔄 Refresh")
            shared.gradio['ct_history_status'] = gr.Textbox(label="Status", interactive=False)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def create_event_handlers():
    # Run code
    shared.gradio['ct_run_btn'].click(
        _run_code_fn,
        inputs=[shared.gradio['ct_language'], shared.gradio['ct_code']],
        outputs=[shared.gradio['ct_status'], shared.gradio['ct_console']],
        show_progress=True,
    )

    # AI feedback
    shared.gradio['ct_feedback_btn'].click(
        _feedback_fn,
        inputs=[
            shared.gradio['ct_language'],
            shared.gradio['ct_code'],
            shared.gradio['ct_question'],
        ],
        outputs=[shared.gradio['ct_status'], shared.gradio['ct_feedback']],
        show_progress=True,
    )

    # Hint
    shared.gradio['ct_hint_btn'].click(
        _hint_fn,
        inputs=[shared.gradio['ct_language'], shared.gradio['ct_code']],
        outputs=[shared.gradio['ct_feedback']],
        show_progress=True,
    )

    # Explain concept
    shared.gradio['ct_concept_btn'].click(
        _explain_fn,
        inputs=[shared.gradio['ct_language'], shared.gradio['ct_concept_input']],
        outputs=[shared.gradio['ct_concept_output']],
        show_progress=True,
    )

    # Save session
    shared.gradio['ct_save_btn'].click(
        _save_fn,
        inputs=[shared.gradio['ct_code'], shared.gradio['ct_language']],
        outputs=[shared.gradio['ct_history_status']],
        show_progress=True,
    )

    # Load session
    shared.gradio['ct_load_btn'].click(
        _load_fn,
        inputs=[shared.gradio['ct_session_selector']],
        outputs=[
            shared.gradio['ct_history_status'],
            shared.gradio['ct_code'],
            shared.gradio['ct_language'],
            shared.gradio['ct_console'],
        ],
        show_progress=True,
    )

    # Refresh session list
    shared.gradio['ct_refresh_btn'].click(
        _refresh_sessions_fn,
        inputs=[],
        outputs=[shared.gradio['ct_session_selector']],
        show_progress=False,
    )

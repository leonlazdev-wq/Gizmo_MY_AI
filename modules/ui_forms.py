"""Forms sidebar-like tab for structured data collection."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.forms import run_form
from modules.utils import gradio


def _submit_form(title: str, email: str, date: str, severity: str) -> str:
    result = run_form(
        session_id="default_session",
        template_id="bug_report",
        values={"title": title, "email": email, "date": date, "severity": severity},
    )
    if result["status"] == "ok":
        return f"✅ Form submitted: {result['path']}"
    return f"❌ Missing/invalid fields: {', '.join(result['errors'])}"


def create_ui() -> None:
    """Render Forms tab."""
    with gr.Tab("Forms", elem_id="forms-tab"):
        gr.Markdown("## 🧩 Conversational Forms")
        # Visual mock: Step 2/5 [title][email][date] -> Next
        shared.gradio["forms_template"] = gr.Dropdown(label="Template", choices=["bug_report"], value="bug_report")
        shared.gradio["forms_start_btn"] = gr.Button("Start form")
        shared.gradio["forms_progress"] = gr.Markdown("Step 1 of 4")
        shared.gradio["forms_title"] = gr.Textbox(label="Bug title")
        shared.gradio["forms_email"] = gr.Textbox(label="Reporter email")
        shared.gradio["forms_date"] = gr.Textbox(label="Date (YYYY-MM-DD)")
        shared.gradio["forms_severity"] = gr.Dropdown(label="Severity", choices=["low", "medium", "high"], value="medium")
        with gr.Row():
            shared.gradio["forms_submit_btn"] = gr.Button("Submit", variant="primary")
            shared.gradio["forms_save_draft_btn"] = gr.Button("Save Draft")
        shared.gradio["forms_status"] = gr.Textbox(label="Form status", interactive=False)


def create_event_handlers() -> None:
    """Wire form submit handler."""
    shared.gradio["forms_submit_btn"].click(
        _submit_form,
        gradio("forms_title", "forms_email", "forms_date", "forms_severity"),
        gradio("forms_status"),
        show_progress=False,
    )
    shared.gradio["forms_save_draft_btn"].click(lambda: "✅ Draft saved (local)", None, gradio("forms_status"), show_progress=False)

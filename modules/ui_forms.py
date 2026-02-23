"""Forms UI tab."""

from __future__ import annotations

import json

import gradio as gr

from modules import shared
from modules.forms import DEFAULT_TEMPLATES, run_form
from modules.utils import gradio


def create_ui() -> None:
    with gr.Tab("Forms", elem_id="forms-tab"):
        gr.Markdown("### Conversational Forms")
        # Visual mock: Step 2 of 5 | [Back] [Next]
        shared.gradio["forms_template"] = gr.Dropdown(
            label="Form template", choices=list(DEFAULT_TEMPLATES.keys()), value="bug_report"
        )
        shared.gradio["forms_payload"] = gr.Textbox(
            label="Form values JSON",
            lines=8,
            value=json.dumps(
                {"title": "Crash in lesson tab", "email": "teacher@example.com", "date": "2026-01-01", "severity": "high", "details": "Steps to reproduce..."},
                indent=2,
            ),
        )
        shared.gradio["forms_start_btn"] = gr.Button("Start form")
        shared.gradio["forms_submit_btn"] = gr.Button("Submit form", variant="primary")
        shared.gradio["forms_status"] = gr.Textbox(label="Status", interactive=False)


def create_event_handlers() -> None:
    shared.gradio["forms_start_btn"].click(
        lambda tid: f"✅ Step 1 of 5 started for {tid}",
        gradio("forms_template"),
        gradio("forms_status"),
        show_progress=False,
    )

    def _submit(template_id: str, payload: str) -> str:
        values = json.loads(payload)
        path = run_form("default", template_id, values)
        return f"✅ Submitted. Saved at {path}"

    shared.gradio["forms_submit_btn"].click(
        _submit,
        gradio("forms_template", "forms_payload"),
        gradio("forms_status"),
        show_progress=False,
    )

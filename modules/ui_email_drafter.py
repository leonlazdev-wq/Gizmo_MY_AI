"""Gradio UI tab for the AI Email/Message Drafter."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.email_drafter import TEMPLATES, TONES, generate_email, get_memory_autofill


def _do_autofill():
    """Load values from chat memory and return updates for fields."""
    data = get_memory_autofill()
    return (
        gr.update(value=data.get("professor", "")),
        gr.update(value=data.get("subject", "")),
        gr.update(value=data.get("name", "")),
    )


def _do_generate(recipient, subject, purpose, tone, template_name, sender_name):
    text, err = generate_email(recipient, subject, purpose, tone, template_name, sender_name)
    if err:
        return err
    return text


def create_ui():
    with gr.Tab("📧 Email Drafter", elem_id="email-drafter-tab"):
        gr.Markdown("### 📧 AI Email/Message Drafter\nGenerate professional emails and messages for any academic situation.")

        with gr.Row():
            shared.gradio['ed_template'] = gr.Dropdown(
                label="Template",
                choices=list(TEMPLATES.keys()),
                value=list(TEMPLATES.keys())[0],
            )
            shared.gradio['ed_tone'] = gr.Dropdown(
                label="Tone",
                choices=TONES,
                value="formal",
            )

        with gr.Row():
            shared.gradio['ed_recipient'] = gr.Textbox(
                label="Recipient Name (Professor / Classmate)",
                placeholder="e.g. Dr. Smith",
                scale=2,
            )
            shared.gradio['ed_subject'] = gr.Textbox(
                label="Subject / Class",
                placeholder="e.g. Introduction to Psychology",
                scale=2,
            )
            shared.gradio['ed_sender_name'] = gr.Textbox(
                label="Your Name (optional)",
                placeholder="e.g. Alex Johnson",
                scale=1,
            )

        shared.gradio['ed_purpose'] = gr.Textbox(
            label="Purpose / Context",
            placeholder="Describe what you need the email to say or accomplish…",
            lines=4,
        )

        with gr.Row():
            shared.gradio['ed_autofill_btn'] = gr.Button("🧠 Auto-fill from Memory", variant="secondary")
            shared.gradio['ed_generate_btn'] = gr.Button("✉️ Generate Email", variant="primary")

        shared.gradio['ed_output'] = gr.Textbox(
            label="Generated Email",
            lines=12,
            interactive=True,
            placeholder="Your generated email will appear here…",
        )

        shared.gradio['ed_copy_btn'] = gr.Button("📋 Copy to Clipboard")
        shared.gradio['ed_copy_status'] = gr.Textbox(label="", interactive=False, visible=True, max_lines=1)


def create_event_handlers():
    shared.gradio['ed_autofill_btn'].click(
        _do_autofill,
        inputs=[],
        outputs=[
            shared.gradio['ed_recipient'],
            shared.gradio['ed_subject'],
            shared.gradio['ed_sender_name'],
        ],
        show_progress=False,
    )

    shared.gradio['ed_generate_btn'].click(
        _do_generate,
        inputs=[
            shared.gradio['ed_recipient'],
            shared.gradio['ed_subject'],
            shared.gradio['ed_purpose'],
            shared.gradio['ed_tone'],
            shared.gradio['ed_template'],
            shared.gradio['ed_sender_name'],
        ],
        outputs=[shared.gradio['ed_output']],
        show_progress=True,
    )

    shared.gradio['ed_copy_btn'].click(
        None,
        inputs=[shared.gradio['ed_output']],
        outputs=[shared.gradio['ed_copy_status']],
        js="(text) => { navigator.clipboard.writeText(text); return '✅ Copied to clipboard!'; }",
    )

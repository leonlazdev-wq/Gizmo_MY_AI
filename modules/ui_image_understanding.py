"""Image Understanding UI tab."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.image_understanding import ask_and_record
from modules.utils import gradio


def create_ui() -> None:
    with gr.Tab("Image Understanding", elem_id="image-understanding-tab"):
        gr.Markdown("## 🖼️ Image Understanding")
        gr.Markdown("Upload an image and ask questions about it – great for diagrams, math problems, and more.")

        with gr.Row():
            with gr.Column(scale=1):
                shared.gradio['iu_image'] = gr.Image(
                    type="filepath",
                    label="📷 Upload Image (drag & drop)"
                )

                gr.Markdown("**Quick Presets:**")
                with gr.Row():
                    shared.gradio['iu_preset_describe'] = gr.Button("Describe this image")
                    shared.gradio['iu_preset_solve'] = gr.Button("Solve this problem")
                with gr.Row():
                    shared.gradio['iu_preset_explain'] = gr.Button("Explain this diagram")
                    shared.gradio['iu_preset_ocr'] = gr.Button("What text is in this image?")

            with gr.Column(scale=2):
                shared.gradio['iu_question'] = gr.Textbox(
                    label="❓ Your Question",
                    placeholder="What is this diagram showing?",
                    lines=3
                )
                shared.gradio['iu_ask_btn'] = gr.Button("Ask AI", variant="primary")
                shared.gradio['iu_response'] = gr.Markdown(label="🤖 AI Response", value="")

        gr.Markdown("### 📜 Session History")
        shared.gradio['iu_history'] = gr.Dataframe(
            headers=["Question", "Answer"],
            datatype=["str", "str"],
            interactive=False,
            label="Previous Q&A pairs"
        )


def create_event_handlers() -> None:
    shared.gradio['iu_ask_btn'].click(
        ask_and_record,
        gradio('iu_image', 'iu_question'),
        gradio('iu_response', 'iu_history'),
        show_progress=True
    )

    # Preset buttons
    for btn_key, preset_text in [
        ('iu_preset_describe', 'Describe this image'),
        ('iu_preset_solve', 'Solve this problem'),
        ('iu_preset_explain', 'Explain this diagram'),
        ('iu_preset_ocr', 'What text is in this image?'),
    ]:
        shared.gradio[btn_key].click(
            lambda t=preset_text: t,
            None,
            gradio('iu_question'),
            show_progress=False
        )

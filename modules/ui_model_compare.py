"""Model Compare UI tab."""

from __future__ import annotations

import gradio as gr

from modules import shared, utils
from modules.model_compare import compare_models, get_compare_history, vote
from modules.utils import gradio


def _get_model_choices() -> list[str]:
    models = utils.get_available_models()
    return ["None"] + list(models) if models else ["None"]


def create_ui() -> None:
    with gr.Tab("Model Compare", elem_id="model-compare-tab"):
        gr.Markdown("## ⚖️ Model Compare")
        gr.Markdown(
            "Ask the same question to two models and compare their responses side by side.\n\n"
            "⚠️ **Note:** Switching models requires loading/unloading which takes time and VRAM."
        )

        choices = _get_model_choices()
        with gr.Row():
            shared.gradio['mc_model_a'] = gr.Dropdown(
                label="🅰 Model A",
                choices=choices,
                value=choices[0] if choices else "None"
            )
            shared.gradio['mc_model_b'] = gr.Dropdown(
                label="🅱 Model B",
                choices=choices,
                value=choices[1] if len(choices) > 1 else "None"
            )

        shared.gradio['mc_prompt'] = gr.Textbox(
            label="💬 Question / Prompt",
            placeholder="Explain quantum entanglement in simple terms.",
            lines=3
        )
        shared.gradio['mc_compare_btn'] = gr.Button("Compare", variant="primary")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 🅰 Response A")
                shared.gradio['mc_response_a'] = gr.Textbox(label="Model A Response", lines=8, interactive=False)
                shared.gradio['mc_meta_a'] = gr.Markdown("")

            with gr.Column():
                gr.Markdown("### 🅱 Response B")
                shared.gradio['mc_response_b'] = gr.Textbox(label="Model B Response", lines=8, interactive=False)
                shared.gradio['mc_meta_b'] = gr.Markdown("")

        with gr.Row():
            shared.gradio['mc_vote_a'] = gr.Button("👍 A is Better")
            shared.gradio['mc_vote_tie'] = gr.Button("🤝 Tie")
            shared.gradio['mc_vote_b'] = gr.Button("👍 B is Better")

        shared.gradio['mc_vote_status'] = gr.Markdown("")

        gr.Markdown("### 📜 Comparison History")
        shared.gradio['mc_history'] = gr.Dataframe(
            headers=["Model A", "Model B", "Prompt Preview"],
            datatype=["str", "str", "str"],
            interactive=False,
            label="Previous comparisons"
        )


def create_event_handlers() -> None:
    shared.gradio['mc_compare_btn'].click(
        compare_models,
        gradio('mc_model_a', 'mc_model_b', 'mc_prompt'),
        gradio('mc_response_a', 'mc_meta_a', 'mc_response_b', 'mc_meta_b'),
        show_progress=True
    )

    shared.gradio['mc_vote_a'].click(
        lambda a, b, p: vote("A", a, b, p),
        gradio('mc_model_a', 'mc_model_b', 'mc_prompt'),
        gradio('mc_vote_status'),
        show_progress=False
    )

    shared.gradio['mc_vote_tie'].click(
        lambda a, b, p: vote("Tie", a, b, p),
        gradio('mc_model_a', 'mc_model_b', 'mc_prompt'),
        gradio('mc_vote_status'),
        show_progress=False
    )

    shared.gradio['mc_vote_b'].click(
        lambda a, b, p: vote("B", a, b, p),
        gradio('mc_model_a', 'mc_model_b', 'mc_prompt'),
        gradio('mc_vote_status'),
        show_progress=False
    )

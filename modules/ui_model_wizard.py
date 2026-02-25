import gradio as gr

from modules import shared
from modules.model_catalog import USE_CASE_LABELS, get_system_resources, recommend_models
from modules.utils import gradio

_WIZARD_FLAG = "user_data/.wizard_completed"


def _mark_wizard_done():
    try:
        from pathlib import Path
        Path(_WIZARD_FLAG).touch()
    except Exception:
        pass


def _wizard_done() -> bool:
    from pathlib import Path
    return Path(_WIZARD_FLAG).exists()


def _run_wizard(selected_use_cases):
    """Return recommendation HTML based on selected use cases."""
    resources = get_system_resources()
    ram = resources.get("ram_gb")
    models = recommend_models(selected_use_cases, available_ram_gb=ram)
    if not models:
        return "<p>No matching models found. Try selecting different use cases.</p>", resources.get("gpu_info", "Unknown"), f"{ram:.1f} GB" if ram else "Unknown"

    cards = ""
    for m in models[:3]:
        badges = " ".join(
            f"<span style='background:#2a2a2a;border:1px solid #444;border-radius:10px;"
            f"padding:2px 8px;font-size:.8em;margin:2px;display:inline-block'>{uc}</span>"
            for uc in m["use_cases"]
        )
        cards += f"""
        <div style='border:1px solid #444;border-radius:8px;padding:12px;margin:8px 0;background:#1a1a2e'>
          <b style='font-size:1.05em'>{m['name']}</b>
          <span style='float:right;color:#aaa;font-size:.85em'>{m['size_gb']} GB · {m['speed']}</span><br>
          <p style='color:#ccc;font-size:.9em;margin:6px 0'>{m['description']}</p>
          <div style='margin:4px 0'>{badges}</div>
          <p style='color:#888;font-size:.8em'>Min RAM: {m['min_ram_gb']} GB · Languages: {', '.join(m['languages'])}</p>
          <p style='font-size:.8em;color:#aaa'>ID: <code>{m['id']}</code></p>
        </div>"""

    ram_str = f"{ram:.1f} GB" if ram else "Unknown"
    gpu_str = resources.get("gpu_info", "Unknown")
    return cards, gpu_str, ram_str


def create_ui():
    with gr.Accordion("🧙 Model Recommendations Wizard", open=not _wizard_done(), elem_id="model-wizard-accordion"):
        gr.Markdown("**What do you want to do?** Select your use cases and we'll recommend the best model.")
        shared.gradio['wizard_use_cases'] = gr.CheckboxGroup(
            choices=list(USE_CASE_LABELS.values()),
            label="Use cases",
            value=[]
        )
        with gr.Row():
            shared.gradio['wizard_run_btn'] = gr.Button("🔍 Find Models", variant="primary")
            shared.gradio['wizard_skip_btn'] = gr.Button("Skip Wizard")

        gr.Markdown("### System Resources")
        with gr.Row():
            shared.gradio['wizard_ram_info'] = gr.Textbox(label="Available RAM", interactive=False, scale=1)
            shared.gradio['wizard_gpu_info'] = gr.Textbox(label="GPU / VRAM", interactive=False, scale=1)

        gr.Markdown("### Recommended Models")
        shared.gradio['wizard_results'] = gr.HTML("<p style='color:#888'>Select use cases above and click Find Models.</p>")


def create_event_handlers():
    def _on_run(use_cases):
        label_to_key = {v: k for k, v in USE_CASE_LABELS.items()}
        keys = [label_to_key.get(uc, uc.lower()) for uc in use_cases]
        html, gpu, ram = _run_wizard(keys)
        _mark_wizard_done()
        return html, gpu, ram

    shared.gradio['wizard_run_btn'].click(
        _on_run,
        gradio('wizard_use_cases'),
        gradio('wizard_results', 'wizard_gpu_info', 'wizard_ram_info')
    )

    shared.gradio['wizard_skip_btn'].click(
        lambda: (_mark_wizard_done(), "<p style='color:#888'>Wizard skipped.</p>")[1],
        [],
        gradio('wizard_results')
    )

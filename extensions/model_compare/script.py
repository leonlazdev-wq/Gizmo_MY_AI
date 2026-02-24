params = {
    "display_name": "Model Comparison",
    "is_tab": True,
}

import html
import time
from typing import Dict, List

import gradio as gr

from modules import shared, utils
from modules.models import load_model, unload_model
from modules.text_generation import generate_reply


class ModelComparison:
    def generate_with_model(self, model_name: str, prompt: str, params: Dict) -> Dict:
        start = time.time()
        unload_model()
        shared.model, shared.tokenizer = load_model(model_name, None)
        state = dict(shared.settings)
        state.update(params)
        result = ""
        for chunk in generate_reply(prompt, state, stopping_strings=[], is_chat=False, for_ui=False):
            result = chunk
        elapsed = max(0.001, time.time() - start)
        tokens = len((result or "").split())
        return {
            "model": model_name,
            "response": result,
            "time": elapsed,
            "tokens": tokens,
            "tokens_per_sec": tokens / elapsed,
        }

    def compare_models(self, prompt: str, models: List[str], temperature: float, max_tokens: int):
        if len(models) < 2:
            return "<p>Select at least 2 models.</p>", []
        params = {"temperature": temperature, "max_new_tokens": int(max_tokens)}
        original = shared.model_name
        results = []
        try:
            for model in models:
                results.append(self.generate_with_model(model, prompt, params))
        finally:
            if original and original != 'None':
                unload_model()
                shared.model, shared.tokenizer = load_model(original, None)

        html_out = ["<div style='background:#1e1e1e;padding:20px;border-radius:10px'><h3 style='color:#4CAF50'>🔬 Model Comparison Results</h3>"]
        for r in results:
            html_out.append(
                f"<div style='margin:10px 0;border-left:4px solid #2196F3;padding-left:12px'><h4 style='color:#2196F3'>{html.escape(r['model'])}</h4>"
                f"<div style='font-size:12px;color:#aaa'>⏱️ {r['time']:.2f}s • ⚡ {r['tokens_per_sec']:.1f} tok/s</div>"
                f"<div style='margin-top:8px'>{html.escape(r['response'] or '')}</div></div>"
            )
        html_out.append("</div>")
        chart = [[r['model'], r['tokens_per_sec']] for r in results]
        return "".join(html_out), chart


def ui():
    comp = ModelComparison()
    gr.Markdown("## 🔬 Model Comparison Tool")
    with gr.Row():
        with gr.Column(scale=1):
            comparison_prompt = gr.Textbox(label="Test Prompt", lines=5)
            model_selection = gr.CheckboxGroup(choices=utils.get_available_models(), label="Select Models (2-4)")
            temp = gr.Slider(0, 1.5, 0.7, 0.05, label="Temperature")
            max_tokens = gr.Slider(64, 2048, 512, 64, label="Max Tokens")
            compare_btn = gr.Button("▶️ Run Comparison", variant="primary")
        with gr.Column(scale=3):
            comparison_output = gr.HTML(value="<p>Results will appear here...</p>")
            performance_chart = gr.BarPlot(x="model", y="tok_s", title="Tokens/Second", value=[])

    compare_btn.click(
        lambda p, m, t, mx: comp.compare_models(p, m, t, mx),
        [comparison_prompt, model_selection, temp, max_tokens],
        [comparison_output, performance_chart],
    )

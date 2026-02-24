"""Workflows tab UI with lightweight pipeline canvas."""

from __future__ import annotations

import json

import gradio as gr

from modules import shared
from modules.feature_workflows import ensure_demo_workflow, run_workflow, run_workflow_path, save_workflow
from modules.utils import gradio


def _save(name: str, workflow_json: str) -> str:
    payload = json.loads(workflow_json or "{}")
    payload["name"] = name or payload.get("name", "Untitled")
    wf_id = save_workflow("local_user", payload)
    return f"✅ Saved workflow {wf_id}"


def _run(name: str, workflow_json: str, input_text: str) -> str:
    payload = json.loads(workflow_json or "{}")
    payload["name"] = name or payload.get("name", "Untitled")
    wf_id = save_workflow("local_user", payload)
    result = run_workflow(wf_id, input_text)
    return result["answer"]


def create_ui() -> None:
    """Render Workflows tab."""
    with gr.Tab("Workflows", elem_id="workflows-tab"):
        gr.Markdown("## 🔧 Visual Workflow Builder")
        # Visual mock: [Palette] -----> [Canvas: Planner -> Search -> Writer]
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("**Node Palette**")
                gr.Markdown("- 🧭 Planner  \n- 🔎 WebSearch  \n- 📚 RAG  \n- 💻 PythonRunner  \n- ✍️ Writer  \n- 🛡️ Critic")

            with gr.Column(scale=3):
                shared.gradio["workflow_canvas"] = gr.HTML(
                    """
                    <div id='workflow-canvas' aria-label='Workflow canvas'>
                      <div style='padding:10px;font-size:12px;color:#4b5563'>
                        Drag nodes here (mock canvas). Example: Planner → WebSearch → Writer.
                      </div>
                    </div>
                    """,
                    elem_id="workflow-canvas",
                )
                shared.gradio["workflow_name"] = gr.Textbox(label="Workflow Name", value="Build draft", elem_id="workflow-name")
                shared.gradio["workflow_json"] = gr.Textbox(
                    label="Workflow JSON",
                    lines=10,
                    value=json.dumps(
                        {
                            "name": "Build draft",
                            "nodes": [
                                {"id": "n1", "type": "Planner", "params": {}},
                                {"id": "n2", "type": "WebSearch", "params": {}},
                                {"id": "n3", "type": "Writer", "params": {}},
                            ],
                            "edges": [["n1", "n2"], ["n2", "n3"]],
                        },
                        indent=2,
                    ),
                )
                shared.gradio["workflow_input"] = gr.Textbox(label="Input", value="Explain photosynthesis for grade 6")
                with gr.Row():
                    shared.gradio["workflow_save_btn"] = gr.Button("Save workflow", elem_id="wf-save-btn")
                    shared.gradio["workflow_run_btn"] = gr.Button("Run workflow", variant="primary", elem_id="wf-run-btn")
                    shared.gradio["workflow_export_btn"] = gr.Button("Export JSON", elem_id="wf-export-btn")
                    shared.gradio["workflow_demo_btn"] = gr.Button("Run demo workflow", elem_id="wf-demo-btn")
                shared.gradio["workflow_status"] = gr.Textbox(label="Status", interactive=False)
                shared.gradio["workflow_output"] = gr.Textbox(label="Run output", lines=8)


def create_event_handlers() -> None:
    """Wire workflow actions."""
    shared.gradio["workflow_save_btn"].click(_save, gradio("workflow_name", "workflow_json"), gradio("workflow_status"), show_progress=False)
    shared.gradio["workflow_run_btn"].click(
        _run,
        gradio("workflow_name", "workflow_json", "workflow_input"),
        gradio("workflow_output"),
        show_progress=False,
    )
    shared.gradio["workflow_export_btn"].click(
        lambda content: content,
        gradio("workflow_json"),
        gradio("workflow_output"),
        show_progress=False,
    )
    shared.gradio["workflow_demo_btn"].click(
        lambda text: run_workflow_path(ensure_demo_workflow(), text).get('answer', ''),
        gradio("workflow_input"),
        gradio("workflow_output"),
        show_progress=False,
    )

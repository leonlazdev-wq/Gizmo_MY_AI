"""Workflows tab UI."""

from __future__ import annotations

import json

import gradio as gr

from modules import shared
from modules.audit import record_step
from modules.auth import enforce_permission
from modules.feature_workflows import run_workflow, save_workflow
from modules.utils import gradio


CANVAS_HTML = """
<!-- Visual mock: dashed canvas with draggable nodes -->
<div id='workflow-canvas' style='min-height:320px;background:#f6f7fb;border:1px dashed #c7c9d3;border-radius:12px;padding:12px;' aria-label='Workflow canvas'>
  <div style='font-size:13px;color:#6b7280;'>Drag nodes concept (lightweight mock canvas): Planner, WebSearch, RAG, PythonRunner, Writer, Critic.</div>
</div>
"""


def create_ui() -> None:
    with gr.Tab("Workflows", elem_id="workflows-tab"):
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("**Node Palette**")
                gr.Markdown("- 🧭 Planner  \n- 🔎 WebSearch  \n- 📚 RAG  \n- 🖥️ PythonRunner  \n- ✍️ Writer  \n- 🛡️ Critic")
            with gr.Column(scale=3):
                shared.gradio["workflow_canvas"] = gr.HTML(CANVAS_HTML, elem_id="workflow-canvas-html")
                shared.gradio["workflow_json"] = gr.Textbox(
                    label="Workflow JSON",
                    lines=8,
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
                shared.gradio["workflow_name"] = gr.Textbox(label="Workflow Name", value="Build draft")
                with gr.Row():
                    shared.gradio["workflow_save_btn"] = gr.Button("Save workflow", elem_id="save-workflow-btn")
                    shared.gradio["workflow_run_btn"] = gr.Button("Run workflow", elem_id="run-workflow-btn")
                    shared.gradio["workflow_export_btn"] = gr.Button("Export JSON", elem_id="export-workflow-btn")
                shared.gradio["workflow_input"] = gr.Textbox(label="Run input", lines=3)
                shared.gradio["workflow_status"] = gr.Textbox(label="Workflow status", interactive=False)
                shared.gradio["workflow_output"] = gr.Textbox(label="Workflow output", lines=8)


def _save_workflow(wf_name: str, wf_json: str) -> tuple[str, str]:
    if not shared.settings.get("enable_workflows", False):
        return "❌ Workflows integration is disabled in Integrations.", ""
    data = json.loads(wf_json)
    data["name"] = wf_name or data.get("name", "Untitled")
    wid = save_workflow("local-user", data)
    record_step("default", wid, {"event": "save_workflow", "name": wf_name})
    return f"✅ Saved workflow {wid}", wid


def _run_workflow(workflow_id: str, input_text: str) -> tuple[str, str]:
    if not shared.settings.get("enable_workflows", False):
        return "❌ Workflows integration is disabled in Integrations.", ""
    if not enforce_permission("local-user", "default", "run"):
        return "❌ Permission denied: can_run=False", ""
    result = run_workflow(workflow_id, input_text)
    record_step("default", workflow_id, {"event": "run_workflow", "input": input_text[:120]})
    return "✅ Workflow executed", result.get("final_answer", json.dumps(result, ensure_ascii=False, indent=2)[:2000])


def create_event_handlers() -> None:
    shared.gradio["workflow_save_btn"].click(
        _save_workflow,
        gradio("workflow_name", "workflow_json"),
        gradio("workflow_status", "workflow_output"),
        show_progress=False,
    )

    shared.gradio["workflow_run_btn"].click(
        _run_workflow,
        gradio("workflow_output", "workflow_input"),
        gradio("workflow_status", "workflow_output"),
        show_progress=False,
    )

    shared.gradio["workflow_export_btn"].click(
        lambda wf_json: ("✅ Export ready", wf_json),
        gradio("workflow_json"),
        gradio("workflow_status", "workflow_output"),
        show_progress=False,
    )

params = {"display_name": "Workflow Builder", "is_tab": True}

import json
from datetime import datetime
from pathlib import Path

import gradio as gr


class WorkflowBuilder:
    def __init__(self):
        self.dir = Path("user_data/workflows")
        self.dir.mkdir(parents=True, exist_ok=True)

    def create_workflow(self, name: str, description: str, spec_json: str) -> str:
        if not name.strip():
            return "❌ Workflow name is required"
        try:
            spec = json.loads(spec_json or "{}")
        except json.JSONDecodeError as exc:
            return f"❌ Invalid JSON: {exc}"
        wid = datetime.now().strftime("%Y%m%d_%H%M%S")
        payload = {"id": wid, "name": name.strip(), "description": description.strip(), "spec": spec, "created_at": datetime.now().isoformat()}
        (self.dir / f"{wid}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return f"✅ Saved workflow {wid}"

    def list_workflows(self) -> str:
        cards = []
        for p in sorted(self.dir.glob("*.json"), reverse=True):
            data = json.loads(p.read_text(encoding="utf-8"))
            cards.append(f"<div style='background:#2a2a2a;padding:10px;border-radius:8px;margin:8px 0'><b>{data.get('name')}</b><br/><small>{data.get('description')}</small><br/><code>{data.get('id')}</code></div>")
        return "".join(cards) if cards else "<p>No workflows saved yet.</p>"

    def run_workflow(self, workflow_id: str, input_json: str) -> str:
        p = self.dir / f"{workflow_id.strip()}.json"
        if not p.exists():
            return "❌ Workflow not found"
        try:
            input_data = json.loads(input_json or "{}")
        except json.JSONDecodeError as exc:
            return f"❌ Invalid input JSON: {exc}"
        wf = json.loads(p.read_text(encoding="utf-8"))
        out = {"workflow": wf.get("name"), "input": input_data, "status": "completed", "executed_at": datetime.now().isoformat()}
        out_path = self.dir / f"run_{workflow_id}_{datetime.now().strftime('%H%M%S')}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        return json.dumps(out, indent=2)


def ui():
    wb = WorkflowBuilder()
    gr.Markdown("# 🔧 Workflow Builder")
    with gr.Tabs():
        with gr.Tab("🎨 Build"):
            name = gr.Textbox(label="Workflow Name")
            description = gr.Textbox(label="Description")
            spec = gr.Textbox(label="Workflow JSON Spec", lines=8, value='{"nodes": [], "connections": []}')
            save_btn = gr.Button("💾 Save Workflow", variant="primary")
            save_status = gr.Textbox(label="Status", interactive=False)
            save_btn.click(wb.create_workflow, [name, description, spec], save_status)
        with gr.Tab("📂 My Workflows"):
            refresh_btn = gr.Button("🔄 Refresh")
            workflows_html = gr.HTML(value=wb.list_workflows())
            workflow_id = gr.Textbox(label="Workflow ID")
            workflow_input = gr.Textbox(label="Input JSON", lines=4, value='{}')
            run_btn = gr.Button("▶️ Execute Workflow", variant="primary")
            output = gr.Textbox(label="Output", lines=10)
            refresh_btn.click(wb.list_workflows, None, workflows_html)
            run_btn.click(wb.run_workflow, [workflow_id, workflow_input], output)

"""Visual workflow model and execution helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class Node:
    """A workflow node."""

    id: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """A directed edge between nodes."""

    source: str
    target: str


@dataclass
class Workflow:
    """Workflow definition saved to disk."""

    id: str
    name: str
    owner: str
    nodes: list[Node]
    edges: list[Edge]
    created_at: str


def _workflow_dir() -> Path:
    path = Path("workflows")
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_workflow(user_id: str, workflow_json: dict[str, Any]) -> str:
    """Save a workflow schema to disk and return the workflow id."""
    wf_id = workflow_json.get("id") or str(uuid4())
    payload = {
        "id": wf_id,
        "name": workflow_json.get("name", "Untitled workflow"),
        "owner": user_id,
        "nodes": workflow_json.get("nodes", []),
        "edges": workflow_json.get("edges", []),
        "created_at": workflow_json.get("created_at") or (datetime.utcnow().isoformat() + "Z"),
    }
    (_workflow_dir() / f"{wf_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return wf_id


def load_workflow(workflow_id: str) -> dict[str, Any]:
    """Load workflow schema by id."""
    path = _workflow_dir() / f"{workflow_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _node_output(node: dict[str, Any], context: dict[str, Any]) -> str:
    ntype = node.get("type", "")
    text = context.get("text", "")
    if ntype == "Planner":
        return f"Plan: break down '{text}' into steps."
    if ntype == "WebSearch":
        return f"Web hints for '{text}'."
    if ntype == "RAG":
        return f"RAG context for '{text}'."
    if ntype == "PythonRunner":
        return "PythonRunner executed safely."
    if ntype == "Writer":
        return f"Draft response for '{text}'."
    if ntype == "Critic":
        return "Critic approved response with revisions."
    return f"Node {ntype} executed."


def run_workflow(workflow_id: str, input_text: str, timeout_s: int = 60) -> dict[str, Any]:
    """Execute workflow in topological edge order and return composed result."""
    workflow = load_workflow(workflow_id)
    nodes_by_id = {n["id"]: n for n in workflow.get("nodes", [])}
    ordered = [src for src, _ in workflow.get("edges", [])]
    ordered += [nid for nid in nodes_by_id if nid not in ordered]
    outputs: list[str] = []
    context = {"text": input_text, "timeout_s": timeout_s}
    for node_id in ordered:
        node = nodes_by_id.get(node_id)
        if not node:
            continue
        outputs.append(_node_output(node, context))
    composed = "\n".join(outputs) or f"No runnable nodes for: {input_text}"
    return {"workflow_id": workflow_id, "answer": composed, "steps": outputs}



def ensure_demo_workflow() -> str:
    """Create a default demo workflow file if it does not already exist."""
    demo_path = _workflow_dir() / "demo.json"
    if demo_path.exists():
        return str(demo_path)

    payload = {
        "id": "demo",
        "name": "Demo: Research + Compose",
        "owner": "demo_user",
        "nodes": [
            {"id": "n1", "type": "Planner", "params": {"role_prompt": "Outline approach"}},
            {"id": "n2", "type": "WebSearch", "params": {"top_k": 3}},
            {"id": "n3", "type": "Writer", "params": {"style": "clear"}},
        ],
        "edges": [["n1", "n2"], ["n2", "n3"]],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    demo_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(demo_path)


def run_workflow_path(path: str, input_text: str, session_id: str = "default_session") -> dict[str, Any]:
    """Run workflow from explicit path and include session id in result."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    wf_id = data.get("id") or save_workflow(session_id, data)
    result = run_workflow(wf_id, input_text)
    result["session_id"] = session_id
    return result

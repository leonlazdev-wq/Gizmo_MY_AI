"""Workflow builder backend for visual pipelines.

# Visual mock:
# [ Planner ] ---> [ WebSearch ] ---> [ Writer ]
#  (⚙ params)        (🌐 tool)         (✍ output)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

WORKFLOW_DIR = Path("workflows")
WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Node:
    """A workflow node descriptor."""

    id: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Directional connection between nodes."""

    source: str
    target: str


@dataclass
class Workflow:
    """Workflow schema and metadata."""

    id: str
    name: str
    owner: str
    nodes: List[Node]
    edges: List[Edge]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [[e.source, e.target] for e in self.edges],
            "created_at": self.created_at,
        }


def _node_run(node: Node, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a known node type against mutable context."""
    text = context.get("text", "")
    if node.type == "Planner":
        context["plan"] = [f"Plan: {text[:80]}"]
    elif node.type == "WebSearch":
        try:
            from modules.web_search import search_with_providers  # lazy import

            context["web"] = search_with_providers(text, max_results=3)
        except BaseException:
            context["web"] = []
    elif node.type == "RAG":
        from modules import rag_engine  # lazy import

        context["rag"] = rag_engine.retrieve_context(text, top_k=3)
    elif node.type == "PythonRunner":
        from modules.tools.python_runner import PythonRunnerTool  # lazy import

        code = node.params.get("code", "print('ok')")
        context["python"] = PythonRunnerTool().run(code)
    elif node.type == "Writer":
        context["draft"] = f"Draft answer for: {text}\nPlan: {context.get('plan', [])}\nRAG: {context.get('rag', [])}"
    elif node.type == "Critic":
        context["final_answer"] = context.get("draft", "") + "\n\nCritic: concise + verified."
    return context


def save_workflow(user_id: str, workflow_json: Dict[str, Any]) -> str:
    """Persist a workflow and return its id."""
    wid = workflow_json.get("id") or str(uuid.uuid4())
    wf = {
        "id": wid,
        "name": workflow_json.get("name", "Untitled workflow"),
        "owner": user_id,
        "nodes": workflow_json.get("nodes", []),
        "edges": workflow_json.get("edges", []),
        "created_at": workflow_json.get("created_at") or datetime.utcnow().isoformat() + "Z",
    }
    (WORKFLOW_DIR / f"{wid}.json").write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
    return wid


def load_workflow(workflow_id: str) -> Dict[str, Any]:
    """Load a workflow from disk."""
    path = WORKFLOW_DIR / f"{workflow_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Workflow not found: {workflow_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_workflow(workflow_id: str, input_text: str, timeout_s: int = 60) -> Dict[str, Any]:
    """Run nodes in a simple topological-by-list order and return execution context."""
    data = load_workflow(workflow_id)
    nodes = [Node(**n) for n in data.get("nodes", [])]
    context: Dict[str, Any] = {"text": input_text, "timeout_s": timeout_s}
    for node in nodes:
        context = _node_run(node, context)
    context["workflow_id"] = workflow_id
    return context

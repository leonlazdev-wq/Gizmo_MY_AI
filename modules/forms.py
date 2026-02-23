"""Conversational form templates and storage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

FORM_DIR = Path("forms")
FORM_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FormTemplate:
    id: str
    name: str
    steps: List[Dict[str, Any]] = field(default_factory=list)


DEFAULT_TEMPLATES = {
    "bug_report": FormTemplate(
        id="bug_report",
        name="Bug Report",
        steps=[
            {"field": "title", "type": "text", "required": True},
            {"field": "email", "type": "email", "required": True},
            {"field": "date", "type": "date", "required": True},
            {"field": "severity", "type": "choice", "choices": ["low", "medium", "high"]},
            {"field": "details", "type": "text", "required": True},
        ],
    )
}


def validate_field(ftype: str, value: str) -> bool:
    if ftype == "email":
        return "@" in value and "." in value.split("@")[-1]
    if ftype == "date":
        return len(value.split("-")) == 3
    return bool(str(value).strip())


def run_form(session_id: str, template_id: str, values: Dict[str, Any]) -> str:
    template = DEFAULT_TEMPLATES[template_id]
    for step in template.steps:
        field = step["field"]
        if step.get("required") and not validate_field(step["type"], str(values.get(field, ""))):
            raise ValueError(f"Invalid field: {field}")
    out = {
        "session_id": session_id,
        "template_id": template_id,
        "values": values,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    out_path = FORM_DIR / f"{template_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)

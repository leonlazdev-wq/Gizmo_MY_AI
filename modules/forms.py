"""Conversational forms with validation and persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FormTemplate:
    """Form template schema."""

    template_id: str
    title: str
    steps: list[dict[str, Any]]


DEFAULT_TEMPLATES = {
    "bug_report": FormTemplate(
        template_id="bug_report",
        title="Bug Report",
        steps=[
            {"name": "title", "type": "text", "required": True},
            {"name": "email", "type": "email", "required": True},
            {"name": "date", "type": "date", "required": True},
            {"name": "severity", "type": "choice", "choices": ["low", "medium", "high"]},
        ],
    )
}


def _forms_dir() -> Path:
    path = Path("forms")
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_field(field_type: str, value: str) -> bool:
    """Validate a typed field value."""
    if field_type == "email":
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value or ""))
    if field_type == "date":
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value or ""))
    return bool((value or "").strip())


def run_form(session_id: str, template_id: str, values: dict[str, str]) -> dict[str, Any]:
    """Validate and persist form submission."""
    template = DEFAULT_TEMPLATES[template_id]
    errors: list[str] = []
    for step in template.steps:
        name = step["name"]
        v = values.get(name, "")
        if step.get("required") and not validate_field(step["type"], v):
            errors.append(name)

    if errors:
        return {"status": "error", "errors": errors}

    payload = {
        "session_id": session_id,
        "template_id": template_id,
        "values": values,
        "saved_at": datetime.utcnow().isoformat() + "Z",
    }
    out = _forms_dir() / f"{session_id}_{template_id}_{int(datetime.utcnow().timestamp())}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(out)}

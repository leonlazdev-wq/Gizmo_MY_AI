"""Assignment Tracker backend for Gizmo."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

_ASSIGNMENTS_FILE = os.path.join("user_data", "assignments.json")

PRIORITY_OPTIONS = ["low", "medium", "high", "urgent"]
STATUS_OPTIONS = ["not started", "in progress", "completed"]

_PRIORITY_COLORS = {
    "low": "#d1fae5",
    "medium": "#fef3c7",
    "high": "#fed7aa",
    "urgent": "#fee2e2",
}
_STATUS_COLORS = {
    "not started": "#f3f4f6",
    "in progress": "#dbeafe",
    "completed": "#d1fae5",
}


def _ensure_dirs() -> None:
    os.makedirs("user_data", exist_ok=True)


def _load_assignments() -> List[Dict]:
    """Load assignments from file."""
    _ensure_dirs()
    if not os.path.isfile(_ASSIGNMENTS_FILE):
        return []
    try:
        with open(_ASSIGNMENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_assignments(assignments: List[Dict]) -> None:
    """Save assignments to file."""
    _ensure_dirs()
    try:
        with open(_ASSIGNMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(assignments, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _call_ai(prompt: str):
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = 512
        from modules.text_generation import generate_reply
        output = ""
        for chunk in generate_reply(prompt, state, stopping_strings=[], is_chat=False):
            if isinstance(chunk, str):
                output = chunk
            elif isinstance(chunk, (list, tuple)) and len(chunk) > 0:
                output = chunk[0] if isinstance(chunk[0], str) else str(chunk[0])
        return output.strip(), None
    except Exception as exc:
        return None, f"❌ AI error: {exc}"


def estimate_time(name: str, description: str, course: str = "") -> Tuple[str, str]:
    """Use AI to estimate time needed for an assignment."""
    if not name:
        return "❌ Please provide an assignment name.", ""

    prompt = (
        f"Estimate the time required to complete the following assignment. "
        f"Provide a realistic estimate in hours and explain briefly.\n\n"
        f"Assignment: {name}\n"
        f"Course: {course or 'N/A'}\n"
        f"Description: {description or 'N/A'}\n\n"
        "Format: 'Estimated time: X hours. Reason: ...'"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Time estimated.", output


def add_assignment(
    name: str,
    course: str,
    due_date: str,
    priority: str,
    description: str,
    status: str = "not started",
    estimated_time: str = "",
) -> str:
    """Add a new assignment."""
    if not name:
        return "❌ Assignment name is required."

    assignments = _load_assignments()
    assignment = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "name": name,
        "course": course,
        "due_date": due_date,
        "priority": priority,
        "description": description,
        "status": status,
        "estimated_time": estimated_time,
        "created_at": datetime.now().isoformat(),
    }
    assignments.append(assignment)
    _save_assignments(assignments)
    return f"✅ Assignment '{name}' added."


def update_assignment_status(assignment_id: str, new_status: str) -> str:
    """Update the status of an assignment by ID."""
    assignments = _load_assignments()
    for a in assignments:
        if a.get("id") == assignment_id:
            a["status"] = new_status
            _save_assignments(assignments)
            return f"✅ Updated status to '{new_status}'."
    return f"❌ Assignment '{assignment_id}' not found."


def delete_assignment(assignment_id: str) -> str:
    """Delete an assignment by ID."""
    assignments = _load_assignments()
    original_count = len(assignments)
    assignments = [a for a in assignments if a.get("id") != assignment_id]
    if len(assignments) == original_count:
        return f"❌ Assignment '{assignment_id}' not found."
    _save_assignments(assignments)
    return "✅ Assignment deleted."


def get_assignments(
    filter_course: str = "All",
    filter_priority: str = "All",
    filter_status: str = "All",
) -> List[Dict]:
    """Return assignments filtered by course, priority, and status."""
    assignments = _load_assignments()
    if filter_course != "All":
        assignments = [a for a in assignments if a.get("course", "") == filter_course]
    if filter_priority != "All":
        assignments = [a for a in assignments if a.get("priority", "") == filter_priority]
    if filter_status != "All":
        assignments = [a for a in assignments if a.get("status", "") == filter_status]

    # Sort by due date, then priority
    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    assignments.sort(key=lambda a: (
        a.get("due_date", "9999-99-99"),
        priority_order.get(a.get("priority", "low"), 4),
    ))
    return assignments


def get_stats() -> Dict:
    """Return assignment statistics."""
    assignments = _load_assignments()
    today = date.today().strftime("%Y-%m-%d")

    completed = [a for a in assignments if a.get("status") == "completed"]
    in_progress = [a for a in assignments if a.get("status") == "in progress"]
    not_started = [a for a in assignments if a.get("status") == "not started"]
    overdue = [
        a for a in assignments
        if a.get("status") != "completed" and a.get("due_date", "9999-99-99") < today
    ]
    upcoming = [
        a for a in assignments
        if a.get("status") != "completed" and a.get("due_date", "9999-99-99") >= today
    ]

    return {
        "total": len(assignments),
        "completed": len(completed),
        "in_progress": len(in_progress),
        "not_started": len(not_started),
        "overdue": len(overdue),
        "upcoming": len(upcoming),
    }


def get_courses() -> List[str]:
    """Return a list of unique course names from saved assignments."""
    assignments = _load_assignments()
    courses = sorted({a.get("course", "") for a in assignments if a.get("course", "")})
    return courses


def render_assignments_html(assignments: List[Dict]) -> str:
    """Render assignments as an HTML table with color coding."""
    import html as html_lib

    today = date.today().strftime("%Y-%m-%d")

    if not assignments:
        return "<div style='color:#888;padding:16px'>No assignments to display.</div>"

    rows = ""
    for a in assignments:
        pc = _PRIORITY_COLORS.get(a.get("priority", "low"), "#fff")
        sc = _STATUS_COLORS.get(a.get("status", "not started"), "#fff")
        due = a.get("due_date", "")
        overdue_badge = ""
        if due and due < today and a.get("status") != "completed":
            overdue_badge = " <span style='background:#ef4444;color:#fff;padding:1px 6px;border-radius:8px;font-size:0.75em'>OVERDUE</span>"

        rows += (
            f"<tr style='border-bottom:1px solid #eee'>"
            f"<td style='padding:8px;font-weight:bold'>{html_lib.escape(a.get('name',''))}</td>"
            f"<td style='padding:8px'>{html_lib.escape(a.get('course',''))}</td>"
            f"<td style='padding:8px'>{html_lib.escape(due)}{overdue_badge}</td>"
            f"<td style='padding:8px'><span style='background:{pc};padding:2px 8px;border-radius:12px;font-size:0.8em'>"
            f"{html_lib.escape(a.get('priority',''))}</span></td>"
            f"<td style='padding:8px'><span style='background:{sc};padding:2px 8px;border-radius:12px;font-size:0.8em'>"
            f"{html_lib.escape(a.get('status',''))}</span></td>"
            f"<td style='padding:8px;font-size:0.8em;color:#666'>{html_lib.escape(a.get('estimated_time',''))}</td>"
            f"<td style='padding:8px;font-size:0.75em;color:#888'>{html_lib.escape(a.get('id',''))}</td>"
            f"</tr>"
        )

    return f"""
<div style="font-family:'Segoe UI',Arial,sans-serif;overflow-x:auto">
  <table style="width:100%;border-collapse:collapse">
    <thead>
      <tr style="background:#f3f4f6;font-size:0.85em">
        <th style="text-align:left;padding:8px">Assignment</th>
        <th style="text-align:left;padding:8px">Course</th>
        <th style="text-align:left;padding:8px">Due Date</th>
        <th style="text-align:left;padding:8px">Priority</th>
        <th style="text-align:left;padding:8px">Status</th>
        <th style="text-align:left;padding:8px">Est. Time</th>
        <th style="text-align:left;padding:8px">ID</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <div style="margin-top:8px;color:#888;font-size:0.8em">{len(assignments)} assignment(s)</div>
</div>"""


def render_stats_html(stats: Optional[Dict] = None) -> str:
    """Render stats summary as HTML."""
    if stats is None:
        stats = get_stats()

    return f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;font-family:'Segoe UI',Arial,sans-serif;padding:8px">
  <div style="background:#d1fae5;border-radius:8px;padding:10px;text-align:center">
    <div style="font-size:1.5em;font-weight:bold">{stats['completed']}</div>
    <div style="font-size:0.8em;color:#555">Completed</div>
  </div>
  <div style="background:#dbeafe;border-radius:8px;padding:10px;text-align:center">
    <div style="font-size:1.5em;font-weight:bold">{stats['in_progress']}</div>
    <div style="font-size:0.8em;color:#555">In Progress</div>
  </div>
  <div style="background:#fee2e2;border-radius:8px;padding:10px;text-align:center">
    <div style="font-size:1.5em;font-weight:bold">{stats['overdue']}</div>
    <div style="font-size:0.8em;color:#555">Overdue ⚠️</div>
  </div>
</div>"""

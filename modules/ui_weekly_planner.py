"""Gradio UI tab for the Smart Weekly Planner."""

from __future__ import annotations

from datetime import date

import gradio as gr

from modules import shared
from modules.weekly_planner import (
    auto_scan,
    generate_schedule,
    list_schedules,
    load_schedule,
    mark_completed,
    reschedule_skipped,
    sync_to_google_calendar,
)

TUTORIAL_URL = (
    "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab"
    "/blob/main/README.md#smart-weekly-planner"
)

# Module-level state
_current_schedule_doc: dict = {}
_current_deadlines: list = []
_scan_data: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _schedule_to_rows(schedule_doc: dict) -> list:
    """Convert schedule entries to a list of rows for the Dataframe."""
    rows = []
    for entry in schedule_doc.get("entries", []):
        rows.append([
            entry.get("date", ""),
            entry.get("day", ""),
            entry.get("time", ""),
            entry.get("subject", ""),
            entry.get("activity", ""),
            f"{entry.get('duration_minutes', 0)} min",
            entry.get("type", "study").capitalize(),
            "✅" if entry.get("completed") else "⬜",
        ])
    return rows


def _deadlines_display() -> str:
    if not _current_deadlines:
        return ""
    lines = [
        f"• {d.get('subject','?')} — {d.get('type','deadline')} on {d.get('date','?')}"
        for d in _current_deadlines
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _auto_scan_fn():
    global _scan_data
    _scan_data = auto_scan()
    decks = _scan_data.get("flashcard_decks", [])
    quizzes = _scan_data.get("quiz_results", [])
    plans = _scan_data.get("study_plans", [])
    summary = (
        f"**🔍 Auto-Scan Results**\n\n"
        f"- 🃏 Flashcard decks found: **{len(decks)}** "
        f"({', '.join(d['deck_name'] for d in decks) or 'none'})\n"
        f"- 📝 Quiz results found: **{len(quizzes)}** "
        f"({', '.join(q['subject'] for q in quizzes) or 'none'})\n"
        f"- 📅 Existing study plans found: **{len(plans)}**\n\n"
        f"Ready to generate schedule. Click **📅 Generate Schedule** to continue."
    )
    return summary


def _add_deadline_fn(subject, dtype, ddate):
    global _current_deadlines
    if not subject or not ddate:
        return "Please enter a subject and date.", _deadlines_display()
    _current_deadlines.append({"subject": subject, "type": dtype, "date": ddate})
    return f"✅ Added: {subject} ({dtype}) on {ddate}", _deadlines_display()


def _clear_deadlines_fn():
    global _current_deadlines
    _current_deadlines = []
    return "✅ Deadlines cleared.", ""


def _generate_fn(courses_text, hours, weak_text, start_date_text):
    global _current_schedule_doc
    courses = [c.strip() for c in courses_text.split(",") if c.strip()]
    weak = [w.strip() for w in weak_text.split(",") if w.strip()]
    start = start_date_text.strip() or date.today().strftime("%Y-%m-%d")

    if not courses:
        return "❌ Please enter at least one course.", [], gr.update()

    status, doc = generate_schedule(
        courses=courses,
        deadlines=_current_deadlines,
        hours_per_day=float(hours),
        weak_subjects=weak,
        scan_data=_scan_data,
        start_date=start,
    )
    _current_schedule_doc = doc
    rows = _schedule_to_rows(doc)
    schedules = list_schedules()
    return status, rows, gr.update(choices=schedules)


def _reschedule_fn():
    global _current_schedule_doc
    if not _current_schedule_doc:
        return "❌ No schedule loaded.", []
    status, doc = reschedule_skipped(_current_schedule_doc)
    _current_schedule_doc = doc
    return status, _schedule_to_rows(doc)


def _mark_done_fn(date_str, subject):
    global _current_schedule_doc
    if not _current_schedule_doc:
        return "❌ No schedule loaded.", []
    if not date_str or not subject:
        return "Please provide a date and subject.", []
    status, doc = mark_completed(_current_schedule_doc, date_str.strip(), subject.strip())
    _current_schedule_doc = doc
    return status, _schedule_to_rows(doc)


def _sync_gcal_fn():
    if not _current_schedule_doc:
        return "❌ No schedule loaded."
    return sync_to_google_calendar(_current_schedule_doc)


def _load_schedule_fn(schedule_id):
    global _current_schedule_doc
    if not schedule_id:
        return "No schedule selected.", []
    msg, doc = load_schedule(schedule_id.strip())
    if doc:
        _current_schedule_doc = doc
    return msg, _schedule_to_rows(doc)


def _refresh_schedules_fn():
    return gr.update(choices=list_schedules())


# ---------------------------------------------------------------------------
# UI definition
# ---------------------------------------------------------------------------

def create_ui():
    with gr.Tab("🗓️ Weekly Planner", elem_id="weekly-planner-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: Smart Weekly Planner</a>"
            f"</div>"
        )

        # --- Inputs ---
        with gr.Accordion("📋 Planner Inputs", open=True):
            with gr.Row():
                shared.gradio['wp_courses'] = gr.Textbox(
                    label="Courses / Subjects (comma-separated)",
                    placeholder="Math, Physics, History",
                    scale=3,
                )
                shared.gradio['wp_hours'] = gr.Slider(
                    minimum=1, maximum=12, value=4, step=0.5,
                    label="Study hours / day",
                    scale=1,
                )
            shared.gradio['wp_weak_subjects'] = gr.Textbox(
                label="Weak subjects to prioritize (comma-separated)",
                placeholder="Math, Chemistry",
            )
            with gr.Row():
                shared.gradio['wp_start_date'] = gr.Textbox(
                    label="Start date (YYYY-MM-DD, leave blank for today)",
                    placeholder=date.today().strftime("%Y-%m-%d"),
                    scale=2,
                )

        # --- Deadlines ---
        with gr.Accordion("📌 Exam Dates & Deadlines", open=False):
            with gr.Row():
                shared.gradio['wp_dl_subject'] = gr.Textbox(label="Subject", scale=2)
                shared.gradio['wp_dl_type'] = gr.Dropdown(
                    label="Type",
                    choices=["Exam", "Assignment", "Quiz", "Project"],
                    value="Exam",
                    scale=1,
                )
                shared.gradio['wp_dl_date'] = gr.Textbox(
                    label="Date (YYYY-MM-DD)", placeholder="2025-06-15", scale=2
                )
                shared.gradio['wp_dl_add_btn'] = gr.Button("➕ Add", scale=1)
            shared.gradio['wp_dl_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['wp_dl_display'] = gr.Textbox(
                label="Added deadlines", lines=4, interactive=False
            )
            shared.gradio['wp_dl_clear_btn'] = gr.Button("🗑️ Clear Deadlines", size="sm")

        # --- Action buttons ---
        with gr.Row():
            shared.gradio['wp_scan_btn'] = gr.Button(
                "🔍 Auto-Scan & Build Schedule", variant="secondary", scale=1
            )
            shared.gradio['wp_generate_btn'] = gr.Button(
                "📅 Generate Schedule", variant="primary", scale=1
            )

        shared.gradio['wp_status'] = gr.Markdown("")

        # --- Schedule display ---
        with gr.Accordion("📊 Weekly Schedule", open=True):
            shared.gradio['wp_schedule_table'] = gr.Dataframe(
                headers=["Date", "Day", "Time", "Subject", "Activity", "Duration", "Type", "Done"],
                label="Schedule",
                interactive=False,
                wrap=True,
            )

        # --- Actions on loaded schedule ---
        with gr.Accordion("⚙️ Schedule Actions", open=False):
            with gr.Row():
                shared.gradio['wp_reschedule_btn'] = gr.Button("🔄 Reschedule Skipped", scale=1)
                shared.gradio['wp_sync_gcal_btn'] = gr.Button(
                    "📤 Sync to Google Calendar", scale=1
                )
            gr.Markdown("**Mark session as completed:**")
            with gr.Row():
                shared.gradio['wp_done_date'] = gr.Textbox(
                    label="Date (YYYY-MM-DD)", scale=2
                )
                shared.gradio['wp_done_subject'] = gr.Textbox(label="Subject", scale=2)
                shared.gradio['wp_done_btn'] = gr.Button("✅ Mark Done", scale=1)
            shared.gradio['wp_action_status'] = gr.Textbox(label="Status", interactive=False)

        # --- Load saved schedule ---
        with gr.Accordion("📂 Load Saved Schedule", open=False):
            with gr.Row():
                shared.gradio['wp_schedule_selector'] = gr.Dropdown(
                    label="Saved schedules", choices=list_schedules(), interactive=True, scale=3
                )
                shared.gradio['wp_load_btn'] = gr.Button("📂 Load", scale=1)
                shared.gradio['wp_refresh_btn'] = gr.Button("🔄", scale=1)
            shared.gradio['wp_load_status'] = gr.Textbox(label="Status", interactive=False)


def create_event_handlers():
    shared.gradio['wp_scan_btn'].click(
        _auto_scan_fn,
        inputs=[],
        outputs=[shared.gradio['wp_status']],
        show_progress=True,
    )

    shared.gradio['wp_dl_add_btn'].click(
        _add_deadline_fn,
        inputs=[
            shared.gradio['wp_dl_subject'],
            shared.gradio['wp_dl_type'],
            shared.gradio['wp_dl_date'],
        ],
        outputs=[shared.gradio['wp_dl_status'], shared.gradio['wp_dl_display']],
        show_progress=False,
    )

    shared.gradio['wp_dl_clear_btn'].click(
        _clear_deadlines_fn,
        inputs=[],
        outputs=[shared.gradio['wp_dl_status'], shared.gradio['wp_dl_display']],
        show_progress=False,
    )

    shared.gradio['wp_generate_btn'].click(
        _generate_fn,
        inputs=[
            shared.gradio['wp_courses'],
            shared.gradio['wp_hours'],
            shared.gradio['wp_weak_subjects'],
            shared.gradio['wp_start_date'],
        ],
        outputs=[
            shared.gradio['wp_status'],
            shared.gradio['wp_schedule_table'],
            shared.gradio['wp_schedule_selector'],
        ],
        show_progress=True,
    )

    shared.gradio['wp_reschedule_btn'].click(
        _reschedule_fn,
        inputs=[],
        outputs=[shared.gradio['wp_action_status'], shared.gradio['wp_schedule_table']],
        show_progress=True,
    )

    shared.gradio['wp_done_btn'].click(
        _mark_done_fn,
        inputs=[shared.gradio['wp_done_date'], shared.gradio['wp_done_subject']],
        outputs=[shared.gradio['wp_action_status'], shared.gradio['wp_schedule_table']],
        show_progress=False,
    )

    shared.gradio['wp_sync_gcal_btn'].click(
        _sync_gcal_fn,
        inputs=[],
        outputs=[shared.gradio['wp_action_status']],
        show_progress=True,
    )

    shared.gradio['wp_load_btn'].click(
        _load_schedule_fn,
        inputs=[shared.gradio['wp_schedule_selector']],
        outputs=[shared.gradio['wp_load_status'], shared.gradio['wp_schedule_table']],
        show_progress=True,
    )

    shared.gradio['wp_refresh_btn'].click(
        _refresh_schedules_fn,
        inputs=[],
        outputs=[shared.gradio['wp_schedule_selector']],
        show_progress=False,
    )

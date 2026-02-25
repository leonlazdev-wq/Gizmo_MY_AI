"""Gradio UI tab for the Assignment Tracker."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.assignment_tracker import (
    PRIORITY_OPTIONS,
    STATUS_OPTIONS,
    add_assignment,
    delete_assignment,
    estimate_time,
    get_assignments,
    get_courses,
    get_stats,
    render_assignments_html,
    render_stats_html,
    update_assignment_status,
)

_estimated_time_cache: str = ""


def _refresh_table(filter_course, filter_priority, filter_status):
    assignments = get_assignments(filter_course, filter_priority, filter_status)
    table_html = render_assignments_html(assignments)
    stats_html = render_stats_html()
    courses = ["All"] + get_courses()
    return table_html, stats_html, gr.update(choices=courses)


def _estimate_time_fn(name, description, course):
    global _estimated_time_cache
    status, result = estimate_time(name, description, course)
    _estimated_time_cache = result
    return result or status


def _add_assignment_fn(name, course, due_date, priority, description, status_val, estimated_time, filter_course, filter_priority, filter_status):
    et = estimated_time or _estimated_time_cache
    msg = add_assignment(name, course, due_date, priority, description, status_val, et)
    assignments = get_assignments(filter_course, filter_priority, filter_status)
    table_html = render_assignments_html(assignments)
    stats_html = render_stats_html()
    courses = ["All"] + get_courses()
    return msg, table_html, stats_html, gr.update(choices=courses)


def _update_status_fn(assignment_id, new_status, filter_course, filter_priority, filter_status):
    if not assignment_id:
        return "❌ Please enter an assignment ID.", render_assignments_html(get_assignments()), render_stats_html()
    msg = update_assignment_status(assignment_id, new_status)
    assignments = get_assignments(filter_course, filter_priority, filter_status)
    table_html = render_assignments_html(assignments)
    stats_html = render_stats_html()
    return msg, table_html, stats_html


def _delete_fn(assignment_id, filter_course, filter_priority, filter_status):
    if not assignment_id:
        return "❌ Please enter an assignment ID.", render_assignments_html(get_assignments()), render_stats_html()
    msg = delete_assignment(assignment_id)
    assignments = get_assignments(filter_course, filter_priority, filter_status)
    table_html = render_assignments_html(assignments)
    stats_html = render_stats_html()
    return msg, table_html, stats_html


def _sync_gcal_fn():
    try:
        from modules.google_calendar_integration import create_event
        assignments = get_assignments(filter_status="not started")
        count = 0
        for a in assignments:
            if a.get("due_date"):
                try:
                    create_event(
                        title=f"[Assignment Due] {a.get('name', '')} ({a.get('course', '')})",
                        date=a.get("due_date", ""),
                        description=a.get("description", ""),
                    )
                    count += 1
                except Exception:
                    pass
        return f"✅ Synced {count} assignment(s) to Google Calendar."
    except Exception as exc:
        return f"❌ Google Calendar error: {exc}"


def create_ui():
    with gr.Tab("🗂️ Assignments", elem_id="assignments-tab"):
        shared.gradio['at_stats_html'] = gr.HTML(
            value=render_stats_html(),
            label="Stats",
        )

        with gr.Row():
            shared.gradio['at_filter_course'] = gr.Dropdown(
                label="Filter by Course",
                choices=["All"] + get_courses(),
                value="All",
                interactive=True,
            )
            shared.gradio['at_filter_priority'] = gr.Dropdown(
                label="Filter by Priority",
                choices=["All"] + PRIORITY_OPTIONS,
                value="All",
                interactive=True,
            )
            shared.gradio['at_filter_status'] = gr.Dropdown(
                label="Filter by Status",
                choices=["All"] + STATUS_OPTIONS,
                value="All",
                interactive=True,
            )
            shared.gradio['at_refresh_btn'] = gr.Button("🔄 Refresh")

        shared.gradio['at_table_html'] = gr.HTML(
            value=render_assignments_html(get_assignments()),
            label="Assignments",
        )

        with gr.Accordion("➕ Add Assignment", open=True):
            with gr.Row():
                shared.gradio['at_name'] = gr.Textbox(
                    label="Assignment Name",
                    placeholder="e.g. Essay on World War I",
                )
                shared.gradio['at_course'] = gr.Textbox(
                    label="Course / Subject",
                    placeholder="e.g. History 101",
                )
            with gr.Row():
                shared.gradio['at_due_date'] = gr.Textbox(
                    label="Due Date (YYYY-MM-DD)",
                    placeholder="e.g. 2025-03-15",
                )
                shared.gradio['at_priority'] = gr.Dropdown(
                    label="Priority",
                    choices=PRIORITY_OPTIONS,
                    value="medium",
                )
                shared.gradio['at_status_new'] = gr.Dropdown(
                    label="Status",
                    choices=STATUS_OPTIONS,
                    value="not started",
                )
            shared.gradio['at_description'] = gr.Textbox(
                label="Description (optional)",
                lines=3,
                placeholder="Brief description of the assignment...",
            )
            shared.gradio['at_estimated_time'] = gr.Textbox(
                label="Estimated Time",
                placeholder="e.g. 3 hours (or use AI Estimate)",
                interactive=True,
            )
            with gr.Row():
                shared.gradio['at_estimate_btn'] = gr.Button("🤖 Estimate Time")
                shared.gradio['at_add_btn'] = gr.Button("➕ Add Assignment", variant="primary")
            shared.gradio['at_add_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("✏️ Update / Delete", open=False):
            shared.gradio['at_update_id'] = gr.Textbox(
                label="Assignment ID (from table)",
                placeholder="Copy the ID from the table above...",
            )
            with gr.Row():
                shared.gradio['at_update_status'] = gr.Dropdown(
                    label="New Status",
                    choices=STATUS_OPTIONS,
                    value="in progress",
                )
                shared.gradio['at_update_btn'] = gr.Button("✅ Update Status")
                shared.gradio['at_delete_btn'] = gr.Button("🗑️ Delete", variant="stop")
            shared.gradio['at_update_msg'] = gr.Textbox(label="Status", interactive=False)

        with gr.Row():
            shared.gradio['at_gcal_btn'] = gr.Button("📅 Sync to Google Calendar")
        shared.gradio['at_gcal_status'] = gr.Textbox(label="Status", interactive=False)


def create_event_handlers():
    filter_inputs = [
        shared.gradio['at_filter_course'],
        shared.gradio['at_filter_priority'],
        shared.gradio['at_filter_status'],
    ]
    table_stats_course_outputs = [
        shared.gradio['at_table_html'],
        shared.gradio['at_stats_html'],
        shared.gradio['at_filter_course'],
    ]

    shared.gradio['at_refresh_btn'].click(
        _refresh_table,
        inputs=filter_inputs,
        outputs=table_stats_course_outputs,
        show_progress=False,
    )

    for widget in filter_inputs:
        widget.change(
            _refresh_table,
            inputs=filter_inputs,
            outputs=table_stats_course_outputs,
            show_progress=False,
        )

    shared.gradio['at_estimate_btn'].click(
        _estimate_time_fn,
        inputs=[
            shared.gradio['at_name'],
            shared.gradio['at_description'],
            shared.gradio['at_course'],
        ],
        outputs=[shared.gradio['at_estimated_time']],
        show_progress=True,
    )

    shared.gradio['at_add_btn'].click(
        _add_assignment_fn,
        inputs=[
            shared.gradio['at_name'],
            shared.gradio['at_course'],
            shared.gradio['at_due_date'],
            shared.gradio['at_priority'],
            shared.gradio['at_description'],
            shared.gradio['at_status_new'],
            shared.gradio['at_estimated_time'],
            shared.gradio['at_filter_course'],
            shared.gradio['at_filter_priority'],
            shared.gradio['at_filter_status'],
        ],
        outputs=[
            shared.gradio['at_add_status'],
            shared.gradio['at_table_html'],
            shared.gradio['at_stats_html'],
            shared.gradio['at_filter_course'],
        ],
        show_progress=True,
    )

    shared.gradio['at_update_btn'].click(
        _update_status_fn,
        inputs=[
            shared.gradio['at_update_id'],
            shared.gradio['at_update_status'],
            shared.gradio['at_filter_course'],
            shared.gradio['at_filter_priority'],
            shared.gradio['at_filter_status'],
        ],
        outputs=[
            shared.gradio['at_update_msg'],
            shared.gradio['at_table_html'],
            shared.gradio['at_stats_html'],
        ],
        show_progress=True,
    )

    shared.gradio['at_delete_btn'].click(
        _delete_fn,
        inputs=[
            shared.gradio['at_update_id'],
            shared.gradio['at_filter_course'],
            shared.gradio['at_filter_priority'],
            shared.gradio['at_filter_status'],
        ],
        outputs=[
            shared.gradio['at_update_msg'],
            shared.gradio['at_table_html'],
            shared.gradio['at_stats_html'],
        ],
        show_progress=True,
    )

    shared.gradio['at_gcal_btn'].click(
        _sync_gcal_fn,
        inputs=[],
        outputs=[shared.gradio['at_gcal_status']],
        show_progress=True,
    )

"""Gradio UI tab for the Study Planner."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.study_planner import (
    add_subject,
    create_study_plan,
    export_plan_csv,
    export_plan_ical,
    get_plan_progress,
    get_today_schedule,
    get_weekly_overview,
    list_plans,
    load_plan,
    recalculate_plan,
    remove_subject,
    update_progress,
)

TUTORIAL_URL = "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#study-planner"

_current_subjects: list = []
_current_plan_id = None


def _subjects_display() -> str:
    if not _current_subjects:
        return ""
    lines = []
    for s in _current_subjects:
        name = s.get("name", str(s))
        exam = s.get("exam_date", "?")
        diff = s.get("difficulty", "?")
        conf = s.get("confidence", "?")
        lines.append(f"• {name} | Exam: {exam} | Difficulty: {diff} | Confidence: {conf}/10")
    return "\n".join(lines)


def _add_subject_fn(name, exam_date, difficulty, confidence):
    global _current_subjects
    if not name:
        return "Please enter a subject name.", _subjects_display()
    _current_subjects.append({
        "name": name,
        "exam_date": exam_date,
        "difficulty": difficulty,
        "confidence": int(confidence),
    })
    return f"✅ Added '{name}'", _subjects_display()


def _clear_subjects():
    global _current_subjects
    _current_subjects = []
    return "✅ All subjects cleared.", ""


def _generate_plan(available_hours, start_date):
    global _current_plan_id
    if not _current_subjects:
        return "No subjects added yet.", "", gr.update()
    msg, plan_data = create_study_plan(
        _current_subjects,
        float(available_hours),
        start_date or None,
    )
    if isinstance(plan_data, dict):
        _current_plan_id = plan_data.get("plan_id")
        lines = []
        for k, v in plan_data.items():
            if k != "plan_id":
                lines.append(f"**{k}:** {v}")
        plan_md = "\n\n".join(lines)
    else:
        plan_md = str(plan_data) if plan_data else ""
    plans = list_plans()
    plan_labels = [f"{p.get('name', p.get('plan_id', p))}" for p in plans] if plans else []
    return msg, plan_md, gr.update(choices=plan_labels)


def _get_today(plan_id):
    pid = _current_plan_id if not plan_id else plan_id
    if not pid:
        return "No plan loaded.", ""
    msg, schedule = get_today_schedule(pid)
    if isinstance(schedule, list):
        lines = [f"• {item}" if isinstance(item, str) else f"• {item}" for item in schedule]
        return msg, "\n".join(lines)
    return msg, str(schedule) if schedule else ""


def _get_week(plan_id):
    pid = _current_plan_id if not plan_id else plan_id
    if not pid:
        return "No plan loaded.", ""
    msg, overview = get_weekly_overview(pid)
    if isinstance(overview, list):
        header = "| Day | Subject | Duration | Topic |\n|-----|---------|----------|-------|"
        rows = [
            f"| {row.get('day','?')} | {row.get('subject','?')} | {row.get('duration','?')} | {row.get('topic','?')} |"
            for row in overview
        ]
        return msg, header + "\n" + "\n".join(rows)
    return msg, str(overview) if overview else ""


def _get_progress(plan_id):
    pid = _current_plan_id if not plan_id else plan_id
    if not pid:
        return "No plan loaded.", ""
    msg, progress = get_plan_progress(pid)
    if isinstance(progress, dict):
        lines = [f"**{k}:** {v}" for k, v in progress.items()]
        return msg, "\n\n".join(lines)
    return msg, str(progress) if progress else ""


def _export_csv_fn(plan_id):
    pid = _current_plan_id if not plan_id else plan_id
    if not pid:
        return "No plan loaded.", gr.update(visible=False)
    path = "/tmp/study_plan.csv"
    msg = export_plan_csv(pid, path)
    return msg, gr.update(value=path, visible=True)


def _export_ical_fn(plan_id):
    pid = _current_plan_id if not plan_id else plan_id
    if not pid:
        return "No plan loaded.", gr.update(visible=False)
    path = "/tmp/study_plan.ics"
    msg = export_plan_ical(pid, path)
    return msg, gr.update(value=path, visible=True)


def _load_plan_fn(plan_label):
    global _current_plan_id
    if not plan_label:
        return "No plan selected.", ""
    plan_id = plan_label.split(":")[0].strip() if ":" in plan_label else plan_label
    msg, plan_data = load_plan(plan_id)
    _current_plan_id = plan_id
    if isinstance(plan_data, dict):
        lines = [f"**{k}:** {v}" for k, v in plan_data.items() if k != "plan_id"]
        return msg, "\n\n".join(lines)
    return msg, str(plan_data) if plan_data else ""


def _refresh_plans():
    plans = list_plans()
    labels = [f"{p.get('name', p.get('plan_id', p))}" for p in plans] if plans else []
    return gr.update(choices=labels)


def _recalculate(plan_id, new_hours):
    pid = _current_plan_id if not plan_id else plan_id
    if not pid:
        return "No plan loaded.", ""
    hours = float(new_hours) if new_hours and float(new_hours) > 0 else None
    msg, plan_data = recalculate_plan(pid, hours)
    if isinstance(plan_data, dict):
        lines = [f"**{k}:** {v}" for k, v in plan_data.items() if k != "plan_id"]
        return msg, "\n\n".join(lines)
    return msg, str(plan_data) if plan_data else ""


def create_ui():
    with gr.Tab("📅 Study Planner", elem_id="study-planner-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: How to use the Study Planner</a>"
            f"</div>"
        )

        with gr.Accordion("➕ Add Subjects", open=True):
            with gr.Row():
                shared.gradio['sp_subject_name'] = gr.Textbox(label="Subject name")
                shared.gradio['sp_exam_date'] = gr.Textbox(
                    label="Exam date", placeholder="YYYY-MM-DD"
                )
                shared.gradio['sp_difficulty'] = gr.Dropdown(
                    label="Difficulty",
                    choices=["easy", "medium", "hard"],
                    value="medium",
                )
            with gr.Row():
                shared.gradio['sp_confidence'] = gr.Slider(
                    minimum=1, maximum=10, value=5, step=1, label="Confidence (1-10)"
                )
                shared.gradio['sp_add_subject_btn'] = gr.Button(
                    "➕ Add Subject", variant="primary"
                )
            shared.gradio['sp_subjects_display'] = gr.Textbox(
                label="Added subjects", lines=5, interactive=False
            )
            shared.gradio['sp_clear_subjects_btn'] = gr.Button("🗑️ Clear All", size="sm")

        with gr.Accordion("📅 Generate Plan", open=True):
            with gr.Row():
                shared.gradio['sp_hours_slider'] = gr.Slider(
                    minimum=1, maximum=12, value=4, step=0.5, label="Study hours/day"
                )
                shared.gradio['sp_start_date'] = gr.Textbox(
                    label="Start date (optional)",
                    placeholder="YYYY-MM-DD (leave blank for today)",
                )
            shared.gradio['sp_generate_btn'] = gr.Button(
                "📅 Generate Study Plan", variant="primary"
            )
            shared.gradio['sp_gen_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📋 Plan View", open=False):
            with gr.Row():
                shared.gradio['sp_plan_selector'] = gr.Dropdown(
                    label="Load saved plan", choices=[], interactive=True
                )
                shared.gradio['sp_load_plan_btn'] = gr.Button("📂 Load")
                shared.gradio['sp_refresh_plans_btn'] = gr.Button("🔄")
            with gr.Row():
                shared.gradio['sp_today_btn'] = gr.Button("📌 Today")
                shared.gradio['sp_week_btn'] = gr.Button("📅 This Week")
                shared.gradio['sp_progress_btn'] = gr.Button("📊 Progress")
                shared.gradio['sp_recalc_btn'] = gr.Button("🔄 Recalculate")
            shared.gradio['sp_recalc_hours'] = gr.Number(
                label="New hours/day (0=keep current)", value=0, precision=1
            )
            shared.gradio['sp_plan_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['sp_plan_display'] = gr.Textbox(
                label="Schedule", lines=15, interactive=False
            )

        with gr.Accordion("📤 Export", open=False):
            with gr.Row():
                shared.gradio['sp_export_csv_btn'] = gr.Button("Export CSV")
                shared.gradio['sp_export_ical_btn'] = gr.Button("Export iCal")
            shared.gradio['sp_export_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['sp_export_file'] = gr.File(
                label="Download", interactive=False, visible=False
            )


def create_event_handlers():
    shared.gradio['sp_add_subject_btn'].click(
        _add_subject_fn,
        inputs=[
            shared.gradio['sp_subject_name'],
            shared.gradio['sp_exam_date'],
            shared.gradio['sp_difficulty'],
            shared.gradio['sp_confidence'],
        ],
        outputs=[shared.gradio['sp_gen_status'], shared.gradio['sp_subjects_display']],
        show_progress=False,
    )

    shared.gradio['sp_clear_subjects_btn'].click(
        _clear_subjects,
        inputs=[],
        outputs=[shared.gradio['sp_gen_status'], shared.gradio['sp_subjects_display']],
        show_progress=False,
    )

    shared.gradio['sp_generate_btn'].click(
        _generate_plan,
        inputs=[shared.gradio['sp_hours_slider'], shared.gradio['sp_start_date']],
        outputs=[
            shared.gradio['sp_gen_status'],
            shared.gradio['sp_plan_display'],
            shared.gradio['sp_plan_selector'],
        ],
        show_progress=True,
    )

    shared.gradio['sp_load_plan_btn'].click(
        _load_plan_fn,
        inputs=[shared.gradio['sp_plan_selector']],
        outputs=[shared.gradio['sp_plan_status'], shared.gradio['sp_plan_display']],
        show_progress=True,
    )

    shared.gradio['sp_refresh_plans_btn'].click(
        _refresh_plans,
        inputs=[],
        outputs=[shared.gradio['sp_plan_selector']],
        show_progress=False,
    )

    shared.gradio['sp_today_btn'].click(
        _get_today,
        inputs=[shared.gradio['sp_plan_selector']],
        outputs=[shared.gradio['sp_plan_status'], shared.gradio['sp_plan_display']],
        show_progress=True,
    )

    shared.gradio['sp_week_btn'].click(
        _get_week,
        inputs=[shared.gradio['sp_plan_selector']],
        outputs=[shared.gradio['sp_plan_status'], shared.gradio['sp_plan_display']],
        show_progress=True,
    )

    shared.gradio['sp_progress_btn'].click(
        _get_progress,
        inputs=[shared.gradio['sp_plan_selector']],
        outputs=[shared.gradio['sp_plan_status'], shared.gradio['sp_plan_display']],
        show_progress=True,
    )

    shared.gradio['sp_recalc_btn'].click(
        _recalculate,
        inputs=[shared.gradio['sp_plan_selector'], shared.gradio['sp_recalc_hours']],
        outputs=[shared.gradio['sp_plan_status'], shared.gradio['sp_plan_display']],
        show_progress=True,
    )

    shared.gradio['sp_export_csv_btn'].click(
        _export_csv_fn,
        inputs=[shared.gradio['sp_plan_selector']],
        outputs=[shared.gradio['sp_export_status'], shared.gradio['sp_export_file']],
        show_progress=True,
    )

    shared.gradio['sp_export_ical_btn'].click(
        _export_ical_fn,
        inputs=[shared.gradio['sp_plan_selector']],
        outputs=[shared.gradio['sp_export_status'], shared.gradio['sp_export_file']],
        show_progress=True,
    )

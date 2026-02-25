"""Gradio UI tab for the Google Calendar Integration feature."""

from __future__ import annotations

from datetime import date, timedelta

import gradio as gr

from modules import shared
from modules.google_calendar_integration import GoogleCalendarManager

TUTORIAL_URL = (
    "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab"
    "/blob/main/README.md#google-calendar-integration"
)

_cal = GoogleCalendarManager()


def _generate_reply(prompt: str) -> str:
    try:
        from modules.text_generation import generate_reply as _gen  # type: ignore
        full = ""
        for chunk in _gen(prompt, state={}, stopping_strings=[]):
            if isinstance(chunk, str):
                full = chunk
        return full
    except Exception as exc:
        return f"⚠️ Could not get AI response: {exc}"


def _authorize(creds_path: str):
    if not creds_path:
        return "<div style='color:#f44336'>No credentials file provided.</div>"
    success, msg = _cal.authorize(creds_path)
    color = "#4CAF50" if success else "#f44336"
    return f"<div style='color:{color};font-weight:600'>{msg}</div>"


def _reconnect():
    success, msg = _cal.connect_from_saved()
    color = "#4CAF50" if success else "#f44336"
    return f"<div style='color:{color};font-weight:600'>{msg}</div>"


def _fetch_events(date_range: str, custom_start: str, custom_end: str):
    today = date.today().isoformat()
    if date_range == "Today":
        start, end = today, today
    elif date_range == "This Week":
        monday = date.today() - timedelta(days=date.today().weekday())
        start = monday.isoformat()
        end = (monday + timedelta(days=6)).isoformat()
    elif date_range == "This Month":
        d = date.today()
        start = d.replace(day=1).isoformat()
        import calendar as _cal_mod
        last_day = _cal_mod.monthrange(d.year, d.month)[1]
        end = d.replace(day=last_day).isoformat()
    else:
        start = custom_start or today
        end = custom_end or today

    events, msg = _cal.get_events(start, end)
    rows = [
        [ev["start"][:10], ev["start"][11:16] if "T" in ev["start"] else "", ev["title"],
         "", ev["calendar"]]
        for ev in events
    ]
    return msg, rows


def _add_study_session(subject: str, date_str: str, start_time: str, end_time: str, notes: str):
    if not subject or not date_str:
        return "Please provide at least a subject and date."
    start = f"{date_str}T{start_time or '09:00'}:00"
    end = f"{date_str}T{end_time or '11:00'}:00"
    _, msg = _cal.create_event(
        title=f"Study: {subject}",
        start=start,
        end=end,
        description=notes or "",
    )
    return msg


def _add_reminder(title: str, date_str: str, time_str: str):
    if not title or not date_str:
        return "Please provide a title and date."
    start = f"{date_str}T{time_str or '08:00'}:00"
    end_dt = f"{date_str}T{_add_one_hour(time_str or '08:00')}:00"
    _, msg = _cal.create_event(title=title, start=start, end=end_dt, reminder_minutes=10)
    return msg


def _add_assignment(name: str, due_date: str, course: str, priority: str):
    if not name or not due_date:
        return "Please provide an assignment name and due date."
    desc = f"Course: {course or 'N/A'} | Priority: {priority or 'Normal'}"
    start = f"{due_date}T09:00:00"
    end = f"{due_date}T10:00:00"
    _, msg = _cal.create_event(title=f"📚 {name}", start=start, end=end, description=desc)
    return msg


def _ai_schedule_helper(request: str):
    if not request.strip():
        return "Please describe what you need scheduled."
    today = date.today().isoformat()
    events, _ = _cal.get_events(today, (date.today() + timedelta(days=7)).isoformat())
    events_str = "\n".join(
        f"- {e['title']} on {e['start'][:10]} at {e['start'][11:16] if 'T' in e['start'] else 'all-day'}"
        for e in events[:20]
    ) or "No events this week."
    prompt = (
        f"You are a scheduling assistant. Here is the user's current calendar for the next 7 days:\n"
        f"{events_str}\n\n"
        f"The user requests: {request}\n\n"
        f"Suggest optimal time slots and explain your reasoning. Today is {today}."
    )
    return _generate_reply(prompt)


def _add_one_hour(time_str: str) -> str:
    try:
        h, m = map(int, time_str.split(":"))
        h = (h + 1) % 24
        return f"{h:02d}:{m:02d}"
    except Exception:
        return "10:00"


def create_ui():
    with gr.Tab("📅 Google Calendar", elem_id="google-calendar-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: Google Calendar Integration</a>"
            f"</div>"
        )

        with gr.Accordion("🔧 Setup & Authorization", open=True):
            gr.Markdown(
                "**Step-by-step:**\n"
                "1. Go to [Google Cloud Console](https://console.cloud.google.com/) → Create a project\n"
                "2. Enable the **Google Calendar API**\n"
                "3. Create OAuth 2.0 credentials → Download `credentials.json`\n"
                "4. Upload the file below and click **Authorize**"
            )
            with gr.Row():
                shared.gradio['gcal_creds_path'] = gr.Textbox(
                    label="Path to credentials.json",
                    placeholder="/path/to/credentials.json",
                    scale=4,
                )
                shared.gradio['gcal_authorize_btn'] = gr.Button("Authorize", variant="primary", scale=1)
            shared.gradio['gcal_reconnect_btn'] = gr.Button("Reconnect (use saved token)", size="sm")
            shared.gradio['gcal_status'] = gr.HTML("<div style='color:#888'>Not connected</div>")

        gr.Markdown("---")
        gr.Markdown("### 📋 View Schedule")
        with gr.Row():
            shared.gradio['gcal_date_range'] = gr.Dropdown(
                label="Date Range",
                choices=["Today", "This Week", "This Month", "Custom"],
                value="Today",
                scale=2,
            )
            shared.gradio['gcal_custom_start'] = gr.Textbox(label="Custom Start (YYYY-MM-DD)", scale=2)
            shared.gradio['gcal_custom_end'] = gr.Textbox(label="Custom End (YYYY-MM-DD)", scale=2)
            shared.gradio['gcal_fetch_btn'] = gr.Button("Fetch Events", variant="primary", scale=1)

        shared.gradio['gcal_fetch_status'] = gr.Textbox(label="Status", interactive=False)
        shared.gradio['gcal_events_table'] = gr.Dataframe(
            headers=["Date", "Time", "Title", "Duration", "Calendar"],
            label="Events",
            interactive=False,
        )

        gr.Markdown("---")
        gr.Markdown("### ➕ Add Events")
        with gr.Accordion("📚 Add Study Session", open=False):
            with gr.Row():
                shared.gradio['gcal_study_subject'] = gr.Textbox(label="Subject", scale=2)
                shared.gradio['gcal_study_date'] = gr.Textbox(label="Date (YYYY-MM-DD)", scale=2)
                shared.gradio['gcal_study_start'] = gr.Textbox(label="Start Time (HH:MM)", value="09:00", scale=1)
                shared.gradio['gcal_study_end'] = gr.Textbox(label="End Time (HH:MM)", value="11:00", scale=1)
            shared.gradio['gcal_study_notes'] = gr.Textbox(label="Notes")
            shared.gradio['gcal_study_btn'] = gr.Button("Add Study Session", variant="primary")
            shared.gradio['gcal_study_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("⏰ Add Reminder", open=False):
            with gr.Row():
                shared.gradio['gcal_reminder_title'] = gr.Textbox(label="Title", scale=3)
                shared.gradio['gcal_reminder_date'] = gr.Textbox(label="Date (YYYY-MM-DD)", scale=2)
                shared.gradio['gcal_reminder_time'] = gr.Textbox(label="Time (HH:MM)", value="08:00", scale=1)
            shared.gradio['gcal_reminder_btn'] = gr.Button("Add Reminder", variant="primary")
            shared.gradio['gcal_reminder_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📝 Add Assignment Deadline", open=False):
            with gr.Row():
                shared.gradio['gcal_assign_name'] = gr.Textbox(label="Assignment Name", scale=3)
                shared.gradio['gcal_assign_due'] = gr.Textbox(label="Due Date (YYYY-MM-DD)", scale=2)
            with gr.Row():
                shared.gradio['gcal_assign_course'] = gr.Textbox(label="Course", scale=2)
                shared.gradio['gcal_assign_priority'] = gr.Dropdown(
                    label="Priority", choices=["Low", "Normal", "High", "Urgent"], value="Normal", scale=1
                )
            shared.gradio['gcal_assign_btn'] = gr.Button("Add Assignment", variant="primary")
            shared.gradio['gcal_assign_status'] = gr.Textbox(label="Status", interactive=False)

        gr.Markdown("---")
        gr.Markdown("### 🤖 AI Schedule Helper")
        shared.gradio['gcal_ai_request'] = gr.Textbox(
            label="Describe what you need scheduled",
            placeholder="Schedule a 2-hour study session for math this week",
            lines=2,
        )
        shared.gradio['gcal_ai_suggest_btn'] = gr.Button("Suggest Times", variant="primary")
        shared.gradio['gcal_ai_suggestions'] = gr.Markdown("")


def create_event_handlers():
    shared.gradio['gcal_authorize_btn'].click(
        _authorize,
        inputs=[shared.gradio['gcal_creds_path']],
        outputs=[shared.gradio['gcal_status']],
    )

    shared.gradio['gcal_reconnect_btn'].click(
        _reconnect,
        inputs=[],
        outputs=[shared.gradio['gcal_status']],
    )

    shared.gradio['gcal_fetch_btn'].click(
        _fetch_events,
        inputs=[
            shared.gradio['gcal_date_range'],
            shared.gradio['gcal_custom_start'],
            shared.gradio['gcal_custom_end'],
        ],
        outputs=[shared.gradio['gcal_fetch_status'], shared.gradio['gcal_events_table']],
    )

    shared.gradio['gcal_study_btn'].click(
        _add_study_session,
        inputs=[
            shared.gradio['gcal_study_subject'],
            shared.gradio['gcal_study_date'],
            shared.gradio['gcal_study_start'],
            shared.gradio['gcal_study_end'],
            shared.gradio['gcal_study_notes'],
        ],
        outputs=[shared.gradio['gcal_study_status']],
    )

    shared.gradio['gcal_reminder_btn'].click(
        _add_reminder,
        inputs=[
            shared.gradio['gcal_reminder_title'],
            shared.gradio['gcal_reminder_date'],
            shared.gradio['gcal_reminder_time'],
        ],
        outputs=[shared.gradio['gcal_reminder_status']],
    )

    shared.gradio['gcal_assign_btn'].click(
        _add_assignment,
        inputs=[
            shared.gradio['gcal_assign_name'],
            shared.gradio['gcal_assign_due'],
            shared.gradio['gcal_assign_course'],
            shared.gradio['gcal_assign_priority'],
        ],
        outputs=[shared.gradio['gcal_assign_status']],
    )

    shared.gradio['gcal_ai_suggest_btn'].click(
        _ai_schedule_helper,
        inputs=[shared.gradio['gcal_ai_request']],
        outputs=[shared.gradio['gcal_ai_suggestions']],
    )

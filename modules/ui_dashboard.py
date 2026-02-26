"""Gradio UI tab for the Student Dashboard feature."""

from __future__ import annotations

import random

import gradio as gr

from modules import shared

TUTORIAL_URL = (
    "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab"
    "/blob/main/README.md#dashboard"
)

_MOTIVATIONAL_QUOTES = [
    "The secret of getting ahead is getting started. – Mark Twain",
    "Education is the passport to the future. – Malcolm X",
    "The beautiful thing about learning is that nobody can take it away from you. – B.B. King",
    "An investment in knowledge pays the best interest. – Benjamin Franklin",
    "It does not matter how slowly you go as long as you do not stop. – Confucius",
    "Success is the sum of small efforts, repeated day in and day out. – Robert Collier",
    "The more that you read, the more things you will know. – Dr. Seuss",
    "The expert in anything was once a beginner. – Helen Hayes",
    "Push yourself, because no one else is going to do it for you.",
    "Great things never come from comfort zones.",
]


def _load_schedule() -> str:
    items: list[str] = []
    try:
        import json
        from pathlib import Path

        sp = Path("user_data/study_planner")
        if sp.exists():
            from datetime import date
            today = date.today().isoformat()
            for f in sp.glob("*.json"):
                data = json.loads(f.read_text())
                for session in data if isinstance(data, list) else [data]:
                    if session.get("date") == today:
                        items.append(
                            f"<li>📚 {session.get('subject','Session')} "
                            f"{session.get('start_time','')}–{session.get('end_time','')}</li>"
                        )
    except Exception:
        pass

    if not items:
        return (
            "<div style='color:#888;padding:10px'>"
            "No events today. Connect Google Calendar or set up Study Planner.</div>"
        )
    return f"<ul style='padding-left:20px'>{''.join(items)}</ul>"


def _load_deadlines() -> str:
    items: list[str] = []
    try:
        import json
        from pathlib import Path
        from datetime import date

        af = Path("user_data/assignments.json")
        if af.exists():
            assignments = json.loads(af.read_text())
            today = date.today().isoformat()
            for a in assignments if isinstance(assignments, list) else []:
                due = a.get("due_date", "")
                if due >= today:
                    color = "#f44336" if due == today else "#FF9800" if due <= today[:8] + "07" else "#4CAF50"
                    items.append(
                        f"<li style='color:{color}'>📋 {a.get('title','Assignment')} — due {due}</li>"
                    )
    except Exception:
        pass

    if not items:
        return (
            "<div style='color:#888;padding:10px'>"
            "No upcoming deadlines. Connect Google Classroom or add assignments.</div>"
        )
    return f"<ul style='padding-left:20px'>{''.join(items)}</ul>"


def _load_flashcards_due() -> str:
    try:
        import json
        from pathlib import Path

        fp = Path("user_data/flashcards")
        if not fp.exists():
            raise FileNotFoundError
        total_due = 0
        for f in fp.glob("*.json"):
            data = json.loads(f.read_text())
            total_due += len(data) if isinstance(data, list) else 0
        if total_due == 0:
            return "<div style='color:#888;padding:10px'>No flashcards due today.</div>"
        return (
            f"<div style='padding:10px;font-size:1.1em'>"
            f"🃏 <b style='color:#8ec8ff'>{total_due}</b> cards due for review.</div>"
        )
    except Exception:
        return "<div style='color:#888;padding:10px'>No flashcard data found.</div>"


def _load_xp_streak() -> str:
    try:
        import json
        from pathlib import Path

        xp_file = Path("user_data/xp.json")
        if not xp_file.exists():
            raise FileNotFoundError
        data = json.loads(xp_file.read_text())
        xp = data.get("xp", 0)
        level = data.get("level", 1)
        streak = data.get("streak", 0)
        return (
            f"<div style='padding:10px'>"
            f"⭐ <b>Level {level}</b> — {xp} XP<br>"
            f"🔥 <b>{streak} day streak</b>"
            f"</div>"
        )
    except Exception:
        return "<div style='color:#888;padding:10px'>No XP data yet. Start studying to earn XP!</div>"


def _get_ai_briefing() -> str:
    try:
        schedule = _load_schedule()
        deadlines = _load_deadlines()
        from modules.text_generation import generate_reply as _gen  # type: ignore
        prompt = (
            "You are Gizmo, an AI study assistant. Give the student a brief, motivating daily briefing "
            "based on their schedule and deadlines. Keep it under 100 words and be encouraging.\n\n"
            f"Schedule:\n{schedule}\n\nDeadlines:\n{deadlines}"
        )
        full = ""
        for chunk in _gen(prompt, state={}, stopping_strings=[]):
            if isinstance(chunk, str):
                full = chunk
        return full
    except Exception as exc:
        return f"⚠️ AI briefing unavailable: {exc}"


def _load_weekly_stats() -> str:
    try:
        import json
        from pathlib import Path

        sf = Path("user_data/study_stats.json")
        if not sf.exists():
            raise FileNotFoundError
        data = json.loads(sf.read_text())
        rows = ""
        for day, minutes in data.get("weekly", {}).items():
            bar_width = min(int(minutes / 3), 200)
            rows += (
                f"<tr><td style='padding:4px 10px'>{day}</td>"
                f"<td><div style='width:{bar_width}px;background:#8ec8ff;height:14px;border-radius:3px'></div></td>"
                f"<td style='padding:4px 10px'>{minutes} min</td></tr>"
            )
        if not rows:
            raise ValueError("No weekly data")
        return f"<table style='width:100%;border-collapse:collapse'>{rows}</table>"
    except Exception:
        return "<div style='color:#888;padding:10px'>No weekly stats yet. Keep studying to build your history!</div>"


def _get_motivational_quote() -> str:
    quote = random.choice(_MOTIVATIONAL_QUOTES)
    return (
        f"<div style='text-align:center;font-style:italic;color:#8ec8ff;padding:10px'>"
        f"💡 {quote}</div>"
    )


def _dashboard_header_html() -> str:
    return """
<div class='gizmo-dash-header'>
  <div>
    <div class='gizmo-dash-kicker'>Unified AI Workspace</div>
    <h2>Everything you need, one clean control center.</h2>
    <p>Chat, models, lessons, sessions, integrations, and tools are all still available in the tabs above.</p>
  </div>
</div>
"""


def _js_go_tab(label: str) -> str:
    return f"() => window.gizmoGoToTab && window.gizmoGoToTab({label!r})"


def create_ui():
    with gr.Tab("📊 Dashboard", elem_id="dashboard-tab"):
        gr.HTML(
            """
<style>
#dashboard-tab .gizmo-dash-header{padding:16px 18px;border:1px solid var(--border-color-primary);border-radius:14px;background:linear-gradient(135deg,#f8fafc 0%,#eef2ff 100%);margin-bottom:12px}
#dashboard-tab .gizmo-dash-kicker{font-size:.8rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6366f1}
#dashboard-tab .gizmo-dash-header h2{margin:6px 0 4px;font-size:1.25rem}
#dashboard-tab .gizmo-dash-header p{margin:0;color:#4b5563}
#dashboard-tab .gizmo-card{border:1px solid var(--border-color-primary);border-radius:12px;padding:10px;background:var(--block-background-fill)}
#dashboard-tab .gizmo-quick-btn button{height:56px;border-radius:12px !important;font-weight:600}
</style>
"""
        )
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: Dashboard Overview</a>"
            f"</div>"
        )

        gr.HTML(_dashboard_header_html())

        with gr.Row():
            with gr.Column(elem_classes=["gizmo-card"]):
                gr.Markdown("#### 📅 Today's Schedule")
                shared.gradio['dash_schedule_html'] = gr.HTML(_load_schedule())
                shared.gradio['dash_refresh_schedule_btn'] = gr.Button("🔄 Refresh")

            with gr.Column(elem_classes=["gizmo-card"]):
                gr.Markdown("#### ⏰ Upcoming Deadlines")
                shared.gradio['dash_deadlines_html'] = gr.HTML(_load_deadlines())
                shared.gradio['dash_refresh_deadlines_btn'] = gr.Button("🔄 Refresh")

            with gr.Column(elem_classes=["gizmo-card"]):
                gr.Markdown("#### 🃏 Review Due")
                shared.gradio['dash_review_html'] = gr.HTML(_load_flashcards_due())
                shared.gradio['dash_start_review_btn'] = gr.Button("🃏 Start Review")

        gr.Markdown("### ⚡ Quick Launch")
        with gr.Row():
            shared.gradio['dash_go_chat_btn'] = gr.Button("💬 Chat", elem_classes=["gizmo-quick-btn"])
            shared.gradio['dash_go_models_btn'] = gr.Button("🤖 Models", elem_classes=["gizmo-quick-btn"])
            shared.gradio['dash_go_lessons_btn'] = gr.Button("📚 Lessons", elem_classes=["gizmo-quick-btn"])
            shared.gradio['dash_go_session_btn'] = gr.Button("🧩 Session", elem_classes=["gizmo-quick-btn"])
            shared.gradio['dash_go_connections_btn'] = gr.Button("🔗 Connections", elem_classes=["gizmo-quick-btn"])

        gr.Markdown("---")

        with gr.Row():
            with gr.Column():
                with gr.Accordion("⭐ XP & Streak", open=True):
                    shared.gradio['dash_xp_html'] = gr.HTML(_load_xp_streak())
                    shared.gradio['dash_refresh_xp_btn'] = gr.Button("🔄 Refresh")

            with gr.Column():
                gr.Markdown("#### 🤖 AI Briefing")
                shared.gradio['dash_briefing_btn'] = gr.Button(
                    "🤖 Get Today's Briefing", variant="primary"
                )
                shared.gradio['dash_briefing_output'] = gr.Markdown("")

        with gr.Accordion("📈 Weekly Progress", open=False):
            shared.gradio['dash_refresh_stats_btn'] = gr.Button("🔄 Refresh Stats")
            shared.gradio['dash_weekly_stats_html'] = gr.HTML(_load_weekly_stats())

        shared.gradio['dash_quote_html'] = gr.HTML(_get_motivational_quote())
        shared.gradio['dash_refresh_quote_btn'] = gr.Button("✨ New Quote")


def create_event_handlers():
    shared.gradio['dash_refresh_schedule_btn'].click(
        _load_schedule,
        inputs=[],
        outputs=[shared.gradio['dash_schedule_html']],
    )

    shared.gradio['dash_refresh_deadlines_btn'].click(
        _load_deadlines,
        inputs=[],
        outputs=[shared.gradio['dash_deadlines_html']],
    )

    shared.gradio['dash_start_review_btn'].click(
        _load_flashcards_due,
        inputs=[],
        outputs=[shared.gradio['dash_review_html']],
    )

    shared.gradio['dash_refresh_xp_btn'].click(
        _load_xp_streak,
        inputs=[],
        outputs=[shared.gradio['dash_xp_html']],
    )

    shared.gradio['dash_briefing_btn'].click(
        _get_ai_briefing,
        inputs=[],
        outputs=[shared.gradio['dash_briefing_output']],
        show_progress=True,
    )

    shared.gradio['dash_refresh_stats_btn'].click(
        _load_weekly_stats,
        inputs=[],
        outputs=[shared.gradio['dash_weekly_stats_html']],
    )

    shared.gradio['dash_refresh_quote_btn'].click(
        _get_motivational_quote,
        inputs=[],
        outputs=[shared.gradio['dash_quote_html']],
    )

    shared.gradio['dash_go_chat_btn'].click(None, None, None, js=_js_go_tab("Chat"))
    shared.gradio['dash_go_models_btn'].click(None, None, None, js=_js_go_tab("Model"))
    shared.gradio['dash_go_lessons_btn'].click(None, None, None, js=_js_go_tab("Lessons"))
    shared.gradio['dash_go_session_btn'].click(None, None, None, js=_js_go_tab("Session"))
    shared.gradio['dash_go_connections_btn'].click(None, None, None, js=_js_go_tab("Connections"))

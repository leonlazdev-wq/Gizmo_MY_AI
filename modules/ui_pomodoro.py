"""Gradio UI tab for the Pomodoro Timer."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.pomodoro import get_stats, get_stats_html, record_session

_TIMER_HTML_TEMPLATE = """
<div id="pomodoro-container" style="font-family:'Segoe UI',Arial,sans-serif;text-align:center;padding:24px">
  <div id="pomo-session-label" style="font-size:1.1em;color:#6b7280;margin-bottom:8px">{session_label}</div>
  <div id="pomo-display" style="font-size:5em;font-weight:bold;letter-spacing:4px;color:{color};
       background:{bg};border-radius:16px;padding:20px 40px;display:inline-block;
       box-shadow:0 4px 16px rgba(0,0,0,0.1);margin-bottom:16px">{time_str}</div>
  <div style="color:#6b7280;font-size:0.9em">Pomodoro #{pomo_count} &nbsp;|&nbsp; {phase}</div>
</div>
"""


def _format_time(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"


def _render_timer_html(seconds: int, phase: str = "Work", pomo_count: int = 1) -> str:
    colors = {
        "Work": ("#1e40af", "#dbeafe"),
        "Short Break": ("#065f46", "#d1fae5"),
        "Long Break": ("#7c3aed", "#ede9fe"),
    }
    color, bg = colors.get(phase, ("#333", "#f9f9f9"))
    labels = {
        "Work": "🍅 Focus Time",
        "Short Break": "☕ Short Break",
        "Long Break": "🌿 Long Break",
    }
    label = labels.get(phase, phase)
    return _TIMER_HTML_TEMPLATE.format(
        session_label=label,
        color=color,
        bg=bg,
        time_str=_format_time(seconds),
        pomo_count=pomo_count,
        phase=phase,
    )


# In-memory timer state
_state = {
    "seconds_remaining": 25 * 60,
    "phase": "Work",
    "pomo_count": 1,
    "running": False,
    "work_duration": 25,
    "short_break": 5,
    "long_break": 15,
    "pomos_before_long": 4,
    "subject": "",
}


def _get_timer_html() -> str:
    return _render_timer_html(
        _state["seconds_remaining"],
        _state["phase"],
        _state["pomo_count"],
    )


def _start_timer_fn(work_dur, short_brk, long_brk, pomos_before, subject):
    _state.update({
        "work_duration": int(work_dur),
        "short_break": int(short_brk),
        "long_break": int(long_brk),
        "pomos_before_long": int(pomos_before),
        "subject": subject or "",
        "running": True,
    })
    if not _state["running"] or _state["seconds_remaining"] <= 0:
        _state["seconds_remaining"] = int(work_dur) * 60
        _state["phase"] = "Work"
    _state["running"] = True
    return _get_timer_html(), "⏱️ Timer started. Use the countdown below and click Complete when done."


def _pause_timer_fn():
    _state["running"] = False
    return _get_timer_html(), "⏸️ Paused."


def _reset_timer_fn():
    _state["running"] = False
    _state["seconds_remaining"] = _state["work_duration"] * 60
    _state["phase"] = "Work"
    return _get_timer_html(), "⏹️ Reset."


def _skip_fn():
    """Skip to next phase."""
    _state["running"] = False
    if _state["phase"] == "Work":
        _state["pomo_count"] += 1
        if _state["pomo_count"] % (_state["pomos_before_long"] + 1) == 0:
            _state["phase"] = "Long Break"
            _state["seconds_remaining"] = _state["long_break"] * 60
        else:
            _state["phase"] = "Short Break"
            _state["seconds_remaining"] = _state["short_break"] * 60
    else:
        _state["phase"] = "Work"
        _state["seconds_remaining"] = _state["work_duration"] * 60
    return _get_timer_html(), f"⏭️ Skipped to {_state['phase']}."


def _complete_session_fn():
    """Mark current session as complete and record it."""
    phase = _state.get("phase", "Work")
    if phase == "Work":
        msg = record_session(
            _state["work_duration"],
            session_type="work",
            subject=_state.get("subject", ""),
        )
    else:
        msg = f"✅ {phase} session ended."

    # Advance to next phase
    html, skip_msg = _skip_fn()
    stats_html = get_stats_html()
    return html, msg, stats_html


def _refresh_stats_fn():
    return get_stats_html()


def create_ui():
    with gr.Tab("📊 Pomodoro Timer", elem_id="pomodoro-tab"):
        shared.gradio['pomo_display'] = gr.HTML(
            value=_get_timer_html(),
            label="Timer",
        )

        with gr.Row():
            shared.gradio['pomo_start_btn'] = gr.Button("▶ Start", variant="primary")
            shared.gradio['pomo_pause_btn'] = gr.Button("⏸ Pause")
            shared.gradio['pomo_reset_btn'] = gr.Button("⏹ Reset")
            shared.gradio['pomo_skip_btn'] = gr.Button("⏭ Skip")
            shared.gradio['pomo_complete_btn'] = gr.Button("✅ Complete Session", variant="secondary")

        shared.gradio['pomo_status'] = gr.Textbox(
            label="Status", interactive=False, value="Configure settings and click ▶ Start."
        )

        with gr.Accordion("⚙️ Settings", open=False):
            with gr.Row():
                shared.gradio['pomo_work_dur'] = gr.Slider(
                    minimum=1, maximum=60, value=25, step=1, label="Work Duration (min)"
                )
                shared.gradio['pomo_short_brk'] = gr.Slider(
                    minimum=1, maximum=30, value=5, step=1, label="Short Break (min)"
                )
            with gr.Row():
                shared.gradio['pomo_long_brk'] = gr.Slider(
                    minimum=1, maximum=60, value=15, step=1, label="Long Break (min)"
                )
                shared.gradio['pomo_before_long'] = gr.Slider(
                    minimum=1, maximum=10, value=4, step=1, label="Pomodoros Before Long Break"
                )
            shared.gradio['pomo_subject'] = gr.Textbox(
                label="Subject Tag (optional)",
                placeholder="e.g. Math, History",
            )

        with gr.Accordion("📊 Stats", open=True):
            shared.gradio['pomo_stats_html'] = gr.HTML(
                value=get_stats_html(),
                label="Statistics",
            )
            shared.gradio['pomo_refresh_stats_btn'] = gr.Button("🔄 Refresh Stats")


def create_event_handlers():
    shared.gradio['pomo_start_btn'].click(
        _start_timer_fn,
        inputs=[
            shared.gradio['pomo_work_dur'],
            shared.gradio['pomo_short_brk'],
            shared.gradio['pomo_long_brk'],
            shared.gradio['pomo_before_long'],
            shared.gradio['pomo_subject'],
        ],
        outputs=[shared.gradio['pomo_display'], shared.gradio['pomo_status']],
        show_progress=False,
    )

    shared.gradio['pomo_pause_btn'].click(
        _pause_timer_fn,
        inputs=[],
        outputs=[shared.gradio['pomo_display'], shared.gradio['pomo_status']],
        show_progress=False,
    )

    shared.gradio['pomo_reset_btn'].click(
        _reset_timer_fn,
        inputs=[],
        outputs=[shared.gradio['pomo_display'], shared.gradio['pomo_status']],
        show_progress=False,
    )

    shared.gradio['pomo_skip_btn'].click(
        _skip_fn,
        inputs=[],
        outputs=[shared.gradio['pomo_display'], shared.gradio['pomo_status']],
        show_progress=False,
    )

    shared.gradio['pomo_complete_btn'].click(
        _complete_session_fn,
        inputs=[],
        outputs=[
            shared.gradio['pomo_display'],
            shared.gradio['pomo_status'],
            shared.gradio['pomo_stats_html'],
        ],
        show_progress=False,
    )

    shared.gradio['pomo_refresh_stats_btn'].click(
        _refresh_stats_fn,
        inputs=[],
        outputs=[shared.gradio['pomo_stats_html']],
        show_progress=False,
    )

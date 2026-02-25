"""Gradio UI tab for Gamification / Achievements."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.gamification import (
    BADGES,
    LEVELS,
    award_xp,
    check_badge,
    get_all_data,
    get_level_info,
    get_streak,
    get_weekly_activity,
    record_daily_login,
)


def _profile_html(data=None):
    if data is None:
        data = get_all_data()
    level_info = get_level_info(data.get("xp", 0))
    level_num = level_info["level"]
    level_name = level_info["level_name"]
    xp = level_info["xp"]
    progress = level_info["progress_pct"]
    xp_to_next = level_info["xp_to_next"]
    next_threshold = level_info["next_threshold"]
    streak = data.get("streak", {})
    current_streak = streak.get("current", 0)
    longest_streak = streak.get("longest", 0)

    bar_color = "#4CAF50" if progress >= 75 else "#2196F3" if progress >= 40 else "#FF9800"
    next_str = f"({xp_to_next} XP to Level {level_num+1})" if xp_to_next > 0 else "(Max Level!)"

    return f"""
<div style='background:#1a1a2e;border-radius:12px;padding:20px;margin-bottom:12px'>
  <div style='display:flex;align-items:center;gap:16px'>
    <div style='font-size:3em'>🏅</div>
    <div>
      <div style='font-size:1.4em;font-weight:bold;color:#e0e0e0'>Level {level_num} — {level_name}</div>
      <div style='color:#8ec8ff;font-size:1.1em'>{xp} XP total {next_str}</div>
    </div>
  </div>
  <div style='margin-top:12px'>
    <div style='display:flex;justify-content:space-between;font-size:.85em;color:#999;margin-bottom:4px'>
      <span>XP Progress</span><span>{progress}%</span>
    </div>
    <div style='background:#333;border-radius:6px;height:16px;overflow:hidden'>
      <div style='background:{bar_color};height:100%;width:{progress}%;transition:width .5s'></div>
    </div>
  </div>
  <div style='margin-top:12px;display:flex;gap:24px'>
    <div style='text-align:center'>
      <div style='font-size:1.5em;font-weight:bold;color:#FFD700'>🔥 {current_streak}</div>
      <div style='font-size:.8em;color:#999'>Current Streak</div>
    </div>
    <div style='text-align:center'>
      <div style='font-size:1.5em;font-weight:bold;color:#FFA500'>🏆 {longest_streak}</div>
      <div style='font-size:.8em;color:#999'>Longest Streak</div>
    </div>
  </div>
</div>
"""


def _badges_html(data=None):
    if data is None:
        data = get_all_data()
    earned = data.get("badges", {})
    items = []
    for badge_id, badge in BADGES.items():
        if badge_id in earned:
            earned_at = earned[badge_id].get("earned_at", "")[:10]
            items.append(
                f"<div style='background:#1e3a1e;border:1px solid #4CAF50;border-radius:8px;"
                f"padding:12px;text-align:center'>"
                f"<div style='font-size:2em'>{badge['icon']}</div>"
                f"<div style='font-weight:bold;color:#4CAF50'>{badge['name']}</div>"
                f"<div style='font-size:.8em;color:#999'>{badge['description']}</div>"
                f"<div style='font-size:.75em;color:#666;margin-top:4px'>Earned {earned_at}</div>"
                f"</div>"
            )
        else:
            items.append(
                f"<div style='background:#1a1a1a;border:1px solid #444;border-radius:8px;"
                f"padding:12px;text-align:center;opacity:.5'>"
                f"<div style='font-size:2em;filter:grayscale(1)'>{badge['icon']}</div>"
                f"<div style='font-weight:bold;color:#666'>{badge['name']}</div>"
                f"<div style='font-size:.8em;color:#555'>{badge['description']}</div>"
                f"<div style='font-size:.75em;color:#444;margin-top:4px'>🔒 Locked</div>"
                f"</div>"
            )
    grid = (
        "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px'>"
        + "".join(items)
        + "</div>"
    )
    return grid


def _stats_html(data=None):
    if data is None:
        data = get_all_data()
    stats = data.get("stats", {})
    weekly = get_weekly_activity()
    rows = [
        ("📝 Quizzes Completed", stats.get("quizzes_completed", 0)),
        ("🃏 Flashcards Reviewed", stats.get("flashcards_reviewed", 0)),
        ("⏱️ Pomodoros Completed", stats.get("pomodoros_completed", 0)),
        ("🌍 Translations Done", stats.get("translations_completed", 0)),
        ("📄 Essays Saved", stats.get("essays_saved", 0)),
        ("🧠 Memories Saved", stats.get("memories_saved", 0)),
        ("✍️ Notes Created", stats.get("notes_created", 0)),
    ]
    stat_items = "".join(
        f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
        f"border-bottom:1px solid #333'>"
        f"<span>{label}</span><strong>{value}</strong></div>"
        for label, value in rows
    )

    # Simple weekly chart
    max_xp = max((d["xp"] for d in weekly), default=1) or 1
    bars = ""
    for d in weekly:
        pct = int((d["xp"] / max_xp) * 60)
        day = d["date"][-5:]
        xp_val = d["xp"]
        bars += (
            f"<div style='display:flex;flex-direction:column;align-items:center;gap:4px'>"
            f"<div style='width:28px;background:#2196F3;height:{pct}px;min-height:2px;"
            f"border-radius:3px 3px 0 0' title='{xp_val} XP'></div>"
            f"<div style='font-size:.7em;color:#999'>{day}</div>"
            f"</div>"
        )
    chart = (
        f"<div style='margin-top:16px'>"
        f"<div style='font-size:.9em;font-weight:bold;color:#ccc;margin-bottom:8px'>📊 Weekly XP Activity</div>"
        f"<div style='display:flex;align-items:flex-end;gap:6px;height:80px'>{bars}</div>"
        f"</div>"
    )

    return f"<div style='padding:12px'>{stat_items}{chart}</div>"


def _activity_log_html(data=None):
    if data is None:
        data = get_all_data()
    log = list(reversed(data.get("activity_log", [])))[:20]
    if not log:
        return "<p style='color:gray'>No activity recorded yet.</p>"
    rows = []
    for entry in log:
        ts = entry.get("timestamp", "")[:16].replace("T", " ")
        amount = entry.get("amount", 0)
        reason = entry.get("reason", "")
        total = entry.get("total_xp", 0)
        rows.append(
            f"<tr>"
            f"<td style='padding:4px 8px;color:gray;font-size:.85em'>{ts}</td>"
            f"<td style='padding:4px 8px;color:#4CAF50'>+{amount} XP</td>"
            f"<td style='padding:4px 8px'>{reason}</td>"
            f"<td style='padding:4px 8px;color:#8ec8ff'>{total} total</td>"
            f"</tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse'>"
        + "".join(rows)
        + "</table>"
    )


def _refresh_all():
    data = get_all_data()
    return (
        _profile_html(data),
        _badges_html(data),
        _stats_html(data),
        _activity_log_html(data),
    )


def _award_xp_manual(amount, reason):
    try:
        amt = int(amount)
    except (ValueError, TypeError):
        return "❌ Invalid amount.", *_refresh_all()
    result = award_xp(amt, reason or "Manual award")
    msg = f"✅ Awarded {amt} XP!"
    if result.get("leveled_up"):
        msg += f" 🎉 Level up! Now Level {result['level']} — {result['level_name']}"
    return (msg,) + _refresh_all()


def create_ui():
    with gr.Tab("🏅 Achievements", elem_id="achievements-tab"):

        with gr.Row():
            shared.gradio['gm_refresh_btn'] = gr.Button("🔄 Refresh", scale=0)
            shared.gradio['gm_login_btn'] = gr.Button("☀️ Record Daily Login", scale=0)

        # Profile card
        shared.gradio['gm_profile_html'] = gr.HTML(_profile_html())

        # Badges grid
        gr.Markdown("### 🎖️ Badges")
        shared.gradio['gm_badges_html'] = gr.HTML(_badges_html())

        # Stats
        gr.Markdown("### 📊 Stats")
        shared.gradio['gm_stats_html'] = gr.HTML(_stats_html())

        # Activity log accordion
        with gr.Accordion("📋 Activity Log", open=False):
            shared.gradio['gm_activity_html'] = gr.HTML(_activity_log_html())

        # Manual XP award (for testing / admin)
        with gr.Accordion("⚙️ Award XP (Admin)", open=False):
            with gr.Row():
                shared.gradio['gm_xp_amount'] = gr.Number(label="XP Amount", value=10, scale=1)
                shared.gradio['gm_xp_reason'] = gr.Textbox(
                    label="Reason", placeholder="e.g. Completed quiz", scale=3
                )
                shared.gradio['gm_award_btn'] = gr.Button("🎁 Award XP", scale=1)
            shared.gradio['gm_award_status'] = gr.Textbox(label="Status", interactive=False)


def create_event_handlers():
    _all_outputs = [
        shared.gradio['gm_profile_html'],
        shared.gradio['gm_badges_html'],
        shared.gradio['gm_stats_html'],
        shared.gradio['gm_activity_html'],
    ]

    shared.gradio['gm_refresh_btn'].click(
        _refresh_all,
        inputs=[],
        outputs=_all_outputs,
        show_progress=False,
    )

    shared.gradio['gm_login_btn'].click(
        lambda: _refresh_all(),
        inputs=[],
        outputs=_all_outputs,
        show_progress=False,
    )

    shared.gradio['gm_award_btn'].click(
        _award_xp_manual,
        inputs=[
            shared.gradio['gm_xp_amount'],
            shared.gradio['gm_xp_reason'],
        ],
        outputs=[
            shared.gradio['gm_award_status'],
            shared.gradio['gm_profile_html'],
            shared.gradio['gm_badges_html'],
            shared.gradio['gm_stats_html'],
            shared.gradio['gm_activity_html'],
        ],
        show_progress=False,
    )

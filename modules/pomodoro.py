"""Pomodoro Timer backend for Gizmo."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

_STATS_FILE = os.path.join("user_data", "pomodoro_stats.json")


def _ensure_dirs() -> None:
    """Create user_data/ directory if it doesn't exist."""
    os.makedirs("user_data", exist_ok=True)


def _load_stats() -> Dict:
    """Load pomodoro stats from file."""
    _ensure_dirs()
    if not os.path.isfile(_STATS_FILE):
        return {"sessions": []}
    try:
        with open(_STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sessions": []}


def _save_stats(stats: Dict) -> None:
    """Save pomodoro stats to file."""
    _ensure_dirs()
    try:
        with open(_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def record_session(
    duration_minutes: int,
    session_type: str = "work",
    subject: str = "",
) -> str:
    """Record a completed pomodoro session."""
    stats = _load_stats()
    session = {
        "timestamp": datetime.now().isoformat(),
        "date": date.today().strftime("%Y-%m-%d"),
        "duration_minutes": duration_minutes,
        "type": session_type,
        "subject": subject,
    }
    stats.setdefault("sessions", []).append(session)
    _save_stats(stats)
    return f"✅ Recorded {session_type} session ({duration_minutes} min)."


def get_stats() -> Dict:
    """Return aggregated statistics."""
    stats = _load_stats()
    sessions = stats.get("sessions", [])

    today_str = date.today().strftime("%Y-%m-%d")
    today_sessions = [s for s in sessions if s.get("date") == today_str and s.get("type") == "work"]

    # This week
    from datetime import timedelta
    week_start = date.today() - timedelta(days=date.today().weekday())
    week_sessions = [
        s for s in sessions
        if s.get("date", "") >= week_start.strftime("%Y-%m-%d") and s.get("type") == "work"
    ]

    work_sessions = [s for s in sessions if s.get("type") == "work"]
    total_focus_minutes = sum(s.get("duration_minutes", 0) for s in work_sessions)

    # Streak calculation
    streak = 0
    check_date = date.today()
    session_dates = {s.get("date") for s in work_sessions}
    while check_date.strftime("%Y-%m-%d") in session_dates:
        streak += 1
        check_date -= timedelta(days=1)

    return {
        "today_count": len(today_sessions),
        "today_minutes": sum(s.get("duration_minutes", 0) for s in today_sessions),
        "week_count": len(week_sessions),
        "week_minutes": sum(s.get("duration_minutes", 0) for s in week_sessions),
        "total_count": len(work_sessions),
        "total_minutes": total_focus_minutes,
        "streak_days": streak,
        "recent_sessions": sessions[-10:][::-1],
    }


def get_stats_html(stats: Optional[Dict] = None) -> str:
    """Render stats as HTML."""
    if stats is None:
        stats = get_stats()

    today_h = stats['today_minutes'] // 60
    today_m = stats['today_minutes'] % 60
    week_h = stats['week_minutes'] // 60
    week_m = stats['week_minutes'] % 60
    total_h = stats['total_minutes'] // 60
    total_m = stats['total_minutes'] % 60

    rows = ""
    for s in stats.get("recent_sessions", []):
        subj = s.get("subject") or "—"
        rows += (
            f"<tr>"
            f"<td>{s.get('date','')}</td>"
            f"<td>{s.get('timestamp','')[:19]}</td>"
            f"<td>{s.get('type','')}</td>"
            f"<td>{s.get('duration_minutes',0)} min</td>"
            f"<td>{subj}</td>"
            f"</tr>"
        )

    return f"""
<div style="font-family:'Segoe UI',Arial,sans-serif;padding:8px">
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">
    <div style="background:#dbeafe;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:1.8em;font-weight:bold">{stats['today_count']}</div>
      <div style="color:#555;font-size:0.85em">Today's Pomodoros</div>
      <div style="color:#888;font-size:0.8em">{today_h}h {today_m}m</div>
    </div>
    <div style="background:#dcfce7;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:1.8em;font-weight:bold">{stats['week_count']}</div>
      <div style="color:#555;font-size:0.85em">This Week</div>
      <div style="color:#888;font-size:0.8em">{week_h}h {week_m}m</div>
    </div>
    <div style="background:#fef3c7;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:1.8em;font-weight:bold">{stats['total_count']}</div>
      <div style="color:#555;font-size:0.85em">All Time</div>
      <div style="color:#888;font-size:0.8em">{total_h}h {total_m}m</div>
    </div>
    <div style="background:#fce7f3;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:1.8em;font-weight:bold">{stats['streak_days']}🔥</div>
      <div style="color:#555;font-size:0.85em">Day Streak</div>
    </div>
  </div>
  <h4 style="margin:8px 0">Recent Sessions</h4>
  <table style="width:100%;border-collapse:collapse;font-size:0.85em">
    <thead><tr style="background:#f3f4f6">
      <th style="text-align:left;padding:6px">Date</th>
      <th style="text-align:left;padding:6px">Time</th>
      <th style="text-align:left;padding:6px">Type</th>
      <th style="text-align:left;padding:6px">Duration</th>
      <th style="text-align:left;padding:6px">Subject</th>
    </tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="5" style="padding:8px;color:#888">No sessions recorded yet.</td></tr>'}</tbody>
  </table>
</div>"""

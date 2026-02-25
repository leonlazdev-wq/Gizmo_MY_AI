"""Gamification / XP System backend for Gizmo."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

_GAMIFICATION_FILE = os.path.join("user_data", "gamification.json")

LEVELS = [
    (0, "Beginner"),
    (100, "Learner"),
    (300, "Scholar"),
    (600, "Expert"),
    (1000, "Master"),
    (1500, "Grandmaster"),
    (2500, "Legend"),
]

BADGES: Dict[str, Dict] = {
    "first_quiz": {
        "id": "first_quiz",
        "name": "First Steps",
        "icon": "🔥",
        "description": "Complete your first quiz",
    },
    "bookworm": {
        "id": "bookworm",
        "name": "Bookworm",
        "icon": "📚",
        "description": "Review 100 flashcards",
    },
    "focus_master": {
        "id": "focus_master",
        "name": "Focus Master",
        "icon": "⏱️",
        "description": "Complete 10 pomodoro sessions",
    },
    "perfect_score": {
        "id": "perfect_score",
        "name": "Perfect Score",
        "icon": "🎯",
        "description": "Get 100% on a quiz",
    },
    "consistent_7": {
        "id": "consistent_7",
        "name": "Consistent",
        "icon": "📅",
        "description": "7-day study streak",
    },
    "dedicated_30": {
        "id": "dedicated_30",
        "name": "Dedicated",
        "icon": "🏆",
        "description": "30-day study streak",
    },
    "knowledge_base": {
        "id": "knowledge_base",
        "name": "Knowledge Base",
        "icon": "🧠",
        "description": "Save 50 memories",
    },
    "note_taker": {
        "id": "note_taker",
        "name": "Note Taker",
        "icon": "✍️",
        "description": "Create 10 sets of notes",
    },
    "translator": {
        "id": "translator",
        "name": "Polyglot",
        "icon": "🌍",
        "description": "Complete 10 translations",
    },
    "essay_writer": {
        "id": "essay_writer",
        "name": "Wordsmith",
        "icon": "📝",
        "description": "Save 5 essays",
    },
}

XP_REWARDS = {
    "quiz_correct_answer": 10,
    "quiz_perfect_score": 50,
    "flashcard_reviewed": 5,
    "pomodoro_completed": 25,
    "study_session_completed": 15,
    "daily_login": 10,
    "streak_bonus": 5,
    "translation_completed": 3,
    "essay_saved": 20,
    "collaborative_quiz_completed": 15,
}


def _load_data() -> Dict:
    if os.path.isfile(_GAMIFICATION_FILE):
        try:
            with open(_GAMIFICATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _default_data()


def _default_data() -> Dict:
    return {
        "xp": 0,
        "badges": {},
        "streak": {
            "current": 0,
            "longest": 0,
            "last_active": "",
        },
        "stats": {
            "quizzes_completed": 0,
            "flashcards_reviewed": 0,
            "pomodoros_completed": 0,
            "translations_completed": 0,
            "essays_saved": 0,
            "notes_created": 0,
            "memories_saved": 0,
        },
        "activity_log": [],
    }


def _save_data(data: Dict) -> None:
    os.makedirs(os.path.dirname(_GAMIFICATION_FILE), exist_ok=True)
    with open(_GAMIFICATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_level_info(xp: Optional[int] = None) -> Dict:
    """Return current level number, name, XP, and progress to next level."""
    data = _load_data() if xp is None else {"xp": xp}
    total_xp = data["xp"] if xp is None else xp
    level_num = 1
    level_name = LEVELS[0][1]
    for i, (threshold, name) in enumerate(LEVELS):
        if total_xp >= threshold:
            level_num = i + 1
            level_name = name

    next_threshold = None
    for threshold, _ in LEVELS:
        if threshold > total_xp:
            next_threshold = threshold
            break

    if next_threshold is None:
        progress_pct = 100
        xp_to_next = 0
    else:
        prev_threshold = LEVELS[level_num - 1][0]
        span = next_threshold - prev_threshold
        progress = total_xp - prev_threshold
        progress_pct = int((progress / span) * 100) if span > 0 else 100
        xp_to_next = next_threshold - total_xp

    return {
        "level": level_num,
        "level_name": level_name,
        "xp": total_xp,
        "next_threshold": next_threshold,
        "progress_pct": progress_pct,
        "xp_to_next": xp_to_next,
    }


def award_xp(amount: int, reason: str = "") -> Dict:
    """Add XP and check for level-ups. Returns updated level info."""
    data = _load_data()
    old_level = get_level_info(data["xp"])["level"]
    data["xp"] = data.get("xp", 0) + amount
    new_level_info = get_level_info(data["xp"])

    entry = {
        "timestamp": datetime.now().isoformat(),
        "amount": amount,
        "reason": reason,
        "total_xp": data["xp"],
    }
    data.setdefault("activity_log", []).append(entry)
    # Keep only last 100 entries
    data["activity_log"] = data["activity_log"][-100:]

    leveled_up = new_level_info["level"] > old_level
    _save_data(data)
    return {**new_level_info, "leveled_up": leveled_up}


def check_badge(badge_id: str) -> bool:
    """Check if a badge condition is met and award it. Returns True if newly awarded."""
    if badge_id not in BADGES:
        return False
    data = _load_data()
    if badge_id in data.get("badges", {}):
        return False  # Already earned

    earned = _check_badge_condition(badge_id, data)
    if earned:
        data.setdefault("badges", {})[badge_id] = {
            "earned_at": datetime.now().isoformat(),
        }
        _save_data(data)
    return earned


def _check_badge_condition(badge_id: str, data: Dict) -> bool:
    stats = data.get("stats", {})
    streak = data.get("streak", {})
    if badge_id == "first_quiz":
        return stats.get("quizzes_completed", 0) >= 1
    elif badge_id == "bookworm":
        return stats.get("flashcards_reviewed", 0) >= 100
    elif badge_id == "focus_master":
        return stats.get("pomodoros_completed", 0) >= 10
    elif badge_id == "perfect_score":
        return stats.get("perfect_scores", 0) >= 1
    elif badge_id == "consistent_7":
        return streak.get("current", 0) >= 7
    elif badge_id == "dedicated_30":
        return streak.get("current", 0) >= 30
    elif badge_id == "knowledge_base":
        return stats.get("memories_saved", 0) >= 50
    elif badge_id == "note_taker":
        return stats.get("notes_created", 0) >= 10
    elif badge_id == "translator":
        return stats.get("translations_completed", 0) >= 10
    elif badge_id == "essay_writer":
        return stats.get("essays_saved", 0) >= 5
    return False


def get_streak() -> Dict:
    """Return current streak and longest streak."""
    data = _load_data()
    return data.get("streak", {"current": 0, "longest": 0, "last_active": ""})


def update_streak() -> Dict:
    """Update the daily streak. Should be called on each session start."""
    data = _load_data()
    streak = data.setdefault("streak", {"current": 0, "longest": 0, "last_active": ""})
    today = date.today().isoformat()
    last = streak.get("last_active", "")
    if last == today:
        return streak  # Already updated today
    elif last == (date.today().toordinal() - 1 and date.fromisoformat(last).toordinal() if last else -1):
        # Consecutive day
        pass

    try:
        if last and (date.today() - date.fromisoformat(last)).days == 1:
            streak["current"] = streak.get("current", 0) + 1
        elif last and (date.today() - date.fromisoformat(last)).days > 1:
            streak["current"] = 1
        else:
            streak["current"] = streak.get("current", 0) + 1
    except Exception:
        streak["current"] = 1

    streak["last_active"] = today
    streak["longest"] = max(streak.get("longest", 0), streak["current"])
    data["streak"] = streak
    _save_data(data)
    return streak


def record_daily_login() -> Dict:
    """Record daily login, award XP and update streak."""
    streak = update_streak()
    last = streak.get("last_active", "")
    today = date.today().isoformat()

    result = {}
    if last == today:
        xp_result = award_xp(XP_REWARDS["daily_login"], "Daily login")
        result = xp_result
        if streak.get("current", 0) > 1:
            bonus = XP_REWARDS["streak_bonus"] * streak["current"]
            award_xp(bonus, f"Streak bonus ({streak['current']} days)")
        # Check streak badges
        for badge_id in ["consistent_7", "dedicated_30"]:
            check_badge(badge_id)
    return result


def increment_stat(stat_name: str, amount: int = 1) -> None:
    """Increment a stat counter."""
    data = _load_data()
    data.setdefault("stats", {})[stat_name] = data["stats"].get(stat_name, 0) + amount
    _save_data(data)


def get_all_data() -> Dict:
    """Return all gamification data."""
    return _load_data()


def get_weekly_activity() -> List[Dict]:
    """Return activity for the last 7 days."""
    data = _load_data()
    log = data.get("activity_log", [])
    today = date.today()
    weekly: Dict[str, int] = {}
    for i in range(7):
        d = (today.toordinal() - i)
        day_str = date.fromordinal(d).isoformat()
        weekly[day_str] = 0
    for entry in log:
        try:
            entry_date = entry["timestamp"][:10]
            if entry_date in weekly:
                weekly[entry_date] = weekly[entry_date] + entry.get("amount", 0)
        except Exception:
            pass
    return [{"date": k, "xp": v} for k, v in sorted(weekly.items())]

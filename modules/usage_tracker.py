import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

STATS_FILE = Path("user_data/usage_stats.json")


def _default_stats() -> dict:
    return {
        "sessions": [],
        "lifetime": {
            "total_messages": 0,
            "total_tokens_generated": 0,
            "total_tokens_input": 0,
            "total_chats": 0,
            "total_generation_time_s": 0.0,
            "models_used": {},
            "first_use": str(date.today()),
            "streak_days": 0,
        }
    }


def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return _default_stats()


def _save_stats(stats: dict):
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(stats, indent=4, ensure_ascii=False), encoding='utf-8')


def log_generation(model_name: str, tokens_generated: int, tokens_input: int, generation_time_s: float):
    """Log a single generation event"""
    try:
        stats = load_stats()
        today = str(date.today())
        lt = stats["lifetime"]

        lt["total_messages"] = lt.get("total_messages", 0) + 1
        lt["total_tokens_generated"] = lt.get("total_tokens_generated", 0) + tokens_generated
        lt["total_tokens_input"] = lt.get("total_tokens_input", 0) + tokens_input
        lt["total_generation_time_s"] = lt.get("total_generation_time_s", 0.0) + generation_time_s
        models_used = lt.get("models_used", {})
        models_used[model_name] = models_used.get(model_name, 0) + 1
        lt["models_used"] = models_used

        # Update today's session
        sessions = stats.get("sessions", [])
        today_session = next((s for s in sessions if s.get("date") == today), None)
        if today_session is None:
            today_session = {
                "date": today,
                "model": model_name,
                "messages_sent": 0,
                "tokens_generated": 0,
                "tokens_input": 0,
                "total_generation_time_s": 0.0,
            }
            sessions.append(today_session)

        today_session["messages_sent"] = today_session.get("messages_sent", 0) + 1
        today_session["tokens_generated"] = today_session.get("tokens_generated", 0) + tokens_generated
        today_session["tokens_input"] = today_session.get("tokens_input", 0) + tokens_input
        today_session["total_generation_time_s"] = today_session.get("total_generation_time_s", 0.0) + generation_time_s
        today_session["model"] = model_name

        # Keep only last 90 days
        stats["sessions"] = sessions[-90:]
        lt["streak_days"] = calculate_streak(sessions)

        _save_stats(stats)
    except Exception:
        pass  # Never break chat for stats errors


def get_dashboard_data() -> dict:
    """Compute dashboard stats from logged data"""
    stats = load_stats()
    lt = stats["lifetime"]
    today = str(date.today())
    sessions = stats.get("sessions", [])

    today_session = next((s for s in sessions if s.get("date") == today), {})
    today_messages = today_session.get("messages_sent", 0)
    today_tokens = today_session.get("tokens_generated", 0)

    total_gen_time = lt.get("total_generation_time_s", 0.0)
    total_messages = lt.get("total_messages", 0)
    avg_response = (total_gen_time / total_messages) if total_messages > 0 else 0.0

    models_used = lt.get("models_used", {})
    most_used = max(models_used, key=models_used.get) if models_used else "None"

    return {
        "today_messages": today_messages,
        "total_messages": total_messages,
        "today_tokens": today_tokens,
        "total_tokens": lt.get("total_tokens_generated", 0),
        "avg_response_time": avg_response,
        "streak_days": lt.get("streak_days", 0),
        "most_used_model": most_used,
        "total_chats": lt.get("total_chats", 0),
        "total_gen_time_s": total_gen_time,
        "first_use": lt.get("first_use", today),
        "models_used": models_used,
        "sessions": sessions,
    }


def get_usage_chart_data() -> dict:
    """Get data for rendering usage charts (last 30 days)"""
    stats = load_stats()
    sessions = stats.get("sessions", [])[-30:]
    dates = [s.get("date", "") for s in sessions]
    messages = [s.get("messages_sent", 0) for s in sessions]
    tokens_out = [s.get("tokens_generated", 0) for s in sessions]
    tokens_in = [s.get("tokens_input", 0) for s in sessions]
    return {"dates": dates, "messages": messages, "tokens_out": tokens_out, "tokens_in": tokens_in}


def calculate_streak(sessions=None) -> int:
    """Calculate consecutive days of usage"""
    from datetime import timedelta
    if sessions is None:
        sessions = load_stats().get("sessions", [])
    if not sessions:
        return 0
    used_dates = sorted({s["date"] for s in sessions if s.get("messages_sent", 0) > 0}, reverse=True)
    if not used_dates:
        return 0
    streak = 0
    check = date.today()
    for d_str in used_dates:
        d = date.fromisoformat(d_str)
        if d == check:
            streak += 1
            check = check - timedelta(days=1)
        else:
            break
    return streak

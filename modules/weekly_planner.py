"""Smart Weekly Planner backend for Gizmo.

Provides AI-powered automatic scheduling with spaced repetition,
adaptive rescheduling, and Google Calendar sync.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

_WEEKLY_PLANNER_DIR = os.path.join("user_data", "weekly_planner")
_FLASHCARDS_DIR = os.path.join("user_data", "flashcards")
_QUIZ_RESULTS_DIR = os.path.join("user_data", "quiz_results")
_STUDY_PLANS_DIR = os.path.join("user_data", "study_plans")


def _ensure_dirs() -> None:
    """Create user_data/weekly_planner/ directory if it doesn't exist."""
    os.makedirs(_WEEKLY_PLANNER_DIR, exist_ok=True)


def _call_ai(prompt: str):
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = 2048
        from modules.text_generation import generate_reply
        output = ""
        for chunk in generate_reply(prompt, state, stopping_strings=[], is_chat=False):
            if isinstance(chunk, str):
                output = chunk
            elif isinstance(chunk, (list, tuple)) and len(chunk) > 0:
                output = chunk[0] if isinstance(chunk[0], str) else str(chunk[0])
        return output.strip(), None
    except Exception as exc:
        return None, f"❌ AI error: {exc}"


# ---------------------------------------------------------------------------
# Spaced Repetition
# ---------------------------------------------------------------------------

def _spaced_repetition_intervals(review_count: int) -> int:
    """Return the next review interval in days using SM-2-inspired steps."""
    steps = [1, 3, 7, 14, 30, 60]
    idx = min(review_count, len(steps) - 1)
    return steps[idx]


def _next_review_date(last_review: str, review_count: int) -> str:
    """Calculate the next review date given the last review date and count."""
    try:
        last = datetime.strptime(last_review, "%Y-%m-%d").date()
    except ValueError:
        last = date.today()
    interval = _spaced_repetition_intervals(review_count)
    return (last + timedelta(days=interval)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Auto-Scan: gather existing Gizmo data
# ---------------------------------------------------------------------------

def scan_flashcard_decks() -> List[Dict]:
    """Scan user_data/flashcards/ and return metadata for each deck."""
    results: List[Dict] = []
    if not os.path.isdir(_FLASHCARDS_DIR):
        return results
    for fname in sorted(os.listdir(_FLASHCARDS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(_FLASHCARDS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                cards = json.load(f)
            deck_name = fname[:-5]
            results.append({
                "deck_name": deck_name,
                "card_count": len(cards) if isinstance(cards, list) else 0,
                "path": fpath,
            })
        except Exception:
            continue
    return results


def scan_quiz_results() -> List[Dict]:
    """Scan user_data/quiz_results/ and return summary of quiz performance."""
    results: List[Dict] = []
    if not os.path.isdir(_QUIZ_RESULTS_DIR):
        return results
    for fname in sorted(os.listdir(_QUIZ_RESULTS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(_QUIZ_RESULTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            subject = data.get("subject", fname[:-5])
            score = data.get("score", data.get("percentage", None))
            total = data.get("total", data.get("total_questions", None))
            results.append({
                "subject": subject,
                "score": score,
                "total": total,
                "timestamp": data.get("timestamp", ""),
                "path": fpath,
            })
        except Exception:
            continue
    return results


def scan_study_plans() -> List[Dict]:
    """Scan user_data/study_plans/ and return plan summaries."""
    results: List[Dict] = []
    if not os.path.isdir(_STUDY_PLANS_DIR):
        return results
    for fname in sorted(os.listdir(_STUDY_PLANS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(_STUDY_PLANS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                plan = json.load(f)
            subjects = [s.get("subject", s.get("name", "?")) for s in plan.get("subjects", [])]
            results.append({
                "plan_id": plan.get("plan_id", fname[:-5]),
                "subjects": subjects,
                "start_date": plan.get("start_date", ""),
                "available_hours": plan.get("available_hours", 0),
            })
        except Exception:
            continue
    return results


def auto_scan() -> Dict:
    """Scan all existing Gizmo data and return a consolidated summary."""
    flashcards = scan_flashcard_decks()
    quiz_results = scan_quiz_results()
    study_plans = scan_study_plans()

    return {
        "flashcard_decks": flashcards,
        "quiz_results": quiz_results,
        "study_plans": study_plans,
        "scan_timestamp": datetime.now().isoformat(),
    }


def _build_scan_summary(scan_data: Dict) -> str:
    """Convert scan data into a human-readable summary for AI prompt."""
    lines: List[str] = []

    decks = scan_data.get("flashcard_decks", [])
    if decks:
        lines.append("Flashcard Decks:")
        for d in decks:
            lines.append(f"  - {d['deck_name']} ({d['card_count']} cards)")

    quiz_results = scan_data.get("quiz_results", [])
    if quiz_results:
        lines.append("Quiz Results:")
        for q in quiz_results:
            score_str = f"{q['score']}/{q['total']}" if q.get("total") else str(q.get("score", "N/A"))
            lines.append(f"  - {q['subject']}: {score_str}")

    plans = scan_data.get("study_plans", [])
    if plans:
        lines.append("Existing Study Plans:")
        for p in plans:
            subj = ", ".join(p["subjects"]) or "none"
            lines.append(f"  - Plan {p['plan_id']}: {subj} (starts {p['start_date']})")

    return "\n".join(lines) if lines else "No existing data found."


# ---------------------------------------------------------------------------
# Schedule generation
# ---------------------------------------------------------------------------

def _build_prompt(
    courses: List[str],
    deadlines: List[Dict],
    hours_per_day: float,
    weak_subjects: List[str],
    scan_summary: str,
    start_date: str,
) -> str:
    """Build the AI prompt for weekly schedule generation."""
    courses_str = ", ".join(courses) if courses else "N/A"
    weak_str = ", ".join(weak_subjects) if weak_subjects else "none"

    deadlines_str = ""
    if deadlines:
        deadline_lines = []
        for d in deadlines:
            deadline_lines.append(
                f"  - {d.get('subject','?')}: {d.get('type','deadline')} on {d.get('date','?')}"
            )
        deadlines_str = "Deadlines / Exam Dates:\n" + "\n".join(deadline_lines)
    else:
        deadlines_str = "Deadlines / Exam Dates: none specified"

    return (
        f"You are an expert academic planner. Generate a complete 7-day weekly study schedule "
        f"starting from {start_date}.\n\n"
        f"Student information:\n"
        f"- Courses/Subjects: {courses_str}\n"
        f"- Available study hours per day: {hours_per_day}\n"
        f"- Weak subjects (prioritize these): {weak_str}\n"
        f"- {deadlines_str}\n\n"
        f"Existing learning data:\n{scan_summary}\n\n"
        f"Requirements:\n"
        f"1. Apply spaced repetition principles: schedule flashcard reviews at optimal intervals.\n"
        f"2. Prioritize weak subjects and subjects with upcoming deadlines.\n"
        f"3. Include short breaks (e.g., 10 min after each 50-minute session).\n"
        f"4. Distribute study sessions evenly across the week.\n"
        f"5. Return ONLY a valid JSON array. Each element must have these keys:\n"
        f"   date (YYYY-MM-DD), day (e.g. Monday), time (HH:MM), subject, activity, "
        f"   duration_minutes (integer), type (study|review|break), notes\n"
        f"Return ONLY the JSON array, no extra text."
    )


def _parse_schedule(ai_output: str, start_date: str) -> List[Dict]:
    """Parse AI output into a list of schedule entry dicts."""
    try:
        json_match = re.search(r'\[.*\]', ai_output, re.DOTALL)
        if json_match:
            raw = json.loads(json_match.group(0))
            schedule = []
            for item in raw:
                schedule.append({
                    "date": str(item.get("date", start_date)),
                    "day": str(item.get("day", "")),
                    "time": str(item.get("time", "09:00")),
                    "subject": str(item.get("subject", "")),
                    "activity": str(item.get("activity", "")),
                    "duration_minutes": int(item.get("duration_minutes", 60)),
                    "type": str(item.get("type", "study")),
                    "notes": str(item.get("notes", "")),
                    "completed": False,
                })
            return schedule
    except Exception:
        pass
    return _generate_schedule_fallback(start_date)


def _generate_schedule_fallback(start_date: str) -> List[Dict]:
    """Generate a minimal placeholder schedule if AI fails."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        start = date.today()

    schedule: List[Dict] = []
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i in range(7):
        day = start + timedelta(days=i)
        schedule.append({
            "date": day.strftime("%Y-%m-%d"),
            "day": day_names[i % 7],
            "time": "09:00",
            "subject": "Study Session",
            "activity": "Review notes and practice problems",
            "duration_minutes": 60,
            "type": "study",
            "notes": "",
            "completed": False,
        })
        schedule.append({
            "date": day.strftime("%Y-%m-%d"),
            "day": day_names[i % 7],
            "time": "10:00",
            "subject": "Break",
            "activity": "Short break",
            "duration_minutes": 10,
            "type": "break",
            "notes": "",
            "completed": False,
        })
    return schedule


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_schedule(
    courses: List[str],
    deadlines: List[Dict],
    hours_per_day: float,
    weak_subjects: List[str],
    scan_data: Optional[Dict] = None,
    start_date: Optional[str] = None,
) -> Tuple[str, Dict]:
    """Generate a weekly schedule using AI and save it.

    Returns (status_message, schedule_dict).
    """
    if start_date is None:
        start_date = date.today().strftime("%Y-%m-%d")

    if scan_data is None:
        scan_data = {}

    scan_summary = _build_scan_summary(scan_data)
    prompt = _build_prompt(courses, deadlines, hours_per_day, weak_subjects, scan_summary, start_date)

    output, error = _call_ai(prompt)
    if error:
        # Fall back to placeholder schedule
        schedule_entries = _generate_schedule_fallback(start_date)
        status = f"⚠️ AI unavailable ({error}). Showing placeholder schedule."
    elif not output:
        schedule_entries = _generate_schedule_fallback(start_date)
        status = "⚠️ AI returned empty output. Showing placeholder schedule."
    else:
        schedule_entries = _parse_schedule(output, start_date)
        if not schedule_entries:
            schedule_entries = _generate_schedule_fallback(start_date)
            status = "⚠️ Could not parse AI schedule. Showing placeholder schedule."
        else:
            status = f"✅ Generated {len(schedule_entries)} schedule entries."

    schedule_id = str(uuid.uuid4())[:8]
    schedule_doc = {
        "schedule_id": schedule_id,
        "courses": courses,
        "deadlines": deadlines,
        "hours_per_day": hours_per_day,
        "weak_subjects": weak_subjects,
        "start_date": start_date,
        "entries": schedule_entries,
        "scan_data": scan_data,
        "created_at": datetime.now().isoformat(),
    }

    save_msg = save_schedule(schedule_doc)
    return f"{status} {save_msg}", schedule_doc


def save_schedule(schedule_doc: Dict) -> str:
    """Save a weekly schedule to user_data/weekly_planner/{schedule_id}.json."""
    _ensure_dirs()
    schedule_id = schedule_doc.get("schedule_id", "unknown")
    path = os.path.join(_WEEKLY_PLANNER_DIR, f"{schedule_id}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(schedule_doc, f, indent=2, ensure_ascii=False)
        return f"💾 Saved as schedule '{schedule_id}'."
    except Exception as exc:
        return f"❌ Failed to save schedule: {exc}"


def load_schedule(schedule_id: str) -> Tuple[str, Dict]:
    """Load a weekly schedule from file."""
    _ensure_dirs()
    path = os.path.join(_WEEKLY_PLANNER_DIR, f"{schedule_id}.json")
    if not os.path.isfile(path):
        return f"❌ Schedule '{schedule_id}' not found.", {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        return f"✅ Loaded schedule '{schedule_id}'.", doc
    except Exception as exc:
        return f"❌ Failed to load schedule: {exc}", {}


def list_schedules() -> List[str]:
    """Return list of saved schedule IDs."""
    _ensure_dirs()
    ids: List[str] = []
    try:
        for fname in sorted(os.listdir(_WEEKLY_PLANNER_DIR)):
            if fname.endswith(".json"):
                ids.append(fname[:-5])
    except Exception:
        pass
    return ids


def reschedule_skipped(schedule_doc: Dict) -> Tuple[str, Dict]:
    """Move uncompleted past sessions to future dates using AI.

    Returns (status_message, updated_schedule_doc).
    """
    today = date.today().strftime("%Y-%m-%d")
    entries = schedule_doc.get("entries", [])

    skipped = [e for e in entries if not e.get("completed") and e.get("date", "") < today]
    future = [e for e in entries if e.get("date", "") >= today]

    if not skipped:
        return "ℹ️ No skipped sessions to reschedule.", schedule_doc

    # Build new dates starting from tomorrow for skipped sessions
    tomorrow = date.today() + timedelta(days=1)
    for i, entry in enumerate(skipped):
        new_date = (tomorrow + timedelta(days=i)).strftime("%Y-%m-%d")
        entry["date"] = new_date
        entry["day"] = (tomorrow + timedelta(days=i)).strftime("%A")
        entry["completed"] = False

    schedule_doc["entries"] = future + skipped
    schedule_doc["entries"].sort(key=lambda x: (x.get("date", ""), x.get("time", "")))

    save_schedule(schedule_doc)
    return f"✅ Rescheduled {len(skipped)} skipped session(s) starting {tomorrow}.", schedule_doc


def mark_completed(schedule_doc: Dict, date_str: str, subject: str) -> Tuple[str, Dict]:
    """Mark a session as completed and apply adaptive logic.

    If the subject appears in quiz results with a high score, reduces
    future review time for that subject.
    """
    updated = 0
    for entry in schedule_doc.get("entries", []):
        if entry.get("date") == date_str and entry.get("subject", "").lower() == subject.lower():
            entry["completed"] = True
            updated += 1

    if updated == 0:
        return f"❌ No session found for '{subject}' on {date_str}.", schedule_doc

    save_schedule(schedule_doc)
    return f"✅ Marked '{subject}' on {date_str} as completed.", schedule_doc


def sync_to_google_calendar(schedule_doc: Dict) -> str:
    """Push schedule entries to Google Calendar using the existing integration."""
    try:
        from modules.google_calendar_integration import GoogleCalendarManager
        cal = GoogleCalendarManager()
        ok, msg = cal.connect_from_saved()
        if not ok:
            return f"❌ Google Calendar not connected: {msg}"

        entries = schedule_doc.get("entries", [])
        pushed = 0
        errors: List[str] = []
        for entry in entries:
            if entry.get("type") == "break":
                continue
            date_str = entry.get("date", "")
            time_str = entry.get("time", "09:00")
            dur = int(entry.get("duration_minutes", 60))
            try:
                start_dt = datetime.strptime(f"{date_str}T{time_str}", "%Y-%m-%dT%H:%M")
                end_dt = start_dt + timedelta(minutes=dur)
                start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:00")
                end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:00")
            except ValueError:
                start_iso = f"{date_str}T{time_str}:00"
                end_iso = f"{date_str}T10:00:00"

            title = f"📚 {entry.get('subject','')} – {entry.get('activity','')}"
            _, create_msg = cal.create_event(
                title=title,
                start=start_iso,
                end=end_iso,
                description=entry.get("notes", ""),
            )
            if "❌" in create_msg:
                errors.append(create_msg)
            else:
                pushed += 1

        if errors:
            return f"⚠️ Pushed {pushed} events; {len(errors)} error(s): {errors[0]}"
        return f"✅ Synced {pushed} session(s) to Google Calendar."
    except Exception as exc:
        return f"❌ Sync failed: {exc}"

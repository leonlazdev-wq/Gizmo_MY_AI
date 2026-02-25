"""Study planner backend for Gizmo."""

from __future__ import annotations

import csv
import json
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

_STUDY_PLANS_DIR = os.path.join("user_data", "study_plans")


def _ensure_dirs() -> None:
    """Create user_data/study_plans/ directory if it doesn't exist."""
    os.makedirs(_STUDY_PLANS_DIR, exist_ok=True)


def _call_ai(prompt: str):
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = 1024
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


def _plan_path(plan_id: str) -> str:
    return os.path.join(_STUDY_PLANS_DIR, f"{plan_id}.json")


def _generate_schedule_ai(subjects: List[Dict], available_hours: float, start_date: str) -> List[Dict]:
    """Use AI to generate a study schedule. Falls back to a simple round-robin if AI fails."""
    subjects_text = "\n".join(
        f"- {s.get('subject','?')} (exam: {s.get('exam_date','TBD')}, "
        f"difficulty: {s.get('difficulty','medium')}, confidence: {s.get('confidence',5)}/10)"
        for s in subjects
    )
    prompt = (
        f"Create a detailed study schedule starting from {start_date}. "
        f"The student has {available_hours} hours per day available.\n\n"
        f"Subjects:\n{subjects_text}\n\n"
        "Return the schedule as a JSON array of objects with keys: "
        "date (YYYY-MM-DD), subject, topic, duration_hours, notes. "
        "Prioritize subjects with sooner exam dates and lower confidence. "
        "Return ONLY the JSON array, no extra text."
    )
    output, error = _call_ai(prompt)
    if error or not output:
        return _generate_schedule_simple(subjects, available_hours, start_date)

    # Try to parse JSON from AI output
    try:
        import re
        json_match = re.search(r'\[.*\]', output, re.DOTALL)
        if json_match:
            schedule_raw = json.loads(json_match.group(0))
            schedule = []
            for item in schedule_raw:
                schedule.append({
                    "date": str(item.get("date", start_date)),
                    "subject": str(item.get("subject", "")),
                    "topic": str(item.get("topic", "")),
                    "duration_hours": float(item.get("duration_hours", 1.0)),
                    "notes": str(item.get("notes", "")),
                    "completed": False,
                })
            return schedule
    except Exception:
        pass

    return _generate_schedule_simple(subjects, available_hours, start_date)


def _generate_schedule_simple(
    subjects: List[Dict], available_hours: float, start_date: str
) -> List[Dict]:
    """Generate a simple round-robin schedule as fallback."""
    schedule: List[Dict] = []
    if not subjects:
        return schedule

    try:
        current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        current_date = date.today()

    # Find the latest exam date to determine schedule length
    end_date = current_date + timedelta(days=30)
    for s in subjects:
        try:
            exam_dt = datetime.strptime(s.get("exam_date", ""), "%Y-%m-%d").date()
            if exam_dt > end_date:
                end_date = exam_dt
        except ValueError:
            pass

    day_count = (end_date - current_date).days
    hours_per_subject = max(0.5, round(available_hours / len(subjects), 1))

    for i in range(day_count):
        day = current_date + timedelta(days=i)
        subject = subjects[i % len(subjects)]
        schedule.append({
            "date": day.strftime("%Y-%m-%d"),
            "subject": subject.get("subject", "Study"),
            "topic": f"Review {subject.get('subject', 'topic')}",
            "duration_hours": hours_per_subject,
            "notes": "",
            "completed": False,
        })

    return schedule


def create_study_plan(
    subjects: List[Dict],
    available_hours_per_day: float,
    start_date: Optional[str] = None,
) -> Tuple[str, Dict]:
    """Create a new study plan using AI to generate the schedule."""
    if not subjects:
        return "❌ Please provide at least one subject.", {}

    if start_date is None:
        start_date = date.today().strftime("%Y-%m-%d")

    plan_id = str(uuid.uuid4())[:8]
    schedule = _generate_schedule_ai(subjects, available_hours_per_day, start_date)

    plan: Dict = {
        "plan_id": plan_id,
        "subjects": subjects,
        "available_hours": available_hours_per_day,
        "start_date": start_date,
        "schedule": schedule,
        "progress": {},
    }

    msg = save_plan(plan)
    subject_names = [s.get("subject", "?") for s in subjects]
    return (
        f"✅ Study plan '{plan_id}' created for {len(subjects)} subject(s): "
        f"{', '.join(subject_names)} ({len(schedule)} sessions).",
        plan,
    )


def save_plan(plan: Dict) -> str:
    """Save a study plan to user_data/study_plans/{plan_id}.json."""
    _ensure_dirs()
    plan_id = plan.get("plan_id", "unknown")
    try:
        with open(_plan_path(plan_id), "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        return f"✅ Plan '{plan_id}' saved."
    except Exception as exc:
        return f"❌ Failed to save plan: {exc}"


def load_plan(plan_id: str) -> Tuple[str, Dict]:
    """Load a study plan from file."""
    _ensure_dirs()
    path = _plan_path(plan_id)
    if not os.path.isfile(path):
        return f"❌ Plan '{plan_id}' not found.", {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        return f"✅ Loaded plan '{plan_id}'.", plan
    except Exception as exc:
        return f"❌ Failed to load plan: {exc}", {}


def list_plans() -> List[Tuple[str, List[str]]]:
    """Return list of (plan_id, subject_names) tuples from saved plans."""
    _ensure_dirs()
    result: List[Tuple[str, List[str]]] = []
    try:
        for fname in sorted(os.listdir(_STUDY_PLANS_DIR)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(_STUDY_PLANS_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    plan = json.load(f)
                plan_id = plan.get("plan_id", fname[:-5])
                subjects = [s.get("subject", "?") for s in plan.get("subjects", [])]
                result.append((plan_id, subjects))
            except Exception:
                continue
    except Exception:
        pass
    return result


def add_subject(
    plan_id: str,
    subject_name: str,
    exam_date: str,
    difficulty: str,
    confidence: int = 5,
) -> str:
    """Add a subject to an existing plan and save."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg

    new_subject = {
        "subject": subject_name,
        "exam_date": exam_date,
        "difficulty": difficulty,
        "confidence": confidence,
    }
    plan.setdefault("subjects", []).append(new_subject)
    return save_plan(plan) + f" Added subject '{subject_name}'."


def remove_subject(plan_id: str, subject_name: str) -> str:
    """Remove a subject from an existing plan and save."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg

    original_count = len(plan.get("subjects", []))
    plan["subjects"] = [
        s for s in plan.get("subjects", [])
        if s.get("subject", "").lower() != subject_name.lower()
    ]
    removed = original_count - len(plan["subjects"])
    if removed == 0:
        return f"❌ Subject '{subject_name}' not found in plan '{plan_id}'."

    # Also remove from schedule
    plan["schedule"] = [
        item for item in plan.get("schedule", [])
        if item.get("subject", "").lower() != subject_name.lower()
    ]
    save_plan(plan)
    return f"✅ Removed subject '{subject_name}' from plan '{plan_id}'."


def update_progress(
    plan_id: str,
    date_str: str,
    subject: str,
    completed: bool = True,
    notes: str = "",
) -> str:
    """Mark a study session as completed or pending."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg

    updated = False
    for item in plan.get("schedule", []):
        if (
            item.get("date") == date_str
            and item.get("subject", "").lower() == subject.lower()
        ):
            item["completed"] = completed
            if notes:
                item["notes"] = notes
            updated = True

    if not updated:
        return f"❌ No session found for '{subject}' on {date_str} in plan '{plan_id}'."

    progress_key = f"{date_str}_{subject}"
    plan.setdefault("progress", {})[progress_key] = {
        "completed": completed,
        "notes": notes,
        "timestamp": datetime.now().isoformat(),
    }
    save_plan(plan)
    status = "completed ✅" if completed else "pending 🔄"
    return f"✅ Marked '{subject}' on {date_str} as {status}."


def get_today_schedule(plan_id: str) -> Tuple[str, List[Dict]]:
    """Return today's scheduled sessions from the plan."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg, []

    today = date.today().strftime("%Y-%m-%d")
    sessions = [item for item in plan.get("schedule", []) if item.get("date") == today]

    if sessions:
        return f"✅ {len(sessions)} session(s) scheduled for today ({today}).", sessions
    return f"📅 No sessions scheduled for today ({today}).", []


def get_weekly_overview(plan_id: str, week_offset: int = 0) -> Tuple[str, List[Dict]]:
    """Return 7 days of schedule starting from today + week_offset*7 days."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg, []

    start = date.today() + timedelta(weeks=week_offset)
    end = start + timedelta(days=7)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    sessions = [
        item for item in plan.get("schedule", [])
        if start_str <= item.get("date", "") < end_str
    ]
    sessions.sort(key=lambda x: x.get("date", ""))
    return f"✅ {len(sessions)} session(s) for week of {start_str}.", sessions


def recalculate_plan(
    plan_id: str,
    new_available_hours: Optional[float] = None,
) -> Tuple[str, Dict]:
    """Recalculate remaining study sessions using AI."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg, {}

    if new_available_hours is not None:
        plan["available_hours"] = new_available_hours

    # Keep completed sessions, regenerate only future ones
    today = date.today().strftime("%Y-%m-%d")
    completed_sessions = [
        item for item in plan.get("schedule", [])
        if item.get("completed") or item.get("date", "") < today
    ]

    new_schedule = _generate_schedule_ai(
        plan.get("subjects", []),
        plan.get("available_hours", 2.0),
        today,
    )

    plan["schedule"] = completed_sessions + new_schedule
    save_plan(plan)
    return f"✅ Plan '{plan_id}' recalculated ({len(new_schedule)} future session(s)).", plan


def get_plan_progress(plan_id: str) -> Tuple[str, Dict]:
    """Return progress stats: total_sessions, completed, percentage, days_remaining."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg, {}

    schedule = plan.get("schedule", [])
    total = len(schedule)
    completed = sum(1 for item in schedule if item.get("completed"))
    percentage = round((completed / total * 100), 1) if total > 0 else 0.0

    # Calculate days remaining until the soonest upcoming exam
    today = date.today()
    days_remaining = None
    for s in plan.get("subjects", []):
        try:
            exam_dt = datetime.strptime(s.get("exam_date", ""), "%Y-%m-%d").date()
            delta = (exam_dt - today).days
            if days_remaining is None or delta < days_remaining:
                days_remaining = delta
        except ValueError:
            pass

    progress = {
        "total_sessions": total,
        "completed": completed,
        "percentage": percentage,
        "days_remaining": days_remaining,
    }
    return f"✅ Plan '{plan_id}': {completed}/{total} sessions done ({percentage}%).", progress


def export_plan_csv(plan_id: str, output_path: str) -> str:
    """Export a study plan schedule as a CSV file."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg

    schedule = plan.get("schedule", [])
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        fieldnames = ["date", "subject", "topic", "duration_hours", "notes", "completed"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(schedule)
        return f"✅ Exported {len(schedule)} session(s) to CSV: {output_path}"
    except Exception as exc:
        return f"❌ Failed to export CSV: {exc}"


def export_plan_ical(plan_id: str, output_path: str) -> str:
    """Export a study plan schedule as an iCal (.ics) file."""
    msg, plan = load_plan(plan_id)
    if not plan:
        return msg

    schedule = plan.get("schedule", [])

    # Try icalendar library first, fall back to manual ICS generation
    try:
        from icalendar import Calendar, Event
        from datetime import timezone

        cal = Calendar()
        cal.add("prodid", "-//Gizmo Study Planner//EN")
        cal.add("version", "2.0")

        for item in schedule:
            event = Event()
            event.add("summary", f"[Study] {item.get('subject','')} – {item.get('topic','')}")
            try:
                dt = datetime.strptime(item.get("date", ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                dt = datetime.now(tz=timezone.utc)
            event.add("dtstart", dt.date())
            event.add("dtend", dt.date() + timedelta(days=1))
            event.add("description", item.get("notes", ""))
            cal.add_component(event)

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(cal.to_ical())
        return f"✅ Exported {len(schedule)} session(s) to iCal: {output_path}"

    except ImportError:
        pass

    # Fallback: write a basic ICS manually
    try:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Gizmo Study Planner//EN",
        ]
        for item in schedule:
            raw_date = item.get("date", "")
            try:
                dt_compact = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y%m%d")
            except ValueError:
                dt_compact = datetime.now().strftime("%Y%m%d")

            try:
                next_day = (datetime.strptime(raw_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
            except ValueError:
                next_day = dt_compact

            uid = str(uuid.uuid4())
            summary = f"[Study] {item.get('subject','')} - {item.get('topic','')}".replace("\n", " ")
            desc = item.get("notes", "").replace("\n", " ")
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART;VALUE=DATE:{dt_compact}",
                f"DTEND;VALUE=DATE:{next_day}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{desc}",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\r\n".join(lines) + "\r\n")
        return f"✅ Exported {len(schedule)} session(s) to iCal (basic): {output_path}"
    except Exception as exc:
        return f"❌ Failed to export iCal: {exc}"

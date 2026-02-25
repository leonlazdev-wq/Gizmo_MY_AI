"""Collaborative Study backend for Gizmo."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

_STUDY_ROOMS_DIR = os.path.join("user_data", "study_rooms")
_ROOM_EXPIRY_HOURS = 24


def _ensure_dirs() -> None:
    """Create user_data/study_rooms/ directory if it doesn't exist."""
    os.makedirs(_STUDY_ROOMS_DIR, exist_ok=True)


def _call_ai(prompt: str) -> Tuple[Optional[str], Optional[str]]:
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


def _room_path(room_code: str) -> str:
    return os.path.join(_STUDY_ROOMS_DIR, f"{room_code}.json")


def _load_room(room_code: str) -> Optional[Dict]:
    path = _room_path(room_code)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_room(room: Dict) -> None:
    _ensure_dirs()
    path = _room_path(room["code"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(room, f, indent=2, ensure_ascii=False)


def _is_expired(room: Dict) -> bool:
    last_active = room.get("last_active", room.get("created_at", ""))
    if not last_active:
        return False
    try:
        last_dt = datetime.fromisoformat(last_active)
        return datetime.now() - last_dt > timedelta(hours=_ROOM_EXPIRY_HOURS)
    except Exception:
        return False


def create_room(name: str, creator: str = "You") -> Tuple[str, Optional[str]]:
    """Create a new study room. Returns (room_code, error)."""
    _ensure_dirs()
    if not name.strip():
        return "", "❌ Please enter a room name."
    code = str(uuid.uuid4())[:6].upper()
    room = {
        "code": code,
        "name": name.strip(),
        "creator": creator,
        "created_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat(),
        "participants": [creator],
        "chat": [],
        "quiz": None,
        "quiz_answers": {},
        "flashcard_deck": None,
        "mode": "discussion",
    }
    _save_room(room)
    return code, None


def join_room(room_code: str, participant: str = "Guest") -> Tuple[Optional[Dict], Optional[str]]:
    """Join an existing room. Returns (room_data, error)."""
    room = _load_room(room_code.upper().strip())
    if room is None:
        return None, f"❌ Room '{room_code}' not found."
    if _is_expired(room):
        return None, "❌ This room has expired (24h inactivity)."
    if participant not in room["participants"]:
        room["participants"].append(participant)
    room["last_active"] = datetime.now().isoformat()
    _save_room(room)
    return room, None


def send_chat_message(room_code: str, sender: str, message: str) -> Tuple[List[Dict], Optional[str]]:
    """Send a chat message to the room. Returns (chat_history, error)."""
    if not message.strip():
        return [], "❌ Empty message."
    room = _load_room(room_code.upper().strip())
    if room is None:
        return [], f"❌ Room '{room_code}' not found."
    entry = {
        "sender": sender,
        "message": message.strip(),
        "timestamp": datetime.now().isoformat(),
    }
    room.setdefault("chat", []).append(entry)
    room["last_active"] = datetime.now().isoformat()
    _save_room(room)
    return room["chat"], None


def start_quiz(room_code: str, topic: str, num_questions: int = 5) -> Tuple[Optional[Dict], Optional[str]]:
    """Generate a quiz for the room. Returns (quiz_data, error)."""
    room = _load_room(room_code.upper().strip())
    if room is None:
        return None, f"❌ Room '{room_code}' not found."

    prompt = (
        f"Generate {num_questions} quiz questions about: {topic}\n"
        "For each question use the format:\n"
        "Q: <question>\n"
        "A) <option1>\n"
        "B) <option2>\n"
        "C) <option3>\n"
        "D) <option4>\n"
        "Answer: <letter>\n\n"
        "Return only the questions in that format."
    )
    output, error = _call_ai(prompt)
    if error:
        return None, error

    questions = _parse_quiz(output or "")
    if not questions:
        return None, "⚠️ Could not parse quiz questions. Try again."

    quiz = {
        "topic": topic,
        "questions": questions,
        "started_at": datetime.now().isoformat(),
        "current_question": 0,
    }
    room["quiz"] = quiz
    room["quiz_answers"] = {}
    room["mode"] = "quiz"
    room["last_active"] = datetime.now().isoformat()
    _save_room(room)
    return quiz, None


def _parse_quiz(output: str) -> List[Dict]:
    """Parse AI quiz output into question dicts."""
    import re
    questions = []
    blocks = re.split(r'\nQ:', output)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        q_text = lines[0].strip()
        options = {}
        answer = ""
        for line in lines[1:]:
            opt_match = re.match(r'^([A-Da-d])\)\s*(.+)', line.strip())
            if opt_match:
                options[opt_match.group(1).upper()] = opt_match.group(2).strip()
            ans_match = re.match(r'^Answer:\s*([A-Da-d])', line.strip(), re.IGNORECASE)
            if ans_match:
                answer = ans_match.group(1).upper()
        if q_text and options:
            questions.append({
                "question": q_text,
                "options": options,
                "answer": answer,
            })
    return questions


def submit_answer(
    room_code: str, participant: str, question_index: int, answer: str
) -> Tuple[bool, str]:
    """Submit an answer. Returns (correct, feedback)."""
    room = _load_room(room_code.upper().strip())
    if room is None:
        return False, f"❌ Room '{room_code}' not found."
    quiz = room.get("quiz")
    if not quiz:
        return False, "❌ No active quiz."
    questions = quiz.get("questions", [])
    if question_index >= len(questions):
        return False, "❌ Invalid question index."
    q = questions[question_index]
    correct = answer.upper().strip() == q.get("answer", "").upper().strip()
    room.setdefault("quiz_answers", {})
    room["quiz_answers"].setdefault(participant, [])
    room["quiz_answers"][participant].append({
        "question_index": question_index,
        "answer": answer,
        "correct": correct,
    })
    room["last_active"] = datetime.now().isoformat()
    _save_room(room)
    feedback = "✅ Correct!" if correct else f"❌ Incorrect. Correct answer: {q.get('answer', '?')}"
    return correct, feedback


def get_scoreboard(room_code: str) -> Dict[str, int]:
    """Return scores for all participants."""
    room = _load_room(room_code.upper().strip())
    if room is None:
        return {}
    scores: Dict[str, int] = {}
    for participant, answers in room.get("quiz_answers", {}).items():
        scores[participant] = sum(1 for a in answers if a.get("correct"))
    return scores


def share_flashcard_deck(room_code: str, deck_name: str) -> Tuple[Optional[List], Optional[str]]:
    """Share a flashcard deck in the room. Returns (cards, error)."""
    from modules.flashcard_generator import load_deck
    room = _load_room(room_code.upper().strip())
    if room is None:
        return None, f"❌ Room '{room_code}' not found."
    msg, cards = load_deck(deck_name)
    if not cards:
        return None, msg
    room["flashcard_deck"] = {"name": deck_name, "cards": cards}
    room["mode"] = "flashcards"
    room["last_active"] = datetime.now().isoformat()
    _save_room(room)
    return cards, None


def get_room_info(room_code: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Get room info. Returns (room, error)."""
    room = _load_room(room_code.upper().strip())
    if room is None:
        return None, f"❌ Room '{room_code}' not found."
    if _is_expired(room):
        return None, "❌ This room has expired (24h inactivity)."
    return room, None


def list_active_rooms() -> List[Dict]:
    """List all non-expired rooms."""
    _ensure_dirs()
    rooms = []
    try:
        for fname in os.listdir(_STUDY_ROOMS_DIR):
            if fname.endswith(".json"):
                room = _load_room(fname[:-5])
                if room and not _is_expired(room):
                    rooms.append(room)
    except Exception:
        pass
    return sorted(rooms, key=lambda r: r.get("created_at", ""), reverse=True)


def get_session_summary(room_code: str) -> str:
    """Generate a session summary for the room's quiz."""
    room = _load_room(room_code.upper().strip())
    if room is None:
        return f"❌ Room '{room_code}' not found."
    quiz = room.get("quiz")
    if not quiz:
        return "No quiz has been run in this room."
    answers = room.get("quiz_answers", {})
    questions = quiz.get("questions", [])
    total_q = len(questions)
    lines = [f"**Session Summary — {quiz.get('topic', 'Quiz')}**\n"]
    if not answers:
        lines.append("No answers submitted yet.")
        return "\n".join(lines)

    scores = get_scoreboard(room_code)
    all_scores = list(scores.values())
    avg = sum(all_scores) / len(all_scores) if all_scores else 0
    lines.append(f"Participants: {len(answers)}")
    lines.append(f"Average score: {avg:.1f} / {total_q}")
    lines.append("")
    for participant, score in sorted(scores.items(), key=lambda x: -x[1]):
        lines.append(f"- {participant}: {score}/{total_q}")

    # Find hardest questions
    if total_q > 0:
        wrong_counts = [0] * total_q
        for participant_answers in answers.values():
            for a in participant_answers:
                idx = a.get("question_index", -1)
                if 0 <= idx < total_q and not a.get("correct"):
                    wrong_counts[idx] += 1
        hardest_idx = sorted(range(total_q), key=lambda i: -wrong_counts[i])[:3]
        if any(wrong_counts[i] > 0 for i in hardest_idx):
            lines.append("\n**Hardest Questions:**")
            for idx in hardest_idx:
                if wrong_counts[idx] > 0:
                    q_text = questions[idx].get("question", "")
                    lines.append(f"- Q{idx+1}: {q_text} ({wrong_counts[idx]} wrong)")

    return "\n".join(lines)

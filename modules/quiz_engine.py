"""Quiz engine backend for Gizmo."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

_QUIZ_RESULTS_DIR = os.path.join("user_data", "quiz_results")
_DEFAULT_QUESTION_TYPES = ["multiple_choice", "true_false", "short_answer"]


def _ensure_dirs() -> None:
    """Create user_data/quiz_results/ directory if it doesn't exist."""
    os.makedirs(_QUIZ_RESULTS_DIR, exist_ok=True)


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


def _parse_questions(ai_output: str) -> List[Dict]:
    """Parse AI output into a list of question dicts."""
    questions: List[Dict] = []
    blocks = re.split(r'\n(?=\d+[\.\)])', ai_output.strip())

    for block in blocks:
        if not block.strip():
            continue

        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        question_text = re.sub(r'^\d+[\.\)]\s*', '', lines[0]).strip()
        options: List[str] = []
        correct_answer = ""
        explanation = ""
        q_type = "short_answer"

        for line in lines[1:]:
            lower = line.lower()
            if lower.startswith(("a)", "b)", "c)", "d)", "a.", "b.", "c.", "d.")):
                options.append(line)
                q_type = "multiple_choice"
            elif lower.startswith(("answer:", "correct:", "correct answer:")):
                correct_answer = line.split(":", 1)[1].strip()
            elif lower.startswith("explanation:"):
                explanation = line.split(":", 1)[1].strip()
            elif lower in ("true", "false", "true.", "false."):
                q_type = "true_false"
                if not correct_answer:
                    correct_answer = line.rstrip(".")

        if question_text:
            questions.append({
                "question": question_text,
                "type": q_type,
                "options": options if options else None,
                "correct_answer": correct_answer,
                "explanation": explanation,
            })

    return questions


def generate_quiz(
    topic: str,
    num_questions: int = 10,
    question_types: Optional[List[str]] = None,
    difficulty: str = "medium",
) -> Tuple[str, List[Dict]]:
    """Generate quiz questions on a topic using AI."""
    if question_types is None:
        question_types = _DEFAULT_QUESTION_TYPES

    types_str = ", ".join(question_types)
    prompt = (
        f"Generate {num_questions} quiz questions about '{topic}'. "
        f"Include these question types: {types_str}. "
        f"Difficulty: {difficulty}.\n\n"
        "For each question use this format:\n"
        "1. <question text>\n"
        "A) <option> B) <option> C) <option> D) <option>  (for multiple choice)\n"
        "Answer: <correct answer>\n"
        "Explanation: <brief explanation>\n\n"
        "Number each question. For true/false, just provide True or False as the answer."
    )
    output, error = _call_ai(prompt)
    if error:
        return error, []

    questions = _parse_questions(output)
    if not questions:
        return "⚠️ Could not parse questions from AI output. Try again.", []

    return f"✅ Generated {len(questions)} question(s) on '{topic}'.", questions


def generate_quiz_from_text(text: str, num_questions: int = 10) -> Tuple[str, List[Dict]]:
    """Generate quiz questions from provided text."""
    prompt = (
        f"Generate {num_questions} quiz questions based on the following text. "
        "Mix question types (multiple choice, true/false, short answer). "
        "Format:\n1. <question>\nA) ... B) ... C) ... D) ...\nAnswer: <answer>\nExplanation: <explanation>\n\n"
        f"Text:\n{text[:4000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, []

    questions = _parse_questions(output)
    if not questions:
        return "⚠️ Could not parse questions from AI output. Try again.", []

    return f"✅ Generated {len(questions)} question(s) from text.", questions


def generate_quiz_from_flashcards(flashcard_set: List[Dict]) -> Tuple[str, List[Dict]]:
    """Convert a list of flashcard dicts into quiz questions."""
    questions: List[Dict] = []
    for card in flashcard_set:
        front = card.get("front", "")
        back = card.get("back", "")
        if front and back:
            questions.append({
                "question": front,
                "type": "short_answer",
                "options": None,
                "correct_answer": back,
                "explanation": "",
            })
    if not questions:
        return "❌ No valid flashcards to convert.", []
    return f"✅ Converted {len(questions)} flashcard(s) to quiz questions.", questions


def check_answer(question_dict: Dict, user_answer: str) -> Tuple[bool, str]:
    """Check a user's answer against the correct answer. Returns (is_correct, feedback)."""
    correct = (question_dict.get("correct_answer") or "").strip().lower()
    given = (user_answer or "").strip().lower()
    explanation = question_dict.get("explanation", "")

    if not correct:
        # Fall back to AI grading if no stored answer
        prompt = (
            f"Question: {question_dict.get('question', '')}\n"
            f"Correct answer: (unknown)\n"
            f"User answer: {user_answer}\n"
            "Is the user's answer correct? Reply with 'Correct' or 'Incorrect' and a brief explanation."
        )
        output, error = _call_ai(prompt)
        if error:
            return False, error
        is_correct = output.lower().startswith("correct")
        return is_correct, output

    q_type = question_dict.get("type", "short_answer")

    if q_type in ("multiple_choice", "true_false"):
        is_correct = correct == given or correct.startswith(given) or given.startswith(correct)
    else:
        # For short answer: check if the key words match
        correct_words = set(correct.split())
        given_words = set(given.split())
        overlap = len(correct_words & given_words)
        is_correct = overlap >= max(1, len(correct_words) * 0.5)

    if is_correct:
        feedback = f"✅ Correct! {explanation}".strip()
    else:
        feedback = f"❌ Incorrect. The correct answer is: {question_dict.get('correct_answer', '')}. {explanation}".strip()

    return is_correct, feedback


def calculate_score(results: List[Tuple[Dict, str, bool]]) -> Dict:
    """Calculate score from a list of (question_dict, user_answer, is_correct) tuples."""
    total = len(results)
    correct_count = sum(1 for _, _, is_correct in results if is_correct)
    percentage = round((correct_count / total * 100), 1) if total > 0 else 0.0
    return {
        "score": correct_count,
        "total": total,
        "percentage": percentage,
    }


def save_quiz_result(
    quiz_id: str,
    topic: str,
    score_dict: Dict,
    timestamp: Optional[str] = None,
) -> str:
    """Save a quiz result to user_data/quiz_results/."""
    _ensure_dirs()
    if timestamp is None:
        timestamp = datetime.now().isoformat()

    result = {
        "quiz_id": quiz_id,
        "topic": topic,
        "timestamp": timestamp,
        **score_dict,
    }
    file_path = os.path.join(_QUIZ_RESULTS_DIR, f"{quiz_id}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return f"✅ Quiz result saved: {quiz_id} ({score_dict.get('percentage', 0)}%)."
    except Exception as exc:
        return f"❌ Failed to save result: {exc}"


def get_leaderboard(topic: Optional[str] = None) -> List[Dict]:
    """Load all results, optionally filter by topic, sort by percentage descending."""
    _ensure_dirs()
    results: List[Dict] = []
    try:
        for fname in os.listdir(_QUIZ_RESULTS_DIR):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(_QUIZ_RESULTS_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if topic is None or data.get("topic", "").lower() == topic.lower():
                    results.append(data)
            except Exception:
                continue
    except Exception:
        pass

    results.sort(key=lambda x: x.get("percentage", 0), reverse=True)
    return results


def get_user_progress(user_id: str = "default") -> Dict:
    """Return user progress: history, average score, weak topics."""
    all_results = get_leaderboard()
    if not all_results:
        return {
            "user_id": user_id,
            "history": [],
            "average_score": 0.0,
            "weak_topics": [],
        }

    topic_scores: Dict[str, List[float]] = {}
    for r in all_results:
        topic = r.get("topic", "Unknown")
        pct = r.get("percentage", 0.0)
        topic_scores.setdefault(topic, []).append(pct)

    avg = round(sum(r.get("percentage", 0) for r in all_results) / len(all_results), 1)
    weak_topics = [
        t for t, scores in topic_scores.items() if sum(scores) / len(scores) < 60.0
    ]

    return {
        "user_id": user_id,
        "history": all_results,
        "average_score": avg,
        "weak_topics": weak_topics,
    }


def list_saved_quizzes() -> List[str]:
    """Return a list of saved quiz result file names."""
    _ensure_dirs()
    try:
        return sorted(
            f for f in os.listdir(_QUIZ_RESULTS_DIR) if f.endswith(".json")
        )
    except Exception:
        return []

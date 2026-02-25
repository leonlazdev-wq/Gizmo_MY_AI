"""Math/Science Solver backend for Gizmo."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

_SOLUTIONS_DIR = os.path.join("user_data", "math_solutions")

SUBJECTS = [
    "General",
    "Algebra",
    "Geometry",
    "Trigonometry",
    "Calculus",
    "Statistics",
    "Linear Algebra",
    "Differential Equations",
    "Physics",
    "Chemistry",
    "Biology",
    "Computer Science",
]


def _ensure_dirs() -> None:
    os.makedirs(_SOLUTIONS_DIR, exist_ok=True)


def _call_ai(prompt: str, max_tokens: int = 2048):
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = max_tokens
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


def solve_problem(
    problem: str,
    subject: str = "General",
    image_path: Optional[str] = None,
) -> Tuple[str, Dict]:
    """Solve a math/science problem with step-by-step explanation."""
    if not problem or not problem.strip():
        if image_path is None:
            return "❌ Please enter a problem or upload an image.", {}

    img_hint = ""
    if image_path:
        img_hint = (
            "\nAn image of the problem has been provided. "
            "Describe and solve the problem shown in the image."
        )

    prompt = (
        f"You are an expert {subject} tutor. Solve the following problem with clear, "
        f"numbered step-by-step reasoning. Show all work. "
        f"Use standard mathematical notation (you may use LaTeX in $...$ for inline or $$...$$ for display math).\n\n"
        f"Problem: {problem}{img_hint}\n\n"
        "Format your response as:\n"
        "SOLUTION:\n"
        "Step 1: ...\n"
        "Step 2: ...\n"
        "(and so on)\n\n"
        "FINAL ANSWER: ...\n"
    )
    output, error = _call_ai(prompt, max_tokens=2048)
    if error:
        return error, {}

    solution = {
        "problem": problem,
        "subject": subject,
        "solution": output,
        "timestamp": datetime.now().isoformat(),
    }
    return "✅ Problem solved.", solution


def explain_further(solution_text: str, step: str = "") -> Tuple[str, str]:
    """Ask AI to explain a step or the solution in more detail."""
    if not solution_text:
        return "❌ No solution to explain.", ""

    focus = f" Specifically explain this part in more detail: {step}" if step else ""
    prompt = (
        f"The following is a math/science solution. Please explain it in more depth, "
        f"clarifying each step and the reasoning behind it.{focus}\n\n"
        f"SOLUTION:\n{solution_text[:3000]}"
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Explanation generated.", output


def generate_similar_problems(problem: str, subject: str = "General") -> Tuple[str, str]:
    """Generate 3-5 similar practice problems."""
    if not problem:
        return "❌ No problem provided.", ""

    prompt = (
        f"Based on the following {subject} problem, generate 5 similar practice problems "
        f"with varying difficulty. For each, provide the problem statement and the final answer.\n\n"
        f"Original problem: {problem}\n\n"
        "Format as a numbered list."
    )
    output, error = _call_ai(prompt)
    if error:
        return error, ""
    return "✅ Similar problems generated.", output


def save_solution(solution: Dict) -> str:
    """Save a solution to user_data/math_solutions/."""
    _ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(_SOLUTIONS_DIR, f"solution_{timestamp}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(solution, f, indent=2, ensure_ascii=False)
        return f"✅ Solution saved to {file_path}."
    except Exception as exc:
        return f"❌ Failed to save solution: {exc}"


def list_solutions() -> List[str]:
    """Return a list of saved solution filenames (without extension)."""
    _ensure_dirs()
    try:
        files = [f for f in os.listdir(_SOLUTIONS_DIR) if f.endswith(".json")]
        return [os.path.splitext(f)[0] for f in sorted(files, reverse=True)]
    except Exception:
        return []


def load_solution(name: str) -> Tuple[str, Dict]:
    """Load a saved solution by name."""
    _ensure_dirs()
    file_path = os.path.join(_SOLUTIONS_DIR, f"{name}.json")
    if not os.path.isfile(file_path):
        return f"❌ Solution '{name}' not found.", {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return f"✅ Loaded solution.", data
    except Exception as exc:
        return f"❌ Failed to load solution: {exc}", {}

"""Gradio UI tab for the Quiz Mode."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.quiz_engine import (
    calculate_score,
    check_answer,
    generate_quiz,
    generate_quiz_from_text,
    get_leaderboard,
    list_saved_quizzes,
    save_quiz_result,
)

TUTORIAL_URL = "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#quiz-mode"

_current_quiz: list = []
_current_q_index: int = 0
_results: list = []


def _question_counter() -> str:
    if not _current_quiz:
        return "No quiz loaded"
    return f"Question {_current_q_index + 1} / {len(_current_quiz)}"


def _question_data(idx) -> dict:
    return _current_quiz[idx] if _current_quiz else {}


def _start_quiz(topic, num_q, difficulty):
    global _current_quiz, _current_q_index, _results
    msg, quiz = generate_quiz(topic, int(num_q), difficulty=difficulty)
    _current_quiz = quiz or []
    _current_q_index = 0
    _results = []
    if not _current_quiz:
        return msg, "", gr.update(choices=[], value=None), gr.update(visible=True), _question_counter()
    q = _question_data(0)
    question_text = q.get("question", "")
    options = q.get("options", [])
    return (
        msg,
        question_text,
        gr.update(choices=options, value=None),
        gr.update(visible=bool(options), value=""),
        _question_counter(),
    )


def _submit_answer(user_answer):
    global _results
    if not _current_quiz or _current_q_index >= len(_current_quiz):
        return "No active quiz.", gr.update(visible=False)
    q = _question_data(_current_q_index)
    feedback, correct = check_answer(q, user_answer)
    _results.append({"question": q, "user_answer": user_answer, "correct": correct})
    is_last = _current_q_index >= len(_current_quiz) - 1
    next_label = "✅ Show Results" if is_last else "▶ Next Question"
    return feedback, gr.update(visible=True, value=next_label)


def _next_question():
    global _current_q_index
    if not _current_quiz:
        return "No quiz loaded", gr.update(choices=[], value=None), "", _question_counter(), ""

    _current_q_index += 1

    if _current_q_index >= len(_current_quiz):
        results_text = _show_results()
        return (
            "Quiz complete! See Results tab.",
            gr.update(choices=[], value=None),
            "",
            f"Question {len(_current_quiz)} / {len(_current_quiz)}",
            results_text,
        )

    q = _question_data(_current_q_index)
    question_text = q.get("question", "")
    options = q.get("options", [])
    return (
        question_text,
        gr.update(choices=options, value=None),
        "",
        _question_counter(),
        "",
    )


def _show_results() -> str:
    if not _results:
        return "No results yet."
    score_data = calculate_score(_results)
    if isinstance(score_data, dict):
        score = score_data.get("score", 0)
        total = score_data.get("total", len(_results))
        pct = score_data.get("percentage", 0)
        lines = [f"**Score: {score}/{total} ({pct:.0f}%)**", ""]
        for i, r in enumerate(_results, 1):
            q_text = r["question"].get("question", "")
            correct_ans = r["question"].get("answer", r["question"].get("correct_answer", ""))
            status = "✅" if r.get("correct") else "❌"
            lines.append(f"{status} Q{i}: {q_text}")
            lines.append(f"   Your answer: {r['user_answer']}")
            if not r.get("correct"):
                lines.append(f"   Correct: {correct_ans}")
        return "\n".join(lines)
    return str(score_data)


def _get_leaderboard(topic=""):
    results = get_leaderboard(topic or None)
    if not results:
        return "No leaderboard data available."
    if isinstance(results, list) and results:
        header = "| Rank | Player | Score | Topic |\n|------|--------|-------|-------|"
        rows = [
            f"| {i+1} | {r.get('player','?')} | {r.get('score','?')} | {r.get('topic','?')} |"
            for i, r in enumerate(results)
        ]
        return header + "\n" + "\n".join(rows)
    return str(results)


def create_ui():
    with gr.Tab("📝 Quiz Mode", elem_id="quiz-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: How to use Quiz Mode</a>"
            f"</div>"
        )

        with gr.Accordion("⚙️ Quiz Setup", open=True):
            shared.gradio['quiz_topic'] = gr.Textbox(
                label="Topic", placeholder="e.g. Python programming"
            )
            with gr.Row():
                shared.gradio['quiz_num_questions'] = gr.Slider(
                    minimum=5, maximum=30, value=10, step=1, label="Number of questions"
                )
                shared.gradio['quiz_difficulty'] = gr.Dropdown(
                    label="Difficulty",
                    choices=["easy", "medium", "hard"],
                    value="medium",
                )
            shared.gradio['quiz_start_btn'] = gr.Button("🚀 Start Quiz", variant="primary")
            shared.gradio['quiz_setup_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("❓ Quiz Interface", open=False):
            shared.gradio['quiz_counter'] = gr.Markdown("No quiz loaded")
            shared.gradio['quiz_question_display'] = gr.Textbox(
                label="Question", lines=3, interactive=False
            )
            shared.gradio['quiz_options'] = gr.Radio(
                label="Options", choices=[], interactive=True
            )
            shared.gradio['quiz_short_answer'] = gr.Textbox(
                label="Your answer",
                placeholder="Type your answer...",
                visible=True,
            )
            shared.gradio['quiz_submit_btn'] = gr.Button("✅ Submit Answer", variant="primary")
            shared.gradio['quiz_feedback'] = gr.Textbox(
                label="Feedback", lines=3, interactive=False
            )
            shared.gradio['quiz_next_btn'] = gr.Button("▶ Next Question", visible=False)

        with gr.Accordion("📊 Results", open=False):
            shared.gradio['quiz_results_display'] = gr.Textbox(
                label="Quiz Results", lines=10, interactive=False
            )
            shared.gradio['quiz_retake_btn'] = gr.Button("🔄 Retake Quiz")

        with gr.Accordion("🏆 Leaderboard", open=False):
            with gr.Row():
                shared.gradio['quiz_lb_topic'] = gr.Textbox(
                    label="Filter by topic (optional)",
                    placeholder="Filter by topic (optional)",
                )
                shared.gradio['quiz_lb_btn'] = gr.Button("🔍 View Leaderboard")
            shared.gradio['quiz_leaderboard_display'] = gr.Textbox(
                label="Leaderboard", lines=8, interactive=False
            )


def create_event_handlers():
    shared.gradio['quiz_start_btn'].click(
        _start_quiz,
        inputs=[
            shared.gradio['quiz_topic'],
            shared.gradio['quiz_num_questions'],
            shared.gradio['quiz_difficulty'],
        ],
        outputs=[
            shared.gradio['quiz_setup_status'],
            shared.gradio['quiz_question_display'],
            shared.gradio['quiz_options'],
            shared.gradio['quiz_short_answer'],
            shared.gradio['quiz_counter'],
        ],
        show_progress=True,
    )

    shared.gradio['quiz_submit_btn'].click(
        _submit_answer,
        inputs=[shared.gradio['quiz_short_answer']],
        outputs=[shared.gradio['quiz_feedback'], shared.gradio['quiz_next_btn']],
        show_progress=False,
    )

    shared.gradio['quiz_next_btn'].click(
        _next_question,
        inputs=[],
        outputs=[
            shared.gradio['quiz_question_display'],
            shared.gradio['quiz_options'],
            shared.gradio['quiz_short_answer'],
            shared.gradio['quiz_counter'],
            shared.gradio['quiz_results_display'],
        ],
        show_progress=False,
    )

    shared.gradio['quiz_retake_btn'].click(
        _start_quiz,
        inputs=[
            shared.gradio['quiz_topic'],
            shared.gradio['quiz_num_questions'],
            shared.gradio['quiz_difficulty'],
        ],
        outputs=[
            shared.gradio['quiz_setup_status'],
            shared.gradio['quiz_question_display'],
            shared.gradio['quiz_options'],
            shared.gradio['quiz_short_answer'],
            shared.gradio['quiz_counter'],
        ],
        show_progress=True,
    )

    shared.gradio['quiz_lb_btn'].click(
        _get_leaderboard,
        inputs=[shared.gradio['quiz_lb_topic']],
        outputs=[shared.gradio['quiz_leaderboard_display']],
        show_progress=False,
    )

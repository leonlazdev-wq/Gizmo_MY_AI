"""Gradio UI tab for the Math/Science Solver."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.math_solver import (
    SUBJECTS,
    explain_further,
    generate_similar_problems,
    list_solutions,
    load_solution,
    save_solution,
    solve_problem,
)

_current_solution: dict = {}


def _solve_fn(problem, subject, image_obj):
    global _current_solution
    image_path = None
    if image_obj is not None:
        image_path = image_obj if isinstance(image_obj, str) else getattr(image_obj, "name", None)

    status, sol = solve_problem(problem, subject, image_path)
    if sol:
        _current_solution = sol
    solution_text = sol.get("solution", "") if sol else ""
    return status, solution_text, gr.update(choices=list_solutions())


def _explain_fn(step_text):
    solution_text = _current_solution.get("solution", "")
    if not solution_text:
        return "❌ Solve a problem first."
    status, result = explain_further(solution_text, step_text)
    return result or status


def _similar_fn():
    problem = _current_solution.get("problem", "")
    subject = _current_solution.get("subject", "General")
    if not problem:
        return "❌ Solve a problem first."
    status, result = generate_similar_problems(problem, subject)
    return result or status


def _save_fn():
    if not _current_solution:
        return "❌ No solution to save."
    return save_solution(_current_solution)


def _load_fn(name):
    global _current_solution
    if not name:
        return "No solution selected.", "", ""
    status, sol = load_solution(name)
    if sol:
        _current_solution = sol
    return status, sol.get("problem", ""), sol.get("solution", "")


def _refresh_fn():
    return gr.update(choices=list_solutions())


def create_ui():
    with gr.Tab("🧮 Math Solver", elem_id="math-solver-tab"):
        with gr.Accordion("📥 Problem Input", open=True):
            shared.gradio['ms_problem'] = gr.Textbox(
                label="Problem",
                lines=4,
                placeholder="Type your math or science problem here...\ne.g. Solve for x: 2x² + 5x - 3 = 0",
            )
            with gr.Row():
                shared.gradio['ms_subject'] = gr.Dropdown(
                    label="Subject",
                    choices=SUBJECTS,
                    value="General",
                )
                shared.gradio['ms_image'] = gr.Image(
                    label="Upload problem image (optional)",
                    type="filepath",
                )
            shared.gradio['ms_solve_btn'] = gr.Button("🧮 Solve", variant="primary")
            shared.gradio['ms_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📝 Solution", open=True):
            shared.gradio['ms_solution'] = gr.Textbox(
                label="Step-by-Step Solution",
                lines=12,
                interactive=False,
            )
            with gr.Row():
                shared.gradio['ms_explain_btn'] = gr.Button("🔍 Explain Further")
                shared.gradio['ms_similar_btn'] = gr.Button("📝 Similar Problems")
            shared.gradio['ms_explain_input'] = gr.Textbox(
                label="Which step to explain? (optional)",
                placeholder="e.g. Step 3 or 'the factoring step'",
            )
            shared.gradio['ms_extra_output'] = gr.Textbox(
                label="Additional Output",
                lines=8,
                interactive=False,
            )

        with gr.Accordion("💾 History", open=False):
            shared.gradio['ms_solution_selector'] = gr.Dropdown(
                label="Load Previous Solution",
                choices=list_solutions(),
                interactive=True,
            )
            with gr.Row():
                shared.gradio['ms_load_btn'] = gr.Button("📂 Load")
                shared.gradio['ms_save_btn'] = gr.Button("💾 Save Current")
                shared.gradio['ms_refresh_btn'] = gr.Button("🔄 Refresh")
            shared.gradio['ms_history_status'] = gr.Textbox(label="Status", interactive=False)


def create_event_handlers():
    shared.gradio['ms_solve_btn'].click(
        _solve_fn,
        inputs=[
            shared.gradio['ms_problem'],
            shared.gradio['ms_subject'],
            shared.gradio['ms_image'],
        ],
        outputs=[
            shared.gradio['ms_status'],
            shared.gradio['ms_solution'],
            shared.gradio['ms_solution_selector'],
        ],
        show_progress=True,
    )

    shared.gradio['ms_explain_btn'].click(
        _explain_fn,
        inputs=[shared.gradio['ms_explain_input']],
        outputs=[shared.gradio['ms_extra_output']],
        show_progress=True,
    )

    shared.gradio['ms_similar_btn'].click(
        _similar_fn,
        inputs=[],
        outputs=[shared.gradio['ms_extra_output']],
        show_progress=True,
    )

    shared.gradio['ms_save_btn'].click(
        _save_fn,
        inputs=[],
        outputs=[shared.gradio['ms_history_status']],
        show_progress=True,
    )

    shared.gradio['ms_load_btn'].click(
        _load_fn,
        inputs=[shared.gradio['ms_solution_selector']],
        outputs=[
            shared.gradio['ms_history_status'],
            shared.gradio['ms_problem'],
            shared.gradio['ms_solution'],
        ],
        show_progress=True,
    )

    shared.gradio['ms_refresh_btn'].click(
        _refresh_fn,
        inputs=[],
        outputs=[shared.gradio['ms_solution_selector']],
        show_progress=False,
    )

"""Launch-time UX helpers: what's new modal, demo CTA, tour, demo data."""

from __future__ import annotations

import json

import gradio as gr

from modules import shared
from modules.demo_data import seed_demo_data
from modules.feature_workflows import ensure_demo_workflow, run_workflow_path
from modules.tour import get_tour_state, mark_tour_completed
from modules.utils import gradio


def create_ui() -> None:
    """Render launch-visible overlays and CTA controls."""
    # Visual mock: [What's New modal] + floating [Run demo] [Feedback]
    shared.gradio['launch_session_id'] = gr.Textbox(value='default_session', visible=False)
    shared.gradio['launch_demo_input'] = gr.Textbox(value='Explain photosynthesis for grade 7', visible=False)

    shared.gradio['run_demo_cta'] = gr.Button('▶ Run demo', elem_id='run-demo-cta', visible=False)
    shared.gradio['feedback_cta_open'] = gr.Button('✎ Feedback', elem_id='feedback-cta', visible=False)

    with gr.Group(visible=False, elem_id='whats-new-modal') as shared.gradio['whats_new_modal']:
        gr.Markdown("### ✨ What's new in Gizmo\n- Guided tour\n- One-click demo workflow\n- Developer tools (A/B, diff, snapshots)\n- Theme editor and feature flags")
        with gr.Row():
            shared.gradio['start_tour_btn'] = gr.Button('Start Tour')
            shared.gradio['run_demo_modal_btn'] = gr.Button('Run Demo Workflow', variant='primary')
            shared.gradio['seed_demo_btn'] = gr.Button('Seed Demo Data')
            shared.gradio['close_whats_new_btn'] = gr.Button('Close')

    shared.gradio['tour_overlay'] = gr.HTML('', elem_id='tour-overlay')
    shared.gradio['launch_status'] = gr.Textbox(label='Launch status', interactive=False, visible=False)


def create_event_handlers() -> None:
    """Wire launch handlers for modal/tour/demo."""
    shared.gradio['run_demo_cta'].click(_run_demo, gradio('launch_demo_input'), gradio('launch_status'), show_progress=False)
    shared.gradio['run_demo_modal_btn'].click(_run_demo, gradio('launch_demo_input'), gradio('launch_status'), show_progress=False)
    shared.gradio['seed_demo_btn'].click(lambda: str(seed_demo_data()), None, gradio('launch_status'), show_progress=False)
    shared.gradio['start_tour_btn'].click(_start_tour, gradio('launch_session_id'), gradio('tour_overlay'), show_progress=False)
    shared.gradio['close_whats_new_btn'].click(lambda: gr.update(visible=False), None, gradio('whats_new_modal'), show_progress=False)


def on_app_ready() -> tuple[str, dict]:
    """Ensure demo workflow exists and indicate if what's new should appear."""
    ensure_demo_workflow()
    sid = 'default_session'
    completed = get_tour_state(sid)
    status = '✅ Demo workflow ready'
    return status, gr.update(visible=not completed)


def _run_demo(input_text: str) -> str:
    ensure_demo_workflow()
    result = run_workflow_path('workflows/demo.json', input_text, 'default_session')
    return f"✅ Demo ran with {len(result.get('steps', []))} steps\n{result.get('answer', '')}"


def _start_tour(session_id: str) -> str:
    mark_tour_completed(session_id)
    return (
        "<div class='tour-card'>"
        "<b>Tour (5 steps)</b><br/>"
        "1) Workflows tab (#workflows-tab)<br/>"
        "2) Marketplace tab (#marketplace-tab)<br/>"
        "3) Forms tab (#forms-tab)<br/>"
        "4) Analytics tab (#analytics-tab)<br/>"
        "5) Developer tab (#developer-tab)<br/>"
        "Tour marked complete.</div>"
    )

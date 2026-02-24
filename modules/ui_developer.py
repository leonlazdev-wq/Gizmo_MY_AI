"""Developer tab for A/B, version diff, snapshots, theme editor, and feedback."""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr

from modules import shared
from modules.ab_test import run_ab_test
from modules.devtools.version_diff import get_recent_commits, render_diff
from modules.feature_flags import get_flags, set_flag
from modules.feedback import submit_feedback
from modules.theme import build_theme_css, save_theme
from modules.ui_snapshot import capture_ui_state
from modules.utils import gradio


def create_ui() -> None:
    """Render Developer tab."""
    with gr.Tab("Developer", elem_id="developer-tab"):
        gr.Markdown("## 🛠 Developer")

        with gr.Accordion('Feature flags', open=True):
            # Visual mock: [x] canary_auto_agent [ ] risky_plugin_runtime
            shared.gradio['ff_session_id'] = gr.Textbox(label='Session ID', value='default_session')
            shared.gradio['ff_name'] = gr.Dropdown(label='Flag', choices=['canary_auto_agent', 'risky_plugin_runtime', 'ab_tester_v2'], value='canary_auto_agent')
            shared.gradio['ff_enabled'] = gr.Checkbox(label='Enabled', value=False)
            with gr.Row():
                shared.gradio['ff_save'] = gr.Button('Save flag')
                shared.gradio['ff_load'] = gr.Button('Load flags')
            shared.gradio['ff_view'] = gr.JSON(label='Flags')

        with gr.Accordion('A/B tester', open=False):
            shared.gradio['ab_prompt_a'] = gr.Textbox(label='Prompt A', value='You are concise.')
            shared.gradio['ab_prompt_b'] = gr.Textbox(label='Prompt B', value='You are detailed.')
            shared.gradio['ab_message'] = gr.Textbox(label='User message', value='Explain neural networks simply.')
            shared.gradio['ab_run'] = gr.Button('Run A/B', variant='primary')
            with gr.Row():
                shared.gradio['ab_out_a'] = gr.Textbox(label='Output A', lines=6)
                shared.gradio['ab_out_b'] = gr.Textbox(label='Output B', lines=6)
            shared.gradio['ab_metrics'] = gr.Markdown('')

        with gr.Accordion('Version Diff', open=False):
            shared.gradio['vd_old'] = gr.Textbox(label='Old revision')
            shared.gradio['vd_new'] = gr.Textbox(label='New revision')
            shared.gradio['vd_auto'] = gr.Button('Use latest two commits')
            shared.gradio['vd_run'] = gr.Button('Show diff')
            shared.gradio['vd_html'] = gr.HTML()

        with gr.Accordion('Theme Editor', open=False):
            shared.gradio['theme_primary'] = gr.ColorPicker(label='Primary color', value='#4F46E5')
            shared.gradio['theme_accent'] = gr.ColorPicker(label='Accent color', value='#059669')
            shared.gradio['theme_font_size'] = gr.Slider(label='Font size', minimum=12, maximum=22, step=1, value=15)
            with gr.Row():
                shared.gradio['theme_preview_btn'] = gr.Button('Preview')
                shared.gradio['theme_save_btn'] = gr.Button('Save theme')
            shared.gradio['theme_preview_html'] = gr.HTML()
            shared.gradio['theme_status'] = gr.Textbox(label='Theme status', interactive=False)

        with gr.Accordion('Snapshot UI', open=False):
            shared.gradio['snapshot_btn'] = gr.Button('Snapshot UI')
            shared.gradio['snapshot_status'] = gr.Textbox(label='Snapshot status', interactive=False)
            shared.gradio['snapshot_file'] = gr.File(label='Download snapshot', interactive=False)

        with gr.Accordion('Feedback', open=False):
            shared.gradio['feedback_user'] = gr.Textbox(label='User ID', value='tester')
            shared.gradio['feedback_session'] = gr.Textbox(label='Session ID', value='default_session')
            shared.gradio['feedback_text'] = gr.Textbox(label='Feedback', lines=4)
            shared.gradio['feedback_file'] = gr.File(label='Optional screenshot', type='filepath')
            shared.gradio['feedback_submit'] = gr.Button('Submit feedback')
            shared.gradio['feedback_status'] = gr.Textbox(label='Feedback status', interactive=False)


def create_event_handlers() -> None:
    """Wire developer handlers."""
    shared.gradio['ff_save'].click(
        lambda sid, name, enabled: (set_flag(sid, name, enabled), get_flags(sid))[1],
        gradio('ff_session_id', 'ff_name', 'ff_enabled'),
        gradio('ff_view'),
        show_progress=False,
    )
    shared.gradio['ff_load'].click(lambda sid: get_flags(sid), gradio('ff_session_id'), gradio('ff_view'), show_progress=False)

    shared.gradio['ab_run'].click(
        _run_ab,
        gradio('ab_prompt_a', 'ab_prompt_b', 'ab_message'),
        gradio('ab_out_a', 'ab_out_b', 'ab_metrics'),
        show_progress=False,
    )

    shared.gradio['vd_auto'].click(
        lambda: tuple(get_recent_commits(2)) if len(get_recent_commits(2)) == 2 else ('', ''),
        None,
        gradio('vd_new', 'vd_old'),
        show_progress=False,
    )
    shared.gradio['vd_run'].click(lambda old, new: render_diff(old, new), gradio('vd_old', 'vd_new'), gradio('vd_html'), show_progress=False)

    shared.gradio['theme_preview_btn'].click(
        lambda p, a, s: build_theme_css(p, a, int(s)),
        gradio('theme_primary', 'theme_accent', 'theme_font_size'),
        gradio('theme_preview_html'),
        show_progress=False,
    )
    shared.gradio['theme_save_btn'].click(
        lambda p, a, s: f"✅ Saved {save_theme(p, a, int(s))}",
        gradio('theme_primary', 'theme_accent', 'theme_font_size'),
        gradio('theme_status'),
        show_progress=False,
    )

    shared.gradio['snapshot_btn'].click(
        lambda: _snapshot_from_state(shared.persistent_interface_state),
        None,
        gradio('snapshot_status', 'snapshot_file'),
        show_progress=False,
    )

    shared.gradio['feedback_submit'].click(
        _submit_feedback,
        gradio('feedback_user', 'feedback_session', 'feedback_text', 'feedback_file'),
        gradio('feedback_status'),
        show_progress=False,
    )


def _snapshot_from_state(state: dict) -> tuple[str, str]:
    path = capture_ui_state('default_session', state)
    return f"✅ Snapshot saved: {Path(path).name}", path


def _submit_feedback(user_id: str, session_id: str, text: str, file_path: str | None) -> str:
    result = submit_feedback(user_id, session_id, text, file_path or '')
    return f"✅ Feedback saved: {result['path']}"


def _run_ab(prompt_a: str, prompt_b: str, message: str) -> tuple[str, str, str]:
    result = run_ab_test(prompt_a, prompt_b, message)
    return result['output_a'], result['output_b'], f"A: {result['ms_a']} ms | B: {result['ms_b']} ms"

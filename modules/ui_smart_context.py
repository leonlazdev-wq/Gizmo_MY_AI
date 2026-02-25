"""Smart Context UI — settings panel for the Smart Context System."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.smart_context import (
    gather_all_context,
    get_relevant_context,
    load_smart_context_settings,
    save_smart_context_settings,
)
from modules.utils import gradio


def _save_and_confirm(
    enable: bool,
    src_academic: bool,
    src_deadlines: bool,
    src_flashcards: bool,
    src_quiz: bool,
    src_planner: bool,
    src_calendar: bool,
    src_classroom: bool,
    src_documents: bool,
    src_gamification: bool,
    max_tokens: int,
) -> str:
    settings = {
        'enable_smart_context': enable,
        'smart_context_sources': {
            'academic_profile': src_academic,
            'deadlines': src_deadlines,
            'flashcard_status': src_flashcards,
            'quiz_scores': src_quiz,
            'study_planner': src_planner,
            'calendar': src_calendar,
            'classroom': src_classroom,
            'documents': src_documents,
            'gamification': src_gamification,
        },
        'smart_context_max_tokens': int(max_tokens),
    }
    save_smart_context_settings(settings)
    # Sync into shared.settings so chat.py picks it up immediately
    shared.settings['enable_smart_context'] = enable
    shared.settings['smart_context_sources'] = settings['smart_context_sources']
    shared.settings['smart_context_max_tokens'] = int(max_tokens)
    return '✅ Smart Context settings saved.'


def _preview_context() -> str:
    ctx = get_relevant_context('help me study and review my progress')
    if not ctx:
        ctx = gather_all_context()
        if not ctx:
            return '(No context data available yet — add memories, flashcards, or assignments to see content here.)'
        # Show a generic preview even if the example message returns nothing
        from modules.smart_context import build_context_block
        ctx = build_context_block(ctx)
    return ctx if ctx else '(No relevant context found for the preview message.)'


def create_ui() -> None:
    settings = load_smart_context_settings()
    sources = settings.get('smart_context_sources', {})

    with gr.Tab("Smart Context", elem_id="smart-context-tab"):
        gr.Markdown("## 🧠 Smart Context System")
        gr.Markdown(
            "Automatically injects relevant information (deadlines, quiz scores, flashcard status, "
            "gamification progress, study plan) into the AI's system prompt based on what you ask."
        )

        shared.gradio['sc_enable'] = gr.Checkbox(
            label="Enable Smart Context (inject relevant context into every chat message)",
            value=settings.get('enable_smart_context', True),
        )

        gr.Markdown("### 📂 Context Sources")
        gr.Markdown("Choose which data sources the AI can draw from:")

        with gr.Row():
            with gr.Column():
                shared.gradio['sc_src_academic'] = gr.Checkbox(
                    label="📚 Academic Profile (from Memories)",
                    value=sources.get('academic_profile', True),
                )
                shared.gradio['sc_src_deadlines'] = gr.Checkbox(
                    label="⏰ Upcoming Deadlines (from Assignment Tracker)",
                    value=sources.get('deadlines', True),
                )
                shared.gradio['sc_src_flashcards'] = gr.Checkbox(
                    label="🃏 Flashcard Review Status",
                    value=sources.get('flashcard_status', True),
                )
                shared.gradio['sc_src_quiz'] = gr.Checkbox(
                    label="📊 Quiz Scores & Weak Subjects",
                    value=sources.get('quiz_scores', True),
                )
                shared.gradio['sc_src_planner'] = gr.Checkbox(
                    label="📅 Study Planner Sessions",
                    value=sources.get('study_planner', True),
                )
            with gr.Column():
                shared.gradio['sc_src_calendar'] = gr.Checkbox(
                    label="🗓️ Calendar Events (Google Calendar)",
                    value=sources.get('calendar', True),
                )
                shared.gradio['sc_src_classroom'] = gr.Checkbox(
                    label="🏫 Google Classroom Data",
                    value=sources.get('classroom', True),
                )
                shared.gradio['sc_src_documents'] = gr.Checkbox(
                    label="📄 Connected Documents (Docs, Slides, PDFs)",
                    value=sources.get('documents', True),
                )
                shared.gradio['sc_src_gamification'] = gr.Checkbox(
                    label="🏅 Gamification Stats (XP, Streak, Badges)",
                    value=sources.get('gamification', True),
                )

        gr.Markdown("### ⚙️ Context Budget")
        shared.gradio['sc_max_tokens'] = gr.Slider(
            label="Max tokens for smart context (larger = more detail, uses more context window)",
            minimum=500,
            maximum=3000,
            step=100,
            value=settings.get('smart_context_max_tokens', 1500),
        )

        shared.gradio['sc_save_btn'] = gr.Button("💾 Save Settings", variant="primary")
        shared.gradio['sc_save_status'] = gr.Markdown("")

        gr.Markdown("### 🔍 Preview Smart Context")
        gr.Markdown(
            "See exactly what context the AI currently receives. "
            "The preview uses a generic study-related message to show all relevant sections."
        )
        shared.gradio['sc_preview_btn'] = gr.Button("🔍 Preview Smart Context")
        shared.gradio['sc_preview_output'] = gr.Textbox(
            label="Current Smart Context (what the AI sees)",
            lines=20,
            interactive=False,
            placeholder="Click 'Preview Smart Context' to see what the AI knows about you...",
        )


def create_event_handlers() -> None:
    shared.gradio['sc_save_btn'].click(
        _save_and_confirm,
        gradio(
            'sc_enable',
            'sc_src_academic',
            'sc_src_deadlines',
            'sc_src_flashcards',
            'sc_src_quiz',
            'sc_src_planner',
            'sc_src_calendar',
            'sc_src_classroom',
            'sc_src_documents',
            'sc_src_gamification',
            'sc_max_tokens',
        ),
        gradio('sc_save_status'),
        show_progress=False,
    )

    shared.gradio['sc_preview_btn'].click(
        _preview_context,
        [],
        gradio('sc_preview_output'),
        show_progress=False,
    )

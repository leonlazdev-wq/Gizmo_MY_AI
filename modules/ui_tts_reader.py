"""Gradio UI tab for Text-to-Speech Reader."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.tts_reader import (
    TTS_LANGUAGES,
    READING_MODES,
    detect_tts_engine,
    extract_text_from_file,
    generate_audio,
    load_from_flashcards,
    load_from_notes,
    load_note_text,
    load_settings,
    save_settings,
    split_into_paragraphs,
)
from modules.flashcard_generator import list_decks

# Paragraph-by-paragraph navigation state
_paragraphs: list = []
_current_para_index: int = 0


def _engine_status():
    _, msg = detect_tts_engine()
    return msg


def _do_extract_file(file_obj):
    if file_obj is None:
        return "", "❌ No file uploaded."
    path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    text, status = extract_text_from_file(path)
    return text, status


def _do_load_note(note_filename):
    if not note_filename:
        return "", "❌ No note selected."
    return load_note_text(note_filename)


def _do_load_flashcards(deck_name):
    if not deck_name:
        return "", "❌ No deck selected."
    text, msg = load_from_flashcards(deck_name)
    return text, msg


def _do_generate_audio(text, language_name, speed, engine, reading_mode):
    global _paragraphs, _current_para_index

    if not text.strip():
        return None, "❌ No text to convert.", text

    # Find language code
    lang_code = "en"
    for name, code in TTS_LANGUAGES:
        if name == language_name:
            lang_code = code
            break

    if reading_mode == "Paragraph by paragraph":
        _paragraphs = split_into_paragraphs(text)
        _current_para_index = 0
        if not _paragraphs:
            return None, "❌ Could not split text into paragraphs.", text
        text_to_speak = _paragraphs[0]
        display = _highlight_paragraph(text, text_to_speak)
    elif reading_mode == "Flashcard mode":
        _paragraphs = split_into_paragraphs(text)
        _current_para_index = 0
        text_to_speak = _paragraphs[0] if _paragraphs else text
        display = text
    else:
        text_to_speak = text
        display = text

    audio_path, status = generate_audio(
        text_to_speak,
        language_code=lang_code,
        speed=float(speed),
        engine=engine,
    )
    return audio_path, status, display


def _do_next_paragraph(text, language_name, speed, engine):
    global _paragraphs, _current_para_index
    if not _paragraphs:
        return None, "❌ No paragraphs loaded. Click Generate Audio first.", text

    _current_para_index = (_current_para_index + 1) % len(_paragraphs)
    text_to_speak = _paragraphs[_current_para_index]
    display = _highlight_paragraph(text, text_to_speak)

    lang_code = "en"
    for name, code in TTS_LANGUAGES:
        if name == language_name:
            lang_code = code
            break

    audio_path, status = generate_audio(
        text_to_speak,
        language_code=lang_code,
        speed=float(speed),
        engine=engine,
    )
    return audio_path, status, display


def _do_prev_paragraph(text, language_name, speed, engine):
    global _paragraphs, _current_para_index
    if not _paragraphs:
        return None, "❌ No paragraphs loaded. Click Generate Audio first.", text

    _current_para_index = (_current_para_index - 1) % len(_paragraphs)
    text_to_speak = _paragraphs[_current_para_index]
    display = _highlight_paragraph(text, text_to_speak)

    lang_code = "en"
    for name, code in TTS_LANGUAGES:
        if name == language_name:
            lang_code = code
            break

    audio_path, status = generate_audio(
        text_to_speak,
        language_code=lang_code,
        speed=float(speed),
        engine=engine,
    )
    return audio_path, status, display


def _highlight_paragraph(full_text: str, current_para: str) -> str:
    """Highlight the current paragraph in the full text display."""
    if not current_para or current_para not in full_text:
        return full_text
    highlighted = full_text.replace(
        current_para,
        f"**>>> {current_para} <<<**",
        1,
    )
    return highlighted


def _do_save_settings(engine, language_name, speed, auto_play, reading_mode):
    lang_code = "en"
    for name, code in TTS_LANGUAGES:
        if name == language_name:
            lang_code = code
            break
    settings = {
        "engine": engine,
        "language": lang_code,
        "speed": float(speed),
        "auto_play": bool(auto_play),
        "reading_mode": reading_mode,
    }
    return save_settings(settings)


def _load_notes_choices():
    files, _ = load_from_notes()
    return gr.update(choices=files)


def _load_deck_choices():
    decks = list_decks()
    return gr.update(choices=decks)


def create_ui():
    settings = load_settings()
    lang_name = "English"
    for name, code in TTS_LANGUAGES:
        if code == settings.get("language", "en"):
            lang_name = name
            break
    engine_choices = ["auto", "gtts", "pyttsx3"]
    lang_names = [name for name, _ in TTS_LANGUAGES]
    notes_files, _ = load_from_notes()
    deck_names = list_decks()

    with gr.Tab("🔊 Read Aloud", elem_id="tts-reader-tab"):
        # Engine status
        shared.gradio['tts_engine_status'] = gr.Markdown(_engine_status())

        with gr.Accordion("📄 Input", open=True):
            shared.gradio['tts_text_input'] = gr.Textbox(
                label="Text to Read",
                lines=8,
                placeholder="Paste text here, or load from a file / notes / flashcards…",
            )
            shared.gradio['tts_file_upload'] = gr.File(
                label="Upload File (PDF, TXT, MD)",
                file_types=[".pdf", ".txt", ".md"],
            )
            shared.gradio['tts_file_status'] = gr.Textbox(label="File Status", interactive=False)
            with gr.Row():
                shared.gradio['tts_note_selector'] = gr.Dropdown(
                    label="📄 Load from Notes",
                    choices=notes_files,
                    scale=3,
                )
                shared.gradio['tts_load_note_btn'] = gr.Button("📄 Load Note", scale=1)
                shared.gradio['tts_refresh_notes_btn'] = gr.Button("🔄", scale=0)
            with gr.Row():
                shared.gradio['tts_deck_selector'] = gr.Dropdown(
                    label="🃏 Load Flashcards",
                    choices=deck_names,
                    scale=3,
                )
                shared.gradio['tts_load_deck_btn'] = gr.Button("🃏 Load Deck", scale=1)
                shared.gradio['tts_refresh_decks_btn'] = gr.Button("🔄", scale=0)
            shared.gradio['tts_load_status'] = gr.Textbox(label="", interactive=False)

        with gr.Accordion("▶ Player", open=True):
            with gr.Row():
                shared.gradio['tts_language'] = gr.Dropdown(
                    label="Language",
                    choices=lang_names,
                    value=lang_name,
                )
                shared.gradio['tts_speed'] = gr.Slider(
                    label="Speed",
                    minimum=0.5,
                    maximum=2.0,
                    value=settings.get("speed", 1.0),
                    step=0.1,
                )
                shared.gradio['tts_reading_mode'] = gr.Dropdown(
                    label="Reading Mode",
                    choices=READING_MODES,
                    value=settings.get("reading_mode", "Full document"),
                )
            shared.gradio['tts_generate_btn'] = gr.Button("🔊 Generate Audio", variant="primary")
            shared.gradio['tts_audio_output'] = gr.Audio(
                label="Audio Output",
                interactive=False,
            )
            shared.gradio['tts_status'] = gr.Textbox(label="Status", interactive=False)
            with gr.Row():
                shared.gradio['tts_prev_para_btn'] = gr.Button("⏮ Previous Paragraph")
                shared.gradio['tts_next_para_btn'] = gr.Button("⏭ Next Paragraph")

        # Text display with highlighting
        shared.gradio['tts_text_display'] = gr.Textbox(
            label="📖 Text (current section highlighted)",
            lines=10,
            interactive=False,
        )

        with gr.Accordion("⚙️ Settings", open=False):
            shared.gradio['tts_engine_selector'] = gr.Dropdown(
                label="TTS Engine",
                choices=engine_choices,
                value=settings.get("engine", "auto"),
            )
            shared.gradio['tts_auto_play'] = gr.Checkbox(
                label="Auto-play on generation",
                value=settings.get("auto_play", False),
            )
            shared.gradio['tts_save_settings_btn'] = gr.Button("💾 Save Settings")
            shared.gradio['tts_settings_status'] = gr.Textbox(label="", interactive=False)


def create_event_handlers():
    shared.gradio['tts_file_upload'].change(
        _do_extract_file,
        inputs=[shared.gradio['tts_file_upload']],
        outputs=[
            shared.gradio['tts_text_input'],
            shared.gradio['tts_file_status'],
        ],
        show_progress=True,
    )

    shared.gradio['tts_load_note_btn'].click(
        _do_load_note,
        inputs=[shared.gradio['tts_note_selector']],
        outputs=[
            shared.gradio['tts_text_input'],
            shared.gradio['tts_load_status'],
        ],
        show_progress=False,
    )

    shared.gradio['tts_load_deck_btn'].click(
        _do_load_flashcards,
        inputs=[shared.gradio['tts_deck_selector']],
        outputs=[
            shared.gradio['tts_text_input'],
            shared.gradio['tts_load_status'],
        ],
        show_progress=False,
    )

    shared.gradio['tts_refresh_notes_btn'].click(
        _load_notes_choices,
        inputs=[],
        outputs=[shared.gradio['tts_note_selector']],
        show_progress=False,
    )

    shared.gradio['tts_refresh_decks_btn'].click(
        _load_deck_choices,
        inputs=[],
        outputs=[shared.gradio['tts_deck_selector']],
        show_progress=False,
    )

    shared.gradio['tts_generate_btn'].click(
        _do_generate_audio,
        inputs=[
            shared.gradio['tts_text_input'],
            shared.gradio['tts_language'],
            shared.gradio['tts_speed'],
            shared.gradio['tts_engine_selector'],
            shared.gradio['tts_reading_mode'],
        ],
        outputs=[
            shared.gradio['tts_audio_output'],
            shared.gradio['tts_status'],
            shared.gradio['tts_text_display'],
        ],
        show_progress=True,
    )

    shared.gradio['tts_next_para_btn'].click(
        _do_next_paragraph,
        inputs=[
            shared.gradio['tts_text_input'],
            shared.gradio['tts_language'],
            shared.gradio['tts_speed'],
            shared.gradio['tts_engine_selector'],
        ],
        outputs=[
            shared.gradio['tts_audio_output'],
            shared.gradio['tts_status'],
            shared.gradio['tts_text_display'],
        ],
        show_progress=True,
    )

    shared.gradio['tts_prev_para_btn'].click(
        _do_prev_paragraph,
        inputs=[
            shared.gradio['tts_text_input'],
            shared.gradio['tts_language'],
            shared.gradio['tts_speed'],
            shared.gradio['tts_engine_selector'],
        ],
        outputs=[
            shared.gradio['tts_audio_output'],
            shared.gradio['tts_status'],
            shared.gradio['tts_text_display'],
        ],
        show_progress=True,
    )

    shared.gradio['tts_save_settings_btn'].click(
        _do_save_settings,
        inputs=[
            shared.gradio['tts_engine_selector'],
            shared.gradio['tts_language'],
            shared.gradio['tts_speed'],
            shared.gradio['tts_auto_play'],
            shared.gradio['tts_reading_mode'],
        ],
        outputs=[shared.gradio['tts_settings_status']],
        show_progress=False,
    )

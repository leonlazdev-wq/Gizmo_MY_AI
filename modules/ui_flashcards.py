"""Gradio UI tab for the Flashcard Generator."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.flashcard_generator import (
    export_anki,
    export_csv,
    export_json,
    generate_flashcards,
    generate_from_notes,
    generate_from_pdf,
    list_decks,
    load_deck,
    save_deck,
)

TUTORIAL_URL = "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#flashcard-generator"

_current_deck: list = []
_current_card_index: int = 0


def _deck_counter() -> str:
    if not _current_deck:
        return "No cards loaded"
    return f"Card {_current_card_index + 1} / {len(_current_deck)}"


def _card_at(idx) -> tuple[str, str]:
    if not _current_deck:
        return "", ""
    card = _current_deck[idx]
    front = card.get("front", card.get("question", str(card)))
    back = card.get("back", card.get("answer", ""))
    return front, back


def _generate_from_topic(topic, count, difficulty):
    global _current_deck, _current_card_index
    msg, deck = generate_flashcards(topic, int(count), difficulty)
    _current_deck = deck or []
    _current_card_index = 0
    front, _ = _card_at(0)
    decks = list_decks()
    return msg, front, "❓ (click Flip to reveal)", _deck_counter(), gr.update(choices=decks)


def _generate_from_notes_fn(notes, count, difficulty):
    global _current_deck, _current_card_index
    msg, deck = generate_from_notes(notes, int(count), difficulty)
    _current_deck = deck or []
    _current_card_index = 0
    front, _ = _card_at(0)
    decks = list_decks()
    return msg, front, "❓ (click Flip to reveal)", _deck_counter(), gr.update(choices=decks)


def _generate_from_pdf_fn(file_obj, count):
    global _current_deck, _current_card_index
    path = file_obj.name if file_obj is not None else None
    msg, deck = generate_from_pdf(path, int(count))
    _current_deck = deck or []
    _current_card_index = 0
    front, _ = _card_at(0)
    decks = list_decks()
    return msg, front, "❓ (click Flip to reveal)", _deck_counter(), gr.update(choices=decks)


def _flip_card():
    if not _current_deck:
        return "No cards loaded."
    _, back = _card_at(_current_card_index)
    return back


def _next_card():
    global _current_card_index
    if not _current_deck:
        return "", "❓ (click Flip to reveal)", "No cards loaded"
    _current_card_index = (_current_card_index + 1) % len(_current_deck)
    front, _ = _card_at(_current_card_index)
    return front, "❓ (click Flip to reveal)", _deck_counter()


def _prev_card():
    global _current_card_index
    if not _current_deck:
        return "", "❓ (click Flip to reveal)", "No cards loaded"
    _current_card_index = (_current_card_index - 1) % len(_current_deck)
    front, _ = _card_at(_current_card_index)
    return front, "❓ (click Flip to reveal)", _deck_counter()


def _export_anki_fn():
    if not _current_deck:
        return "No deck loaded.", gr.update(visible=False)
    path = "/tmp/flashcards_anki.txt"
    msg = export_anki(_current_deck, path)
    return msg, gr.update(value=path, visible=True)


def _export_csv_fn():
    if not _current_deck:
        return "No deck loaded.", gr.update(visible=False)
    path = "/tmp/flashcards.csv"
    msg = export_csv(_current_deck, path)
    return msg, gr.update(value=path, visible=True)


def _export_json_fn():
    if not _current_deck:
        return "No deck loaded.", gr.update(visible=False)
    path = "/tmp/flashcards.json"
    msg = export_json(_current_deck, path)
    return msg, gr.update(value=path, visible=True)


def _save_deck_fn(deck_name):
    if not deck_name:
        return "Please enter a deck name."
    return save_deck(deck_name, _current_deck)


def _load_saved_deck(deck_name):
    global _current_deck, _current_card_index
    if not deck_name:
        return "No deck selected.", "", "❓ (click Flip to reveal)", "No cards loaded", gr.update()
    msg, deck = load_deck(deck_name)
    _current_deck = deck or []
    _current_card_index = 0
    front, _ = _card_at(0)
    decks = list_decks()
    return msg, front, "❓ (click Flip to reveal)", _deck_counter(), gr.update(choices=decks)


def _list_decks_fn():
    decks = list_decks()
    return gr.update(choices=decks)


def create_ui():
    with gr.Tab("🃏 Flashcards", elem_id="flashcards-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: How to use the Flashcard Generator</a>"
            f"</div>"
        )

        with gr.Accordion("🎴 Generate Flashcards", open=True):
            shared.gradio['fc_topic_input'] = gr.Textbox(label="Topic/Subject")
            shared.gradio['fc_notes_input'] = gr.Textbox(
                label="Or paste notes", lines=4
            )
            shared.gradio['fc_pdf_upload'] = gr.File(
                label="Or upload PDF", file_types=[".pdf"]
            )
            with gr.Row():
                shared.gradio['fc_count_slider'] = gr.Slider(
                    minimum=5, maximum=50, value=10, step=1, label="Number of cards"
                )
                shared.gradio['fc_difficulty'] = gr.Dropdown(
                    label="Difficulty",
                    choices=["easy", "medium", "hard"],
                    value="medium",
                )
            shared.gradio['fc_generate_btn'] = gr.Button(
                "🎴 Generate Flashcards", variant="primary"
            )
            shared.gradio['fc_gen_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📚 Study Mode", open=True):
            shared.gradio['fc_card_front'] = gr.Textbox(
                label="Question (Front)", lines=3, interactive=False
            )
            shared.gradio['fc_card_back'] = gr.Textbox(
                label="Answer (Back)", lines=3, interactive=False
            )
            with gr.Row():
                shared.gradio['fc_prev_btn'] = gr.Button("◀ Prev")
                shared.gradio['fc_flip_btn'] = gr.Button("🔄 Flip")
                shared.gradio['fc_next_btn'] = gr.Button("▶ Next")
            shared.gradio['fc_counter'] = gr.Markdown("No cards loaded")

        with gr.Accordion("💾 Save & Load", open=False):
            with gr.Row():
                shared.gradio['fc_deck_name'] = gr.Textbox(
                    label="Deck name", placeholder="Deck name..."
                )
                shared.gradio['fc_save_btn'] = gr.Button("💾 Save Deck")
            shared.gradio['fc_deck_selector'] = gr.Dropdown(
                label="Load saved deck", choices=[], interactive=True
            )
            with gr.Row():
                shared.gradio['fc_load_btn'] = gr.Button("📂 Load")
                shared.gradio['fc_refresh_decks_btn'] = gr.Button("🔄 Refresh")
            shared.gradio['fc_save_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📤 Export", open=False):
            with gr.Row():
                shared.gradio['fc_export_anki_btn'] = gr.Button("Export Anki")
                shared.gradio['fc_export_csv_btn'] = gr.Button("Export CSV")
                shared.gradio['fc_export_json_btn'] = gr.Button("Export JSON")
            shared.gradio['fc_export_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['fc_export_file'] = gr.File(
                label="Download", interactive=False, visible=False
            )


def create_event_handlers():
    _gen_outputs = [
        shared.gradio['fc_gen_status'],
        shared.gradio['fc_card_front'],
        shared.gradio['fc_card_back'],
        shared.gradio['fc_counter'],
        shared.gradio['fc_deck_selector'],
    ]

    shared.gradio['fc_generate_btn'].click(
        _generate_from_topic,
        inputs=[
            shared.gradio['fc_topic_input'],
            shared.gradio['fc_count_slider'],
            shared.gradio['fc_difficulty'],
        ],
        outputs=_gen_outputs,
        show_progress=True,
    )

    shared.gradio['fc_notes_input'].blur(
        _generate_from_notes_fn,
        inputs=[
            shared.gradio['fc_notes_input'],
            shared.gradio['fc_count_slider'],
            shared.gradio['fc_difficulty'],
        ],
        outputs=_gen_outputs,
        show_progress=False,
    )

    shared.gradio['fc_pdf_upload'].change(
        _generate_from_pdf_fn,
        inputs=[shared.gradio['fc_pdf_upload'], shared.gradio['fc_count_slider']],
        outputs=_gen_outputs,
        show_progress=True,
    )

    shared.gradio['fc_flip_btn'].click(
        _flip_card,
        inputs=[],
        outputs=[shared.gradio['fc_card_back']],
        show_progress=False,
    )

    shared.gradio['fc_next_btn'].click(
        _next_card,
        inputs=[],
        outputs=[
            shared.gradio['fc_card_front'],
            shared.gradio['fc_card_back'],
            shared.gradio['fc_counter'],
        ],
        show_progress=False,
    )

    shared.gradio['fc_prev_btn'].click(
        _prev_card,
        inputs=[],
        outputs=[
            shared.gradio['fc_card_front'],
            shared.gradio['fc_card_back'],
            shared.gradio['fc_counter'],
        ],
        show_progress=False,
    )

    shared.gradio['fc_export_anki_btn'].click(
        _export_anki_fn,
        inputs=[],
        outputs=[shared.gradio['fc_export_status'], shared.gradio['fc_export_file']],
        show_progress=True,
    )

    shared.gradio['fc_export_csv_btn'].click(
        _export_csv_fn,
        inputs=[],
        outputs=[shared.gradio['fc_export_status'], shared.gradio['fc_export_file']],
        show_progress=True,
    )

    shared.gradio['fc_export_json_btn'].click(
        _export_json_fn,
        inputs=[],
        outputs=[shared.gradio['fc_export_status'], shared.gradio['fc_export_file']],
        show_progress=True,
    )

    shared.gradio['fc_save_btn'].click(
        _save_deck_fn,
        inputs=[shared.gradio['fc_deck_name']],
        outputs=[shared.gradio['fc_save_status']],
        show_progress=True,
    )

    shared.gradio['fc_load_btn'].click(
        _load_saved_deck,
        inputs=[shared.gradio['fc_deck_selector']],
        outputs=[
            shared.gradio['fc_save_status'],
            shared.gradio['fc_card_front'],
            shared.gradio['fc_card_back'],
            shared.gradio['fc_counter'],
            shared.gradio['fc_deck_selector'],
        ],
        show_progress=True,
    )

    shared.gradio['fc_refresh_decks_btn'].click(
        _list_decks_fn,
        inputs=[],
        outputs=[shared.gradio['fc_deck_selector']],
        show_progress=False,
    )

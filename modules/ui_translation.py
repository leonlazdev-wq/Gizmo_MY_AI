"""Gradio UI tab for Multi-Language Translation."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.translation import (
    LANGUAGES,
    TARGET_LANGUAGES,
    delete_translation,
    detect_language,
    explain_grammar,
    extract_vocabulary,
    list_translations,
    pronunciation_guide,
    save_translation,
    translate_text,
    word_count,
)


def _do_detect(text):
    lang, err = detect_language(text)
    return err or lang or "Unknown"


def _do_translate(source_text, source_lang, target_lang):
    translated, err = translate_text(source_text, source_lang, target_lang)
    if err:
        return err, "", ""
    src_count = word_count(source_text)
    tgt_count = word_count(translated)
    return translated, f"Source: {src_count}", f"Translation: {tgt_count}"


def _do_save(source_text, translated_text, source_lang, target_lang):
    if not source_text.strip() or not translated_text.strip():
        return "❌ Nothing to save.", _history_html()
    msg = save_translation(source_text, translated_text, source_lang, target_lang)
    return msg, _history_html()


def _do_explain_grammar(translated_text, target_lang):
    result, err = explain_grammar(translated_text, target_lang)
    if err:
        return f"<p>{err}</p>"
    return f"<pre style='white-space:pre-wrap'>{result}</pre>"


def _do_extract_vocab(translated_text, target_lang):
    result, err = extract_vocabulary(translated_text, target_lang)
    if err:
        return f"<p>{err}</p>"
    return f"<pre style='white-space:pre-wrap'>{result}</pre>"


def _do_pronunciation(translated_text, target_lang):
    result, err = pronunciation_guide(translated_text, target_lang)
    if err:
        return f"<p>{err}</p>"
    return f"<pre style='white-space:pre-wrap'>{result}</pre>"


def _do_swap(source_lang, target_lang, source_text, translated_text):
    """Swap source and target languages and their texts."""
    new_source = target_lang if target_lang != "Auto-detect" else source_lang
    new_target = source_lang if source_lang != "Auto-detect" else target_lang
    return (
        gr.update(value=new_source),
        gr.update(value=new_target),
        translated_text,
        source_text,
    )


def _do_delete(translation_id):
    if not translation_id:
        return "❌ No ID selected.", _history_html()
    msg = delete_translation(translation_id)
    return msg, _history_html()


def _history_html():
    translations = list_translations()
    if not translations:
        return "<p style='color:gray'>No translations saved yet.</p>"
    rows = []
    for t in translations[:20]:
        ts = t.get("timestamp", "")[:16].replace("T", " ")
        src = t.get("source_lang", "?")
        tgt = t.get("target_lang", "?")
        src_text = t.get("source_text", "")[:60]
        tgt_text = t.get("translated_text", "")[:60]
        tid = t.get("id", "")
        rows.append(
            f"<tr>"
            f"<td style='padding:4px 8px;color:gray;font-size:.85em'>{ts}</td>"
            f"<td style='padding:4px 8px'>{src} → {tgt}</td>"
            f"<td style='padding:4px 8px'>{src_text}…</td>"
            f"<td style='padding:4px 8px;color:#8ec8ff'>{tgt_text}…</td>"
            f"<td style='padding:4px 8px;font-size:.8em;color:gray'>{tid}</td>"
            f"</tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse'>"
        "<thead><tr>"
        "<th style='text-align:left;padding:4px 8px'>Time</th>"
        "<th style='text-align:left;padding:4px 8px'>Languages</th>"
        "<th style='text-align:left;padding:4px 8px'>Source</th>"
        "<th style='text-align:left;padding:4px 8px'>Translation</th>"
        "<th style='text-align:left;padding:4px 8px'>ID</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def create_ui():
    with gr.Tab("🌍 Translation", elem_id="translation-tab"):
        # Language row
        with gr.Row():
            shared.gradio['tl_source_lang'] = gr.Dropdown(
                label="Source Language",
                choices=LANGUAGES,
                value="Auto-detect",
            )
            shared.gradio['tl_swap_btn'] = gr.Button("🔄 Swap", scale=0)
            shared.gradio['tl_target_lang'] = gr.Dropdown(
                label="Target Language",
                choices=TARGET_LANGUAGES,
                value="English",
            )

        # Side-by-side text panels
        with gr.Row():
            with gr.Column():
                shared.gradio['tl_source_text'] = gr.Textbox(
                    label="Source Text",
                    lines=8,
                    placeholder="Enter text to translate…",
                )
                shared.gradio['tl_source_count'] = gr.Markdown("")
                shared.gradio['tl_detect_btn'] = gr.Button("🔍 Detect Language")
                shared.gradio['tl_detected_lang'] = gr.Textbox(
                    label="Detected Language", interactive=False
                )
            with gr.Column():
                shared.gradio['tl_translated_text'] = gr.Textbox(
                    label="Translated Text",
                    lines=8,
                    interactive=False,
                    placeholder="Translation will appear here…",
                )
                shared.gradio['tl_target_count'] = gr.Markdown("")

        # Translate button
        shared.gradio['tl_translate_btn'] = gr.Button("🌍 Translate", variant="primary")
        shared.gradio['tl_translate_status'] = gr.Textbox(label="Status", interactive=False, visible=False)

        # AI Actions row
        with gr.Row():
            shared.gradio['tl_grammar_btn'] = gr.Button("📖 Explain Grammar")
            shared.gradio['tl_vocab_btn'] = gr.Button("📝 Extract Vocabulary")
            shared.gradio['tl_pronounce_btn'] = gr.Button("🔊 Pronunciation Guide")

        # AI output panel
        shared.gradio['tl_ai_output'] = gr.HTML(
            "<p style='color:gray'>AI analysis will appear here.</p>"
        )

        # Save translation
        with gr.Row():
            shared.gradio['tl_save_btn'] = gr.Button("💾 Save Translation")
            shared.gradio['tl_save_status'] = gr.Textbox(label="", interactive=False, scale=2)

        # History accordion
        with gr.Accordion("📜 Translation History", open=False):
            shared.gradio['tl_history_html'] = gr.HTML(_history_html())
            with gr.Row():
                shared.gradio['tl_delete_id'] = gr.Textbox(
                    label="Delete by ID", placeholder="Enter translation ID…"
                )
                shared.gradio['tl_delete_btn'] = gr.Button("🗑️ Delete")
            shared.gradio['tl_delete_status'] = gr.Textbox(
                label="", interactive=False
            )
            shared.gradio['tl_refresh_history_btn'] = gr.Button("🔄 Refresh History")


def create_event_handlers():
    shared.gradio['tl_detect_btn'].click(
        _do_detect,
        inputs=[shared.gradio['tl_source_text']],
        outputs=[shared.gradio['tl_detected_lang']],
        show_progress=True,
    )

    shared.gradio['tl_translate_btn'].click(
        _do_translate,
        inputs=[
            shared.gradio['tl_source_text'],
            shared.gradio['tl_source_lang'],
            shared.gradio['tl_target_lang'],
        ],
        outputs=[
            shared.gradio['tl_translated_text'],
            shared.gradio['tl_source_count'],
            shared.gradio['tl_target_count'],
        ],
        show_progress=True,
    )

    shared.gradio['tl_swap_btn'].click(
        _do_swap,
        inputs=[
            shared.gradio['tl_source_lang'],
            shared.gradio['tl_target_lang'],
            shared.gradio['tl_source_text'],
            shared.gradio['tl_translated_text'],
        ],
        outputs=[
            shared.gradio['tl_source_lang'],
            shared.gradio['tl_target_lang'],
            shared.gradio['tl_source_text'],
            shared.gradio['tl_translated_text'],
        ],
        show_progress=False,
    )

    shared.gradio['tl_grammar_btn'].click(
        _do_explain_grammar,
        inputs=[
            shared.gradio['tl_translated_text'],
            shared.gradio['tl_target_lang'],
        ],
        outputs=[shared.gradio['tl_ai_output']],
        show_progress=True,
    )

    shared.gradio['tl_vocab_btn'].click(
        _do_extract_vocab,
        inputs=[
            shared.gradio['tl_translated_text'],
            shared.gradio['tl_target_lang'],
        ],
        outputs=[shared.gradio['tl_ai_output']],
        show_progress=True,
    )

    shared.gradio['tl_pronounce_btn'].click(
        _do_pronunciation,
        inputs=[
            shared.gradio['tl_translated_text'],
            shared.gradio['tl_target_lang'],
        ],
        outputs=[shared.gradio['tl_ai_output']],
        show_progress=True,
    )

    shared.gradio['tl_save_btn'].click(
        _do_save,
        inputs=[
            shared.gradio['tl_source_text'],
            shared.gradio['tl_translated_text'],
            shared.gradio['tl_source_lang'],
            shared.gradio['tl_target_lang'],
        ],
        outputs=[
            shared.gradio['tl_save_status'],
            shared.gradio['tl_history_html'],
        ],
        show_progress=False,
    )

    shared.gradio['tl_delete_btn'].click(
        _do_delete,
        inputs=[shared.gradio['tl_delete_id']],
        outputs=[
            shared.gradio['tl_delete_status'],
            shared.gradio['tl_history_html'],
        ],
        show_progress=False,
    )

    shared.gradio['tl_refresh_history_btn'].click(
        lambda: _history_html(),
        inputs=[],
        outputs=[shared.gradio['tl_history_html']],
        show_progress=False,
    )

"""Gradio UI tab for the Essay Outliner & Writing Coach."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.essay_writer import (
    ACADEMIC_LEVELS,
    ESSAY_TYPES,
    analyze_writing,
    check_arguments,
    export_essay_markdown,
    generate_outline,
    generate_thesis_options,
    improve_paragraph,
    list_essays,
    load_essay,
    save_essay,
    word_count_stats,
    write_paragraph,
)

# Section names for paragraph writer
_SECTION_OPTIONS = [
    "Introduction",
    "Body Paragraph 1",
    "Body Paragraph 2",
    "Body Paragraph 3",
    "Body Paragraph 4",
    "Conclusion",
]

# In-memory essay state
_paragraphs: dict = {}
_current_outline: str = ""


def _do_generate_outline(topic, essay_type, word_count, academic_level):
    global _current_outline
    outline, err = generate_outline(topic, essay_type, int(word_count), academic_level)
    if err:
        return f"<p style='color:red'>{err}</p>", ""
    _current_outline = outline
    html = f"<pre style='white-space:pre-wrap;font-size:.9em'>{outline}</pre>"
    return html, "✅ Outline generated."


def _do_generate_thesis(topic, essay_type, academic_level):
    thesis, err = generate_thesis_options(topic, essay_type, academic_level)
    if err:
        return f"<p style='color:red'>{err}</p>"
    return f"<pre style='white-space:pre-wrap'>{thesis}</pre>"


def _do_write_paragraph(section, essay_type, academic_level):
    global _paragraphs
    if not section:
        return "❌ Please select a section.", gr.update()
    para, err = write_paragraph(section, essay_type, academic_level, context=_current_outline)
    if err:
        return err, gr.update()
    _paragraphs[section] = para
    return para, gr.update()


def _do_improve_paragraph(paragraph_text, essay_type, academic_level):
    if not paragraph_text.strip():
        return "❌ No paragraph to improve."
    improved, err = improve_paragraph(paragraph_text, essay_type, academic_level)
    if err:
        return err
    return improved


def _do_assemble_essay(topic, essay_type):
    global _paragraphs
    if not _paragraphs:
        return "❌ No paragraphs written yet. Use '✍️ Write Paragraph' to draft sections."
    parts = []
    for section in _SECTION_OPTIONS:
        if section in _paragraphs:
            parts.append(f"## {section}\n\n{_paragraphs[section]}\n")
    return "\n\n".join(parts) if parts else "No paragraphs assembled."


def _do_analyze(full_essay):
    if not full_essay.strip():
        return "<p style='color:red'>❌ No essay text to analyze.</p>"
    feedback, err = analyze_writing(full_essay)
    if err:
        return f"<p style='color:red'>{err}</p>"
    return f"<pre style='white-space:pre-wrap'>{feedback}</pre>"


def _do_check_args(full_essay):
    if not full_essay.strip():
        return "<p style='color:red'>❌ No essay text to check.</p>"
    result, err = check_arguments(full_essay)
    if err:
        return f"<p style='color:red'>{err}</p>"
    return f"<pre style='white-space:pre-wrap'>{result}</pre>"


def _do_word_count(full_essay):
    stats = word_count_stats(full_essay)
    return (
        f"📏 **{stats['words']}** words | "
        f"**{stats['sentences']}** sentences | "
        f"Reading level: **{stats['reading_level']}** | "
        f"Avg words/sentence: **{stats['avg_words_per_sentence']}**"
    )


def _do_save_essay(title, topic, essay_type, academic_level, full_essay):
    global _paragraphs
    data = {
        "topic": topic,
        "essay_type": essay_type,
        "academic_level": academic_level,
        "full_essay": full_essay,
        "paragraphs": _paragraphs.copy(),
    }
    msg = save_essay(title, data)
    essays = list_essays()
    choices = [f"{e.get('id', '')} — {e.get('title', '')}" for e in essays]
    return msg, gr.update(choices=choices)


def _do_load_essay(essay_choice):
    global _paragraphs, _current_outline
    if not essay_choice:
        return "❌ No essay selected.", "", ""
    essay_id = essay_choice.split(" — ")[0]
    essay_data, err = load_essay(essay_id)
    if err:
        return err, "", ""
    _paragraphs = essay_data.get("paragraphs", {})
    full = essay_data.get("full_essay", "")
    return f"✅ Loaded '{essay_data.get('title', '')}'.", full, f"Loaded: {essay_data.get('topic', '')}"


def _do_export_markdown(topic, essay_type, full_essay):
    global _paragraphs
    data = {
        "topic": topic,
        "essay_type": essay_type,
        "full_essay": full_essay,
        "paragraphs": _paragraphs.copy(),
    }
    return export_essay_markdown(data)


def _essay_choices():
    essays = list_essays()
    return [f"{e.get('id', '')} — {e.get('title', '')}" for e in essays]


def create_ui():
    with gr.Tab("📝 Essay Writer", elem_id="essay-writer-tab"):

        with gr.Accordion("📋 Setup", open=True):
            shared.gradio['ew_topic'] = gr.Textbox(
                label="Essay Topic / Prompt",
                placeholder="e.g. The impact of social media on mental health",
                lines=2,
            )
            with gr.Row():
                shared.gradio['ew_essay_type'] = gr.Dropdown(
                    label="Essay Type",
                    choices=ESSAY_TYPES,
                    value="Argumentative",
                )
                shared.gradio['ew_academic_level'] = gr.Dropdown(
                    label="Academic Level",
                    choices=ACADEMIC_LEVELS,
                    value="Undergraduate",
                )
                shared.gradio['ew_word_count'] = gr.Slider(
                    label="Target Word Count",
                    minimum=250,
                    maximum=5000,
                    value=750,
                    step=50,
                )
            with gr.Row():
                shared.gradio['ew_generate_outline_btn'] = gr.Button(
                    "📝 Generate Outline", variant="primary"
                )
                shared.gradio['ew_thesis_btn'] = gr.Button("💡 Generate Thesis Options")
            shared.gradio['ew_outline_status'] = gr.Textbox(label="Status", interactive=False)

        # Outline display
        gr.Markdown("### 📋 Outline")
        shared.gradio['ew_outline_html'] = gr.HTML(
            "<p style='color:gray'>Outline will appear here after generation.</p>"
        )
        shared.gradio['ew_thesis_html'] = gr.HTML("")

        # Writing section
        with gr.Accordion("✍️ Write Paragraphs", open=True):
            with gr.Row():
                shared.gradio['ew_section_selector'] = gr.Dropdown(
                    label="Section to Write",
                    choices=_SECTION_OPTIONS,
                    value="Introduction",
                )
                shared.gradio['ew_write_para_btn'] = gr.Button("✍️ Write Paragraph", variant="primary")
            shared.gradio['ew_paragraph_text'] = gr.Textbox(
                label="Paragraph (editable)",
                lines=8,
                placeholder="Generated paragraph will appear here…",
            )
            shared.gradio['ew_improve_btn'] = gr.Button("🔄 Improve Paragraph")

        # Full essay assembly
        with gr.Accordion("📄 Full Essay", open=False):
            shared.gradio['ew_assemble_btn'] = gr.Button("📄 Assemble Full Essay", variant="primary")
            shared.gradio['ew_full_essay'] = gr.Textbox(
                label="Full Essay",
                lines=15,
                placeholder="Full essay will appear here…",
            )
            shared.gradio['ew_word_count_display'] = gr.Markdown("")
            shared.gradio['ew_count_btn'] = gr.Button("📏 Count Words")

        # Feedback
        with gr.Accordion("🔍 Writing Feedback", open=False):
            with gr.Row():
                shared.gradio['ew_analyze_btn'] = gr.Button("📊 Analyze Writing")
                shared.gradio['ew_check_args_btn'] = gr.Button("🔍 Check Arguments")
            shared.gradio['ew_feedback_html'] = gr.HTML(
                "<p style='color:gray'>Feedback will appear here.</p>"
            )

        # Save / Export / Load
        with gr.Accordion("💾 Save & Load", open=False):
            with gr.Row():
                shared.gradio['ew_title_input'] = gr.Textbox(
                    label="Essay Title", placeholder="My Essay…", scale=3
                )
                shared.gradio['ew_save_btn'] = gr.Button("💾 Save", scale=1)
            shared.gradio['ew_save_status'] = gr.Textbox(label="Status", interactive=False)
            with gr.Row():
                shared.gradio['ew_essay_selector'] = gr.Dropdown(
                    label="Load Saved Essay",
                    choices=_essay_choices(),
                    scale=3,
                )
                shared.gradio['ew_load_btn'] = gr.Button("📂 Load", scale=1)
            shared.gradio['ew_load_status'] = gr.Textbox(label="", interactive=False)
            shared.gradio['ew_export_md_btn'] = gr.Button("📥 Export as Markdown")
            shared.gradio['ew_export_display'] = gr.Textbox(
                label="Markdown Export", lines=10, interactive=False
            )


def create_event_handlers():
    shared.gradio['ew_generate_outline_btn'].click(
        _do_generate_outline,
        inputs=[
            shared.gradio['ew_topic'],
            shared.gradio['ew_essay_type'],
            shared.gradio['ew_word_count'],
            shared.gradio['ew_academic_level'],
        ],
        outputs=[
            shared.gradio['ew_outline_html'],
            shared.gradio['ew_outline_status'],
        ],
        show_progress=True,
    )

    shared.gradio['ew_thesis_btn'].click(
        _do_generate_thesis,
        inputs=[
            shared.gradio['ew_topic'],
            shared.gradio['ew_essay_type'],
            shared.gradio['ew_academic_level'],
        ],
        outputs=[shared.gradio['ew_thesis_html']],
        show_progress=True,
    )

    shared.gradio['ew_write_para_btn'].click(
        _do_write_paragraph,
        inputs=[
            shared.gradio['ew_section_selector'],
            shared.gradio['ew_essay_type'],
            shared.gradio['ew_academic_level'],
        ],
        outputs=[
            shared.gradio['ew_paragraph_text'],
            shared.gradio['ew_outline_status'],
        ],
        show_progress=True,
    )

    shared.gradio['ew_improve_btn'].click(
        _do_improve_paragraph,
        inputs=[
            shared.gradio['ew_paragraph_text'],
            shared.gradio['ew_essay_type'],
            shared.gradio['ew_academic_level'],
        ],
        outputs=[shared.gradio['ew_paragraph_text']],
        show_progress=True,
    )

    shared.gradio['ew_assemble_btn'].click(
        _do_assemble_essay,
        inputs=[
            shared.gradio['ew_topic'],
            shared.gradio['ew_essay_type'],
        ],
        outputs=[shared.gradio['ew_full_essay']],
        show_progress=False,
    )

    shared.gradio['ew_count_btn'].click(
        _do_word_count,
        inputs=[shared.gradio['ew_full_essay']],
        outputs=[shared.gradio['ew_word_count_display']],
        show_progress=False,
    )

    shared.gradio['ew_analyze_btn'].click(
        _do_analyze,
        inputs=[shared.gradio['ew_full_essay']],
        outputs=[shared.gradio['ew_feedback_html']],
        show_progress=True,
    )

    shared.gradio['ew_check_args_btn'].click(
        _do_check_args,
        inputs=[shared.gradio['ew_full_essay']],
        outputs=[shared.gradio['ew_feedback_html']],
        show_progress=True,
    )

    shared.gradio['ew_save_btn'].click(
        _do_save_essay,
        inputs=[
            shared.gradio['ew_title_input'],
            shared.gradio['ew_topic'],
            shared.gradio['ew_essay_type'],
            shared.gradio['ew_academic_level'],
            shared.gradio['ew_full_essay'],
        ],
        outputs=[
            shared.gradio['ew_save_status'],
            shared.gradio['ew_essay_selector'],
        ],
        show_progress=False,
    )

    shared.gradio['ew_load_btn'].click(
        _do_load_essay,
        inputs=[shared.gradio['ew_essay_selector']],
        outputs=[
            shared.gradio['ew_load_status'],
            shared.gradio['ew_full_essay'],
            shared.gradio['ew_outline_status'],
        ],
        show_progress=False,
    )

    shared.gradio['ew_export_md_btn'].click(
        _do_export_markdown,
        inputs=[
            shared.gradio['ew_topic'],
            shared.gradio['ew_essay_type'],
            shared.gradio['ew_full_essay'],
        ],
        outputs=[shared.gradio['ew_export_display']],
        show_progress=False,
    )

"""Gradio UI tab for the YouTube Video Summarizer feature."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.youtube_summarizer import summarize_video

TUTORIAL_URL = (
    "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab"
    "/blob/main/README.md#youtube-video-summarizer"
)

_SUMMARY_STYLES = [
    "Brief (1 paragraph)",
    "Detailed (bullet points)",
    "Study Notes",
    "Key Takeaways",
    "Timeline/Chapters",
]

_LANGUAGES = ["en", "es", "fr", "de", "pt", "zh", "ja", "ko", "ar", "hi"]

# Session-level history (list of dicts)
_video_history: list[dict] = []


def _generate_reply(prompt: str) -> str:
    """Send *prompt* to the currently loaded model and return the response."""
    try:
        from modules.text_generation import generate_reply as _gen  # type: ignore
        for chunk in _gen(prompt, state={}, stopping_strings=[]):
            if isinstance(chunk, str):
                full = chunk
        return full  # type: ignore[return-value]
    except Exception as exc:
        return f"⚠️ Could not get AI response: {exc}"


def _fetch_and_summarize(url: str, style: str, language: str):
    """Gradio handler: fetch transcript and return summary."""
    if not url.strip():
        return (
            gr.update(value=""),         # thumbnail
            "Please enter a YouTube URL.",  # meta
            "Please enter a YouTube URL.",  # summary
            "",                           # raw transcript
            [],                           # transcript table
        )

    data = summarize_video(url.strip(), style, language)
    if "error" in data:
        return (
            gr.update(value=None),
            f"**Error:** {data['error']}",
            f"❌ {data['error']}",
            "",
            [],
        )

    meta = data.get("metadata", {})
    meta_md = (
        f"**{meta.get('title', 'Unknown')}**  \n"
        f"📺 {meta.get('channel', 'Unknown')} · ⏱ {meta.get('duration', 'N/A')}"
    )
    thumbnail = meta.get("thumbnail_url")

    # AI summary
    ai_answer = _generate_reply(data["prompt"])

    # Transcript table rows [timestamp, text]
    segments = data.get("transcript_segments", [])
    table_rows = [
        [f"{int(s.get('start', 0) // 60)}:{int(s.get('start', 0) % 60):02d}", s.get("text", "")]
        for s in segments[:200]
    ]

    # Save to history
    _video_history.append({
        "url": url.strip(),
        "title": meta.get("title", "Unknown"),
        "summary": ai_answer,
    })

    return (
        gr.update(value=thumbnail),
        meta_md,
        ai_answer,
        data.get("full_text", ""),
        table_rows,
    )


def _ask_about_video(url: str, question: str, language: str):
    """Gradio handler: answer a custom question about the video."""
    if not url.strip() or not question.strip():
        return "Please provide both a URL and a question."
    data = summarize_video(url.strip(), "Brief (1 paragraph)", language, question=question.strip())
    if "error" in data:
        return f"❌ {data['error']}"
    return _generate_reply(data["prompt"])


def create_ui():
    with gr.Tab("▶️ YouTube Summarizer", elem_id="youtube-summarizer-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: YouTube Video Summarizer</a>"
            f"</div>"
        )

        with gr.Row():
            shared.gradio['yt_url'] = gr.Textbox(
                label="YouTube URL",
                placeholder="https://www.youtube.com/watch?v=...",
                scale=4,
            )
            shared.gradio['yt_fetch_btn'] = gr.Button("▶ Fetch & Summarize", variant="primary", scale=1)

        with gr.Row():
            shared.gradio['yt_thumbnail'] = gr.Image(label="Thumbnail", type="filepath", scale=1, height=160)
            shared.gradio['yt_meta'] = gr.Markdown("", elem_id="yt-meta")

        with gr.Row():
            shared.gradio['yt_style'] = gr.Dropdown(
                label="Summary Style",
                choices=_SUMMARY_STYLES,
                value=_SUMMARY_STYLES[0],
                scale=2,
            )
            shared.gradio['yt_language'] = gr.Dropdown(
                label="Transcript Language",
                choices=_LANGUAGES,
                value="en",
                scale=1,
            )

        shared.gradio['yt_summary'] = gr.Markdown("", label="AI Summary")

        gr.Markdown("---")
        with gr.Row():
            shared.gradio['yt_question'] = gr.Textbox(
                label="Ask a question about this video",
                placeholder="What are the main arguments?",
                scale=4,
            )
            shared.gradio['yt_ask_btn'] = gr.Button("Ask", scale=1)
        shared.gradio['yt_answer'] = gr.Markdown("")

        gr.Markdown("---")
        with gr.Accordion("📝 Raw Transcript with Timestamps", open=False):
            shared.gradio['yt_transcript'] = gr.Textbox(lines=10, interactive=False, label="Full Transcript")
            shared.gradio['yt_transcript_table'] = gr.Dataframe(
                headers=["Timestamp", "Text"],
                label="Transcript Segments",
                interactive=False,
            )


def create_event_handlers():
    shared.gradio['yt_fetch_btn'].click(
        _fetch_and_summarize,
        inputs=[
            shared.gradio['yt_url'],
            shared.gradio['yt_style'],
            shared.gradio['yt_language'],
        ],
        outputs=[
            shared.gradio['yt_thumbnail'],
            shared.gradio['yt_meta'],
            shared.gradio['yt_summary'],
            shared.gradio['yt_transcript'],
            shared.gradio['yt_transcript_table'],
        ],
    )

    shared.gradio['yt_ask_btn'].click(
        _ask_about_video,
        inputs=[
            shared.gradio['yt_url'],
            shared.gradio['yt_question'],
            shared.gradio['yt_language'],
        ],
        outputs=[shared.gradio['yt_answer']],
    )

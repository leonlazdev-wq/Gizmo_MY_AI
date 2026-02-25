"""Voice Chat UI tab."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.utils import gradio
from modules.voice_chat import process_voice_input


def create_ui() -> None:
    with gr.Tab("Voice Chat", elem_id="voice-chat-tab"):
        gr.Markdown("## 🎙️ Voice Chat")
        gr.Markdown("Record your voice, let Gizmo transcribe it, respond, and speak back.")

        with gr.Row():
            with gr.Column(scale=2):
                shared.gradio['vc_audio_input'] = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="🎤 Record Audio"
                )
                shared.gradio['vc_record_btn'] = gr.Button("Transcribe & Ask AI", variant="primary")
                shared.gradio['vc_transcription'] = gr.Textbox(label="📝 Transcription", interactive=False, lines=3)
                shared.gradio['vc_ai_response'] = gr.Textbox(label="🤖 AI Response", interactive=False, lines=5)
                shared.gradio['vc_audio_output'] = gr.Audio(label="🔊 AI Spoken Response", interactive=False)

            with gr.Column(scale=1):
                gr.Markdown("### ⚙️ Settings")
                shared.gradio['vc_language'] = gr.Dropdown(
                    label="STT Language",
                    choices=["auto", "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko", "ar"],
                    value="auto"
                )
                shared.gradio['vc_tts_engine'] = gr.Dropdown(
                    label="TTS Engine",
                    choices=["gtts", "pyttsx3"],
                    value="gtts"
                )
                shared.gradio['vc_speed'] = gr.Slider(
                    label="TTS Speed",
                    minimum=0.5,
                    maximum=2.0,
                    step=0.1,
                    value=1.0
                )
                gr.Markdown(
                    "**Optional dependencies:**\n"
                    "- STT: `pip install openai-whisper`\n"
                    "- TTS: `pip install gTTS` or `pip install pyttsx3`"
                )


def create_event_handlers() -> None:
    shared.gradio['vc_record_btn'].click(
        process_voice_input,
        gradio('vc_audio_input', 'vc_language', 'vc_tts_engine', 'vc_speed'),
        gradio('vc_transcription', 'vc_ai_response', 'vc_audio_output'),
        show_progress=True
    )

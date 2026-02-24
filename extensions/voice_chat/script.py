params = {
    "display_name": "Voice Chat",
    "is_tab": False,
}

import tempfile
from pathlib import Path
from typing import Tuple

import gradio as gr

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None


class VoiceInterface:
    def __init__(self) -> None:
        self.recognizer = sr.Recognizer() if sr is not None else None

    def speech_to_text(self, audio_path: str) -> Tuple[str, str]:
        if self.recognizer is None or sr is None:
            return "", "❌ speech_recognition is not installed"
        if not audio_path:
            return "", "❌ No audio input"

        try:
            with sr.AudioFile(audio_path) as source:
                audio_data = self.recognizer.record(source)
            text = self.recognizer.recognize_google(audio_data)
            return text, "✅ Speech recognized"
        except sr.UnknownValueError:
            return "", "❌ Could not understand audio"
        except sr.RequestError as exc:
            return "", f"❌ Recognition API error: {exc}"
        except Exception as exc:
            return "", f"❌ Failed to process audio: {exc}"

    def text_to_speech(self, text: str, language: str = 'en', slow: bool = False):
        if gTTS is None:
            return None, "❌ gTTS is not installed"
        clean_text = (text or "").strip()
        if not clean_text:
            return None, "❌ No text to speak"
        try:
            out_dir = Path("user_data/outputs")
            out_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=out_dir.as_posix()) as fp:
                tts = gTTS(text=clean_text, lang=language, slow=slow)
                tts.save(fp.name)
                return fp.name, "✅ Audio generated"
        except Exception as exc:
            return None, f"❌ TTS failed: {exc}"


VOICE = VoiceInterface()


def transcribe_audio(audio_path: str):
    text, status = VOICE.speech_to_text(audio_path)
    return text, status


def synthesize_audio(text: str, language: str):
    audio_path, status = VOICE.text_to_speech(text, language=language, slow=False)
    return audio_path, status


def ui():
    with gr.Accordion("🎤 Voice Controls", open=False):
        with gr.Row():
            voice_language = gr.Dropdown(
                choices=["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh-cn"],
                value="en",
                label="Voice Language",
            )

        audio_input = gr.Audio(sources=["microphone"], type="filepath", label="Speak now")
        transcribed_text = gr.Textbox(label="Transcribed Text", lines=2)
        voice_status = gr.Textbox(label="Voice status", interactive=False)

        with gr.Row():
            transcribe_btn = gr.Button("📝 Transcribe")
            tts_btn = gr.Button("🔊 Speak text")

        tts_source_text = gr.Textbox(label="Text to speech", lines=2)
        audio_output = gr.Audio(label="Response audio")

    transcribe_btn.click(transcribe_audio, audio_input, [transcribed_text, voice_status])
    tts_btn.click(synthesize_audio, [tts_source_text, voice_language], [audio_output, voice_status])

"""Voice Chat backend – STT via OpenAI Whisper, TTS via gTTS or pyttsx3."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from modules.logging_colors import logger


def transcribe_audio(audio_path: str, language: str = "auto") -> str:
    """Transcribe audio file to text using OpenAI Whisper."""
    if not audio_path or not Path(audio_path).exists():
        return ""

    try:
        import whisper  # type: ignore

        model = whisper.load_model("base")
        options: dict = {}
        if language and language != "auto":
            options["language"] = language

        result = model.transcribe(audio_path, **options)
        return (result.get("text") or "").strip()
    except ImportError:
        logger.warning("openai-whisper is not installed. Run: pip install openai-whisper")
        return "[Whisper not installed – pip install openai-whisper]"
    except Exception as exc:
        logger.error(f"Transcription error: {exc}")
        return f"[Transcription failed: {exc}]"


def text_to_speech_gtts(text: str, language: str = "en", speed: float = 1.0) -> str | None:
    """Convert text to speech using gTTS and return path to audio file."""
    try:
        from gtts import gTTS  # type: ignore

        slow = speed < 0.9
        tts = gTTS(text=text, lang=language if language != "auto" else "en", slow=slow)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, dir="user_data/cache")
        tts.save(tmp.name)
        return tmp.name
    except ImportError:
        logger.warning("gTTS is not installed. Run: pip install gTTS")
        return None
    except Exception as exc:
        logger.error(f"gTTS error: {exc}")
        return None


def text_to_speech_pyttsx3(text: str, speed: float = 1.0) -> str | None:
    """Convert text to speech using pyttsx3 and return path to audio file."""
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        rate = engine.getProperty("rate")
        engine.setProperty("rate", int(rate * speed))

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="user_data/cache")
        engine.save_to_file(text, tmp.name)
        engine.runAndWait()
        return tmp.name
    except ImportError:
        logger.warning("pyttsx3 is not installed. Run: pip install pyttsx3")
        return None
    except Exception as exc:
        logger.error(f"pyttsx3 error: {exc}")
        return None


def synthesize_speech(text: str, engine: str = "gtts", language: str = "en", speed: float = 1.0) -> str | None:
    """Synthesize speech using the specified engine."""
    Path("user_data/cache").mkdir(parents=True, exist_ok=True)
    text = (text or "").strip()
    if not text:
        return None

    if engine == "pyttsx3":
        return text_to_speech_pyttsx3(text, speed=speed)
    else:
        lang = language if language != "auto" else "en"
        return text_to_speech_gtts(text, language=lang, speed=speed)


def process_voice_input(audio_path: str, language: str, tts_engine: str, tts_speed: float) -> tuple[str, str, str | None]:
    """Full pipeline: transcribe → generate AI response → TTS."""
    if not audio_path:
        return "No audio recorded.", "", None

    # Step 1: Transcribe
    transcription = transcribe_audio(audio_path, language)
    if not transcription or transcription.startswith("["):
        return transcription, "", None

    # Step 2: Get AI response
    ai_response = _get_ai_response(transcription)

    # Step 3: TTS
    audio_out = synthesize_speech(ai_response, engine=tts_engine, language=language, speed=tts_speed)

    return transcription, ai_response, audio_out


def _get_ai_response(user_message: str) -> str:
    """Send text to the loaded model and return the response."""
    try:
        from modules import shared
        from modules.text_generation import generate_reply

        if shared.model is None:
            return "⚠️ No model is loaded. Please load a model first."

        state = {"max_new_tokens": 512, "temperature": 0.7, "top_p": 0.9}
        generator = generate_reply(user_message, state)
        response = ""
        for chunk in generator:
            if isinstance(chunk, str):
                response = chunk
            elif isinstance(chunk, list):
                response = chunk[0] if chunk else response
        return response.strip() or "[No response]"
    except Exception as exc:
        logger.error(f"AI response error: {exc}")
        return f"[AI error: {exc}]"

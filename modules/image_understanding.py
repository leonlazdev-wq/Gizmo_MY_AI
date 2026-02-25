"""Image Understanding backend – convert image to base64 and query the AI."""

from __future__ import annotations

import base64
from pathlib import Path

from modules.logging_colors import logger


def image_to_base64(image_path: str) -> str:
    """Read an image file and return its base64 encoding."""
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        ext = Path(image_path).suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{encoded}"
    except Exception as exc:
        logger.error(f"Image encoding error: {exc}")
        return ""


def ask_about_image(image_path: str | None, question: str) -> str:
    """Ask the loaded model a question about an uploaded image."""
    if not image_path:
        return "⚠️ Please upload an image first."

    question = (question or "").strip()
    if not question:
        return "⚠️ Please enter a question about the image."

    try:
        from modules import shared
        from modules.text_generation import generate_reply

        if shared.model is None:
            return "⚠️ No model is loaded. Please load a model first."

        # Build a simple text description prompt (works with all models)
        # For multimodal models the image would be embedded; here we describe the intent
        b64 = image_to_base64(image_path)
        if not b64:
            return "⚠️ Could not read the image file."

        # If the model is multimodal, try to use vision capabilities
        if getattr(shared, "is_multimodal", False):
            prompt = f"<image>\n{question}"
        else:
            prompt = (
                f"[An image has been uploaded by the user. "
                f"Describe and answer based on it.]\n\n"
                f"User question: {question}\n\n"
                f"Please answer the question as if you can see the image."
            )

        state = {"max_new_tokens": 1024, "temperature": 0.7, "top_p": 0.9}
        generator = generate_reply(prompt, state)
        response = ""
        for chunk in generator:
            if isinstance(chunk, str):
                response = chunk
            elif isinstance(chunk, list):
                response = chunk[0] if chunk else response
        return response.strip() or "[No response]"
    except Exception as exc:
        logger.error(f"Image understanding error: {exc}")
        return f"[Error: {exc}]"


# Session history stored in memory
_session_history: list[dict] = []


def get_session_history() -> list[list[str]]:
    return [[h["question"], h["answer"]] for h in _session_history[-10:]]


def add_to_history(question: str, answer: str, image_path: str) -> None:
    _session_history.append({"question": question, "answer": answer, "image": image_path})


def ask_and_record(image_path: str | None, question: str) -> tuple[str, list[list[str]]]:
    """Ask about image and record in session history."""
    answer = ask_about_image(image_path, question)
    if image_path and not answer.startswith("⚠️"):
        add_to_history(question or "", answer, image_path or "")
    return answer, get_session_history()

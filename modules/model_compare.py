"""Model Compare backend – run the same prompt through two models side by side."""

from __future__ import annotations

import json
import time
from pathlib import Path

from modules.logging_colors import logger

_compare_history: list[dict] = []
_RESULTS_PATH = Path("user_data/compare_results.json")


def _load_and_generate(model_name: str, prompt: str) -> tuple[str, float, int]:
    """Load a model (if needed), generate a response, return (text, elapsed_s, token_count)."""
    from modules import shared
    from modules.models import load_model
    from modules.text_generation import generate_reply

    if shared.model_name != model_name:
        logger.info(f"Model Compare: loading {model_name}")
        shared.model, shared.tokenizer = load_model(model_name)
        shared.model_name = model_name

    state = {"max_new_tokens": 512, "temperature": 0.7, "top_p": 0.9}
    t0 = time.perf_counter()
    response = ""
    for chunk in generate_reply(prompt, state):
        if isinstance(chunk, str):
            response = chunk
        elif isinstance(chunk, list):
            response = chunk[0] if chunk else response
    elapsed = time.perf_counter() - t0

    token_count = 0
    if shared.tokenizer:
        try:
            token_count = len(shared.tokenizer.encode(response))
        except Exception:
            token_count = len(response.split())

    return response.strip(), round(elapsed, 2), token_count


def compare_models(model_a: str, model_b: str, prompt: str) -> tuple[str, str, str, str]:
    """Run prompt on both models and return responses + metadata."""
    prompt = (prompt or "").strip()
    if not prompt:
        return "⚠️ Enter a question first.", "", "", ""

    if not model_a or model_a == "None":
        return "⚠️ Select Model A.", "", "", ""

    if not model_b or model_b == "None":
        return "⚠️ Select Model B.", "", "", ""

    try:
        from modules import shared

        if shared.model is None and model_a != "None":
            return "⚠️ No model loaded. Please load a model first or select valid models.", "", "", ""

        resp_a, time_a, tokens_a = _load_and_generate(model_a, prompt)
        resp_b, time_b, tokens_b = _load_and_generate(model_b, prompt)

        meta_a = f"⏱ {time_a}s | 🔤 {tokens_a} tokens | {round(tokens_a / max(time_a, 0.001), 1)} tok/s"
        meta_b = f"⏱ {time_b}s | 🔤 {tokens_b} tokens | {round(tokens_b / max(time_b, 0.001), 1)} tok/s"

        _compare_history.append({
            "prompt": prompt,
            "model_a": model_a, "response_a": resp_a[:200],
            "model_b": model_b, "response_b": resp_b[:200],
        })

        return resp_a, meta_a, resp_b, meta_b

    except Exception as exc:
        logger.error(f"Model compare error: {exc}")
        return f"[Error: {exc}]", "", "", ""


def vote(winner: str, model_a: str, model_b: str, prompt: str) -> str:
    """Log a preference vote to compare_results.json."""
    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: list = []
    if _RESULTS_PATH.exists():
        try:
            existing = json.loads(_RESULTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    existing.append({"winner": winner, "model_a": model_a, "model_b": model_b, "prompt": (prompt or "")[:100]})
    _RESULTS_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"✅ Voted: {winner}"


def get_compare_history() -> list[list[str]]:
    return [[h["model_a"], h["model_b"], h["prompt"][:60]] for h in _compare_history[-10:]]

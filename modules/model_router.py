"""Rule-based model routing."""

from __future__ import annotations

from typing import Dict


class ModelRouter:
    def __init__(self, fast_model: str = "fast", smart_model: str = "smart"):
        self.fast_model = fast_model
        self.smart_model = smart_model

    def select_model(self, prompt: str, state: Dict | None = None) -> str:
        state = state or {}
        if state.get("force_model"):
            return state["force_model"]

        text = (prompt or "")
        complex_markers = ["analyze", "design", "architecture", "debug", "multi-step", "reasoning"]
        if len(text) > 600 or any(m in text.lower() for m in complex_markers):
            return self.smart_model
        return self.fast_model

"""Prompt optimization helpers."""

from __future__ import annotations


def optimize_prompt(user_prompt: str, include_context: str = "") -> str:
    base = (user_prompt or "").strip()
    if not base:
        return ""

    preface = "You are a precise assistant. Provide actionable, structured output."
    if include_context.strip():
        return f"{preface}\n\nContext:\n{include_context}\n\nUser request:\n{base}"

    return f"{preface}\n\nUser request:\n{base}"

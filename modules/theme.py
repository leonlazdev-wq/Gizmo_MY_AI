"""Theme editor helpers for generating runtime CSS."""

from __future__ import annotations

import json
from pathlib import Path


THEME_PATH = Path("user_data/theme.json")


def build_theme_css(primary: str, accent: str, font_size: int) -> str:
    """Build CSS snippet from theme controls."""
    return (
        "<style id='gizmo-theme-preview'>"
        f":root{{--gizmo-primary:{primary};--gizmo-accent:{accent};--gizmo-font-size:{font_size}px;}}"
        "button.primary{background:var(--gizmo-primary)!important;border-color:var(--gizmo-primary)!important;}"
        "body,.gradio-container{font-size:var(--gizmo-font-size)!important;}"
        "</style>"
    )


def save_theme(primary: str, accent: str, font_size: int) -> str:
    """Persist theme settings and return path."""
    THEME_PATH.parent.mkdir(parents=True, exist_ok=True)
    THEME_PATH.write_text(
        json.dumps({"primary": primary, "accent": accent, "font_size": font_size}, indent=2),
        encoding="utf-8",
    )
    return str(THEME_PATH)

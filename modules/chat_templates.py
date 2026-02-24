"""Chat templates storage and operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

TEMPLATES_DIR = Path("user_data/chat_templates")
TEMPLATE_FILE = TEMPLATES_DIR / "templates.json"

DEFAULT_TEMPLATES: Dict[str, Dict[str, object]] = {
    "coding_assistant": {
        "name": "👨‍💻 Coding Assistant",
        "description": "Expert programmer ready to help debug, explain, and write code.",
        "system_prompt": "You are an expert programmer. Explain tradeoffs and provide tested code when possible.",
        "starter_messages": [
            "Explain this code to me",
            "Help me debug this function",
            "Write a function that...",
        ],
        "category": "Programming",
        "icon": "💻",
    },
    "creative_writer": {
        "name": "✍️ Creative Writing Coach",
        "description": "Professional writing guidance for stories, poems, and editing.",
        "system_prompt": "You are a bestselling author and writing coach. Give concrete suggestions and alternatives.",
        "starter_messages": [
            "Help me brainstorm a story about...",
            "Review my writing and suggest improvements",
            "Write a poem about...",
        ],
        "category": "Creative",
        "icon": "📝",
    },
    "research_helper": {
        "name": "🔬 Research Assistant",
        "description": "Academic assistant for reading, summarizing, and framing research.",
        "system_prompt": "You are a rigorous researcher. Cite assumptions and distinguish evidence from speculation.",
        "starter_messages": [
            "Help me understand this research paper",
            "Suggest research directions for...",
            "Summarize key findings on...",
        ],
        "category": "Academic",
        "icon": "📚",
    },
    "math_tutor": {
        "name": "➗ Math Tutor",
        "description": "Step-by-step guidance from arithmetic to advanced topics.",
        "system_prompt": "You are a patient math tutor. Show every important step and verify calculations.",
        "starter_messages": ["Walk me through this equation", "Give me practice problems", "Explain this theorem simply"],
        "category": "Academic",
        "icon": "➗",
    },
    "language_teacher": {
        "name": "🗣️ Language Teacher",
        "description": "Conversation and grammar coach for language learners.",
        "system_prompt": "You are a language teacher. Correct mistakes gently and provide better alternatives.",
        "starter_messages": ["Practice a dialogue with me", "Correct this paragraph", "Teach me useful phrases"],
        "category": "Academic",
        "icon": "🗣️",
    },
    "debate_partner": {
        "name": "⚖️ Debate Partner",
        "description": "Challenges assumptions and sharpens arguments with balanced reasoning.",
        "system_prompt": "You are a debate partner. Present strongest arguments for and against before concluding.",
        "starter_messages": ["Debate this idea with me", "Challenge my position on...", "Steelman both sides of..."],
        "category": "Business",
        "icon": "⚖️",
    },
}


def _ensure_storage() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def save_templates(templates: Dict[str, Dict[str, object]]) -> None:
    _ensure_storage()
    TEMPLATE_FILE.write_text(json.dumps(templates, indent=2), encoding="utf-8")


def load_templates() -> Dict[str, Dict[str, object]]:
    _ensure_storage()
    if not TEMPLATE_FILE.exists():
        save_templates(DEFAULT_TEMPLATES)
    try:
        return json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        save_templates(DEFAULT_TEMPLATES)
        return DEFAULT_TEMPLATES.copy()


def get_template_choices(category: str = "All") -> List[Tuple[str, str]]:
    templates = load_templates()
    filtered = []
    for key, template in templates.items():
        template_category = str(template.get("category", "Other"))
        if category == "All" or template_category == category:
            filtered.append((str(template.get("name", key)), key))
    return sorted(filtered, key=lambda item: item[0].lower())


def apply_template(template_key: str, history: dict) -> tuple[dict, str, str]:
    templates = load_templates()
    if template_key not in templates:
        return history, "", "❌ Template not found"

    template = templates[template_key]
    welcome = [
        f"**{template.get('icon', '💬')} {template.get('name', template_key)}**",
        "",
        str(template.get("description", "")),
        "",
        "**Suggested prompts:**",
    ]
    for suggestion in template.get("starter_messages", []):
        welcome.append(f"- {suggestion}")

    internal = [["", f"[SYSTEM] {template.get('system_prompt', '')}"], [None, "\n".join(welcome)]]
    visible = [["", ""], [None, "\n".join(welcome)]]
    updated = {
        "internal": internal,
        "visible": visible,
        "metadata": {"template": template_key},
    }
    return updated, str(template.get("system_prompt", "")), f"✅ Applied template: {template.get('name', template_key)}"


def create_custom_template(name: str, description: str, system_prompt: str, category: str, icon: str) -> str:
    cleaned_name = (name or "").strip()
    cleaned_description = (description or "").strip()
    cleaned_prompt = (system_prompt or "").strip()
    if not cleaned_name or not cleaned_prompt:
        return "❌ Template name and system prompt are required"

    template_id = "_".join(cleaned_name.lower().split())
    templates = load_templates()
    templates[template_id] = {
        "name": cleaned_name,
        "description": cleaned_description,
        "system_prompt": cleaned_prompt,
        "starter_messages": [],
        "category": category or "Other",
        "icon": (icon or "💬").strip() or "💬",
    }
    save_templates(templates)
    return f"✅ Created template: {cleaned_name}"

params = {
    "display_name": "Multi-Agent Debate",
    "is_tab": True,
}

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import gradio as gr

from modules import shared
from modules.text_generation import generate_reply


@dataclass
class Agent:
    name: str
    persona: str
    color: str

    def format_prompt(self, topic: str, conversation_history: List[Dict[str, str]]) -> str:
        prompt = f"You are {self.name}. {self.persona}\n\nTopic: {topic}\n"
        if conversation_history:
            prompt += "\nPrevious statements:\n"
            for msg in conversation_history[-10:]:
                prompt += f"- {msg['agent']}: {msg['content']}\n"
        prompt += "\nRespond in 2-4 concise paragraphs with clear reasoning."
        return prompt


AGENTS = {
    "optimist": Agent("The Optimist 🌟", "Focus on upside, opportunities, and constructive framing.", "#4CAF50"),
    "skeptic": Agent("The Skeptic 🤔", "Challenge assumptions and highlight risks and blind spots.", "#FF9800"),
    "pragmatist": Agent("The Pragmatist ⚖️", "Balance tradeoffs and propose realistic implementation steps.", "#2196F3"),
    "futurist": Agent("The Futurist 🚀", "Analyze long-term implications and emerging trends.", "#9C27B0"),
}


def _generate_response(prompt: str) -> str:
    state = dict(shared.settings)
    final = ""
    for text in generate_reply(prompt, state, stopping_strings=[], is_chat=False, escape_html=False, for_ui=False):
        final = text
    return final.strip() or "I do not have enough information to answer."


def format_debate_output(conversation: List[Dict[str, str]]) -> str:
    output = "# 🎭 Multi-Agent Debate\n\n"
    current_round = 0
    for msg in conversation:
        if msg["round"] != current_round:
            current_round = msg["round"]
            output += f"\n---\n## 📍 Round {current_round}\n\n"

        output += (
            f"<div style='border-left:4px solid {msg['color']};padding-left:12px;margin:10px 0;'>"
            f"<strong style='color:{msg['color']};'>{msg['agent']}</strong><br/>{msg['content']}"
            "</div>"
        )

    return output


def run_debate(topic: str, selected_agents: List[str], rounds: int):
    if not topic.strip():
        yield "❌ Please provide a topic."
        return

    chosen = [AGENTS[a] for a in selected_agents if a in AGENTS]
    if len(chosen) < 2:
        yield "❌ Select at least 2 agents."
        return

    conversation: List[Dict[str, str]] = []
    for round_num in range(1, int(rounds) + 1):
        for agent in chosen:
            prompt = agent.format_prompt(topic, conversation)
            response = _generate_response(prompt)
            conversation.append(
                {
                    "agent": agent.name,
                    "content": response,
                    "round": round_num,
                    "color": agent.color,
                }
            )
            yield format_debate_output(conversation)


def export_debate(markdown_text: str) -> str:
    if not markdown_text.strip():
        return "❌ Nothing to export"
    output_dir = Path("user_data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"debate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path.write_text(markdown_text, encoding="utf-8")
    return f"✅ Saved debate transcript to {path.as_posix()}"


def ui():
    gr.Markdown("## 🎭 Multi-Agent Debate")
    with gr.Row():
        with gr.Column(scale=1):
            debate_topic = gr.Textbox(label="Debate Topic", lines=3, placeholder="Should AI be regulated?")
            agent_selection = gr.CheckboxGroup(
                choices=list(AGENTS.keys()),
                value=["optimist", "skeptic"],
                label="Select Agents",
            )
            rounds = gr.Slider(minimum=1, maximum=5, value=2, step=1, label="Rounds")
            start_debate_btn = gr.Button("🎬 Start Debate", variant="primary")
            quick_topics = gr.Radio(
                choices=[
                    "Should remote work become default?",
                    "Impact of AI on creative industries",
                    "Universal Basic Income pros and cons",
                    "Future of education in 2030",
                ],
                label="Quick Topics",
            )
        with gr.Column(scale=3):
            debate_output = gr.Markdown(value="*Debate will appear here...*")
            export_btn = gr.Button("📥 Export Debate Transcript")
            export_status = gr.Textbox(label="Export status", interactive=False)

    quick_topics.change(lambda x: x, quick_topics, debate_topic)
    start_debate_btn.click(run_debate, [debate_topic, agent_selection, rounds], debate_output)
    export_btn.click(export_debate, debate_output, export_status)

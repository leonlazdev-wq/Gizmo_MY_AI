params = {"display_name": "Learning Center", "is_tab": True}

import json
from pathlib import Path

import gradio as gr


class LearningCenter:
    def __init__(self):
        self.dir = Path("user_data/tutorials")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.dir / "progress.json"
        self.tips_file = self.dir / "community_tips.json"
        self.progress = self._load_json(self.progress_file, {})
        self.tips = self._load_json(self.tips_file, [])

    @staticmethod
    def _load_json(path: Path, fallback):
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return fallback

    def _save_json(self, path: Path, data):
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_tip(self, title: str, content: str, category: str) -> str:
        if not title.strip() or not content.strip():
            return "❌ Title and content are required"
        self.tips.append({"title": title.strip(), "content": content.strip(), "category": category or "Other"})
        self._save_json(self.tips_file, self.tips)
        return "✅ Tip submitted"

    def render_tips(self) -> str:
        if not self.tips:
            return "<p>No community tips yet.</p>"
        cards = []
        for tip in reversed(self.tips[-50:]):
            cards.append(f"<div style='background:#2a2a2a;padding:12px;border-radius:8px;margin:8px 0'><b>{tip['title']}</b> <small>({tip['category']})</small><br/>{tip['content']}</div>")
        return "".join(cards)


def ui():
    lc = LearningCenter()
    gr.Markdown("# 🎓 Learning Center")
    with gr.Tabs():
        with gr.Tab("📚 Tutorials"):
            gr.Markdown("Starter tutorials are coming soon. Use Prompt Library and Community tabs for now.")
        with gr.Tab("💡 Prompt Library"):
            gr.Markdown("- **Code Explainer**: Explain this Python function and suggest improvements.\n- **Story Starter**: Write an opening paragraph for a sci-fi story set on Mars.")
        with gr.Tab("💬 Community"):
            with gr.Row():
                with gr.Column():
                    tip_title = gr.Textbox(label="Tip Title")
                    tip_content = gr.Textbox(label="Share Your Tip", lines=5)
                    tip_category = gr.Dropdown(choices=["Prompt Engineering", "Workflow", "Model Selection", "Other"], label="Category")
                    submit_tip_btn = gr.Button("📤 Submit Tip")
                    tip_status = gr.Textbox(label="Status", interactive=False)
                with gr.Column():
                    community_tips = gr.HTML(value=lc.render_tips())
            submit_tip_btn.click(lc.add_tip, [tip_title, tip_content, tip_category], tip_status).then(lc.render_tips, None, community_tips)

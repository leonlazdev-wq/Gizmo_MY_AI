import os
import re
from datetime import datetime
from pathlib import Path

import gradio as gr
import psutil

params = {
    "display_name": "🛠️ Student Utils",
    "is_tab": True,
}

PERSONAS = [
    ("🎓 Tutor", "You are a patient and encouraging tutor. You explain things clearly, check for understanding, and never make the student feel bad for not knowing something. Always ask 'Does that make sense?' at the end of explanations."),
    ("💻 Coder", "You are an expert software engineer and coding mentor. You write clean, well-commented production code. You explain WHY you made each coding choice, not just what the code does. You never write pseudocode — always real, working code."),
    ("✍️ Writing Coach", "You are a writing coach who helps students write better essays, stories, and reports. You give specific, actionable feedback. You point out what is working well AND what needs improvement. You help the student improve their own writing rather than writing it for them."),
    ("🌍 Translator", "You are a professional translator and language teacher. You translate accurately while preserving tone and meaning. When asked to translate, you also point out interesting vocabulary or phrases the student might want to learn."),
    ("🧮 Math Helper", "You are a math tutor who specializes in making math feel approachable. You solve problems step by step, never skipping steps. You connect math concepts to real-world examples. If a student makes a mistake, you guide them to find the error themselves rather than just correcting it."),
    ("⚔️ Debate Partner", "You are a debate coach and sparring partner. When the student states a position, you steelman the opposing view — arguing against them with the strongest possible counterarguments. This helps them prepare for real debates and think critically. After the debate, you give coaching on how they can strengthen their arguments."),
]

NOTES_FILE_CANDIDATES = [
    Path("/content/drive/MyDrive/MY-AI-Gizmo/notes.txt"),
    Path("/content/MY-AI-Gizmo/notes.txt"),
]


def card_style():
    return """
    <style>
      .su-card{background:#1e1e2e;border:1px solid #333355;border-radius:12px;padding:14px;color:#e0e0f0;}
      .su-muted{color:#aaaacc;font-size:.9em}
      .su-link a{color:#8ec8ff !important;text-decoration:underline;}
    </style>
    """


def get_history():
    try:
        import modules.shared as shared

        hist = getattr(shared, "history", {})
        if isinstance(hist, dict):
            return hist.get("internal", []) or []
    except Exception:
        pass
    return []


def export_chat(history, fmt, filename):
    safe_name = re.sub(r"[^\w\-_]", "_", (filename or "").strip()) or "chat_export"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".md" if "Markdown" in (fmt or "") else ".txt"
    full_name = f"{safe_name}_{timestamp}{ext}"

    if not history:
        return "⚠️ Start a chat first, then export.", ""

    for base in (Path("/content/drive/MyDrive/MY-AI-Gizmo/exports"), Path("/content/MY-AI-Gizmo/exports")):
        try:
            base.mkdir(parents=True, exist_ok=True)
            out_path = base / full_name
            lines = []
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            if "Markdown" in fmt:
                lines.append(f"# Chat Export — {now}\n")
                for i, pair in enumerate(history, 1):
                    user = pair[0] if len(pair) > 0 else ""
                    bot = pair[1] if len(pair) > 1 else ""
                    lines.append(f"## Turn {i}\n")
                    lines.append(f"**You:** {user}\n")
                    lines.append(f"**AI:** {bot}\n")
            else:
                lines.append(f"Chat Export — {now}\n")
                for i, pair in enumerate(history, 1):
                    user = pair[0] if len(pair) > 0 else ""
                    bot = pair[1] if len(pair) > 1 else ""
                    lines.append(f"[{i}] You: {user}\n")
                    lines.append(f"[{i}] AI:  {bot}\n")

            out_path.write_text("\n".join(lines), encoding="utf-8")
            return f"✅ Saved: {out_path}", f"<div class='su-link'><a href='file={out_path}'>📄 {full_name}</a></div>"
        except Exception:
            continue

    return "❌ Could not save file — check Drive is mounted", ""


def build_status_card():
    vm = psutil.virtual_memory()
    ram_used_gb = vm.used / 1024**3
    ram_total_gb = vm.total / 1024**3
    ram_pct = vm.percent
    ram_bar_fill = int(ram_pct / 5)
    ram_bar = "█" * ram_bar_fill + "░" * (20 - ram_bar_fill)
    ram_color = "#e74c3c" if ram_pct > 85 else "#f39c12" if ram_pct > 65 else "#2ecc71"

    cpu_pct = psutil.cpu_percent(interval=0.1)

    model_name = "None loaded"
    try:
        import modules.shared as shared

        if getattr(shared, "model_name", None):
            model_name = shared.model_name
    except Exception:
        pass

    drive_info = ""
    try:
        du = psutil.disk_usage("/content/drive/MyDrive")
        used_gb = du.used / 1024**3
        total_gb = du.total / 1024**3
        drive_info = f"<tr><td>📁 Drive</td><td>{used_gb:.1f} / {total_gb:.1f} GB</td></tr>"
    except Exception:
        pass

    return f"""
    <div class='su-card' style='font-family:monospace'>
      <div class='su-muted' style='margin-bottom:10px'>Updated: {datetime.now().strftime('%H:%M:%S')}</div>
      <table style='width:100%;border-collapse:collapse;color:#e0e0f0'>
        <tr><td style='padding:4px 8px;color:#888'>🧠 RAM</td>
            <td style='padding:4px 8px'><span style='color:{ram_color}'>{ram_bar}</span>
            <span style='margin-left:8px'>{ram_used_gb:.1f} / {ram_total_gb:.1f} GB ({ram_pct:.0f}%)</span></td></tr>
        <tr><td style='padding:4px 8px;color:#888'>⚙️ CPU</td><td style='padding:4px 8px'>{cpu_pct:.0f}%</td></tr>
        <tr><td style='padding:4px 8px;color:#888'>🤖 Model</td><td style='padding:4px 8px'>{model_name}</td></tr>
        {drive_info}
      </table>
    </div>
    """


def switch_persona(persona_name, system_prompt):
    try:
        import modules.shared as shared

        if hasattr(shared, "settings") and isinstance(shared.settings, dict):
            shared.settings["instruction_template_str"] = system_prompt
            shared.settings["system_message"] = system_prompt
        return f"✅ Switched to: {persona_name}", persona_name, ""
    except Exception as e:
        msg = (
            f"⚠️ Could not switch automatically ({e}). Copy and paste prompt manually."
        )
        return msg, persona_name, system_prompt


def load_notes():
    for path in NOTES_FILE_CANDIDATES:
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


def save_notes(text):
    for path in NOTES_FILE_CANDIDATES:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text or "", encoding="utf-8")
            return f"✅ Saved at {datetime.now().strftime('%H:%M:%S')}"
        except Exception:
            continue
    return "❌ Could not save — Drive may not be mounted"


def clear_notes():
    status = save_notes("")
    return "", status


def ui():
    gr.HTML(card_style())
    with gr.Tabs():
        with gr.Tab("⚡ Quick Prompts"):
            try:
                gr.Markdown("### ⚡ Quick Prompts")
                with gr.Group(elem_classes=["su-card"]):
                    gr.Markdown("Use these starter prompts:")
                    gr.Markdown("- Explain this topic like I'm 12.\n- Quiz me on this chapter.\n- Turn these notes into flashcards.\n- Summarize this in 5 bullet points.")
            except Exception as e:
                gr.Markdown(f"⚠️ Quick Prompts unavailable: {e}")

        with gr.Tab("💾 Export Chat"):
            try:
                gr.Markdown("### 💾 Export Chat")
                with gr.Group(elem_classes=["su-card"]):
                    fmt = gr.Radio(["Markdown (.md)", "Plain Text (.txt)"], label="Format", value="Markdown (.md)")
                    filename = gr.Textbox(label="Filename", value="chat_export", placeholder="Enter filename without extension")
                    export_btn = gr.Button("⬇️ Export to Drive", variant="primary")
                    status = gr.Textbox(label="Status", interactive=False)
                    link = gr.HTML()

                    def on_export(sel_fmt, name):
                        return export_chat(get_history(), sel_fmt, name)

                    export_btn.click(on_export, [fmt, filename], [status, link], show_progress=False)
            except Exception as e:
                gr.Markdown(f"⚠️ Export Chat unavailable: {e}")

        with gr.Tab("📊 System Status"):
            try:
                gr.Markdown("### 📊 Session Status")
                with gr.Group(elem_classes=["su-card"]):
                    status_card = gr.HTML(build_status_card())
                    refresh = gr.Button("🔄 Refresh")
                    refresh.click(lambda: build_status_card(), None, status_card, show_progress=False)
            except Exception as e:
                gr.Markdown(f"⚠️ System Status unavailable: {e}")

        with gr.Tab("🎭 Personas"):
            try:
                gr.Markdown("### 🎭 Quick Persona")
                with gr.Group(elem_classes=["su-card"]):
                    active = gr.Textbox(label="Active Persona", value="None", interactive=False)
                    persona_status = gr.Textbox(label="Status", interactive=False)
                    fallback_prompt = gr.Textbox(label="Fallback System Prompt (copy if needed)", lines=6, interactive=True)
                    with gr.Row():
                        for label, prompt in PERSONAS[:3]:
                            btn = gr.Button(label)
                            btn.click(lambda n=label, p=prompt: switch_persona(n, p), None, [persona_status, active, fallback_prompt], show_progress=False)
                    with gr.Row():
                        for label, prompt in PERSONAS[3:]:
                            btn = gr.Button(label)
                            btn.click(lambda n=label, p=prompt: switch_persona(n, p), None, [persona_status, active, fallback_prompt], show_progress=False)
            except Exception as e:
                gr.Markdown(f"⚠️ Personas unavailable: {e}")

        with gr.Tab("📝 Notes"):
            try:
                gr.Markdown("### 📝 My Notes")
                with gr.Group(elem_classes=["su-card"]):
                    notes = gr.Textbox(label="Notes (auto-saved to Drive)", lines=10, placeholder="Type notes here...", value=load_notes())
                    with gr.Row():
                        save_btn = gr.Button("💾 Save Notes", variant="primary")
                        clear_btn = gr.Button("🗑️ Clear", variant="stop")
                        copy_btn = gr.Button("📋 Copy to Clipboard")
                    notes_status = gr.Textbox(label="", interactive=False)

                    save_btn.click(save_notes, notes, notes_status, show_progress=False)
                    clear_btn.click(clear_notes, None, [notes, notes_status], show_progress=False)
                    copy_btn.click(None, None, None, js="() => { const t=document.querySelector('textarea[aria-label=\"Notes (auto-saved to Drive)\"]'); if(t){navigator.clipboard.writeText(t.value);} }")
            except Exception as e:
                gr.Markdown(f"⚠️ Notes unavailable: {e}")

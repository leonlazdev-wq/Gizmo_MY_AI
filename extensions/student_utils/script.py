<<<<<<< codex/add-model-download-hub-extension-he6kfh
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4
=======
import os
import re
from datetime import datetime
from pathlib import Path
>>>>>>> main

import gradio as gr
import psutil

params = {
    "display_name": "🛠️ Student Utils",
    "is_tab": True,
}

<<<<<<< codex/add-model-download-hub-extension-he6kfh
SESSION_START = datetime.now()
MAX_ACTIVITY_ITEMS = 50

STRINGS = {
    "quick_prompts": "### ⚡ Quick Prompts",
    "export": "### 💾 Export Chat",
    "status": "### 📊 Session Status",
    "persona": "### 🎭 Quick Persona",
    "notes": "### 📝 My Notes",
    "activity": "### 🔔 Activity",
    "ready": "Ready.",
}

=======
>>>>>>> main
PERSONAS = [
    ("🎓 Tutor", "You are a patient and encouraging tutor. You explain things clearly, check for understanding, and never make the student feel bad for not knowing something. Always ask 'Does that make sense?' at the end of explanations."),
    ("💻 Coder", "You are an expert software engineer and coding mentor. You write clean, well-commented production code. You explain WHY you made each coding choice, not just what the code does. You never write pseudocode — always real, working code."),
    ("✍️ Writing Coach", "You are a writing coach who helps students write better essays, stories, and reports. You give specific, actionable feedback. You point out what is working well AND what needs improvement. You help the student improve their own writing rather than writing it for them."),
    ("🌍 Translator", "You are a professional translator and language teacher. You translate accurately while preserving tone and meaning. When asked to translate, you also point out interesting vocabulary or phrases the student might want to learn."),
    ("🧮 Math Helper", "You are a math tutor who specializes in making math feel approachable. You solve problems step by step, never skipping steps. You connect math concepts to real-world examples. If a student makes a mistake, you guide them to find the error themselves rather than just correcting it."),
    ("⚔️ Debate Partner", "You are a debate coach and sparring partner. When the student states a position, you steelman the opposing view — arguing against them with the strongest possible counterarguments. This helps them prepare for real debates and think critically. After the debate, you give coaching on how they can strengthen their arguments."),
]

<<<<<<< codex/add-model-download-hub-extension-he6kfh
NOTES_FILE_CANDIDATES = [Path("/content/drive/MyDrive/MY-AI-Gizmo/notes.txt"), Path("/content/MY-AI-Gizmo/notes.txt")]
EXPORT_DIR_CANDIDATES = [Path("/content/drive/MyDrive/MY-AI-Gizmo/exports"), Path("/content/MY-AI-Gizmo/exports")]
=======
NOTES_FILE_CANDIDATES = [
    Path("/content/drive/MyDrive/MY-AI-Gizmo/notes.txt"),
    Path("/content/MY-AI-Gizmo/notes.txt"),
]
>>>>>>> main


def card_style():
    return """
    <style>
      .su-card{background:#1e1e2e;border:1px solid #333355;border-radius:12px;padding:14px;color:#e0e0f0;}
      .su-muted{color:#aaaacc;font-size:.9em}
<<<<<<< codex/add-model-download-hub-extension-he6kfh
      .su-link a{color:#8ec8ff;text-decoration:underline;}
      .su-list{margin:0;padding-left:18px;display:grid;gap:6px}
      .su-help{font-size:.92em;color:#aab0cf}
      .su-activity-list{display:grid;gap:8px;max-height:360px;overflow:auto}
      .su-activity-item{border:1px solid #303552;border-radius:10px;padding:8px 10px;background:#171a2b}
      .su-activity-item.unread{border-color:#4a90d9}
      .su-activity-meta{display:flex;justify-content:space-between;font-size:.8em;color:#9da3c7}
      .su-activity-msg{margin-top:4px;color:#e0e0f0;line-height:1.35}
=======
      .su-link a{color:#8ec8ff !important;text-decoration:underline;}
>>>>>>> main
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


<<<<<<< codex/add-model-download-hub-extension-he6kfh
def _pair_values(item):
    if isinstance(item, (list, tuple)):
        user = str(item[0]) if len(item) > 0 and item[0] is not None else ""
        bot = str(item[1]) if len(item) > 1 and item[1] is not None else ""
        return user, bot
    return "", ""


def sanitize_filename(filename):
    return re.sub(r"[^\w\-_]", "_", (filename or "").strip()) or "chat_export"


def _add_activity(activity, message, level="info"):
    event = {"id": str(uuid4()), "message": message, "timestamp": datetime.now().isoformat(timespec="seconds"), "level": level, "read": False}
    return ([event] + list(activity or []))[:MAX_ACTIVITY_ITEMS]


def _relative_time(iso_ts):
    try:
        sec = max(0, int((datetime.now() - datetime.fromisoformat(iso_ts)).total_seconds()))
        if sec < 60:
            return f"{sec}s ago"
        if sec < 3600:
            return f"{sec // 60}m ago"
        return f"{sec // 3600}h ago"
    except Exception:
        return "just now"


def render_activity(activity):
    items = list(activity or [])
    if not items:
        return "<div class='su-card su-muted'>No activity yet.</div>", "0"
    unread = sum(1 for i in items if not i.get("read"))
    parts = ["<div class='su-card'><div class='su-activity-list' role='list'>"]
    for item in items:
        cls = "su-activity-item unread" if not item.get("read") else "su-activity-item"
        parts.append(f"<div class='{cls}' role='listitem'><div class='su-activity-meta'><span>{item.get('level','info').upper()}</span><span>{_relative_time(item.get('timestamp',''))}</span></div><div class='su-activity-msg'>{item.get('message','')}</div></div>")
    parts.append("</div></div>")
    return "".join(parts), str(unread)


def mark_all_read(activity):
    updated = [{**i, "read": True} for i in list(activity or [])]
    html, unread = render_activity(updated)
    return updated, html, unread


def clear_activity():
    html, unread = render_activity([])
    return [], html, unread


def add_activity(activity, message, level="info"):
    updated = _add_activity(activity, message, level)
    html, unread = render_activity(updated)
    return updated, html, unread


def export_chat(history, fmt, filename):
    if not history:
        return "⚠️ Start a chat first, then export.", "", False
    full_name = f"{sanitize_filename(filename)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{'.md' if 'Markdown' in (fmt or '') else '.txt'}"
    for base in EXPORT_DIR_CANDIDATES:
=======
def export_chat(history, fmt, filename):
    safe_name = re.sub(r"[^\w\-_]", "_", (filename or "").strip()) or "chat_export"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".md" if "Markdown" in (fmt or "") else ".txt"
    full_name = f"{safe_name}_{timestamp}{ext}"

    if not history:
        return "⚠️ Start a chat first, then export.", ""

    for base in (Path("/content/drive/MyDrive/MY-AI-Gizmo/exports"), Path("/content/MY-AI-Gizmo/exports")):
>>>>>>> main
        try:
            base.mkdir(parents=True, exist_ok=True)
            out_path = base / full_name
            lines = []
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
<<<<<<< codex/add-model-download-hub-extension-he6kfh
            if "Markdown" in (fmt or ""):
                lines.append(f"# Chat Export — {now}\n")
                for i, item in enumerate(history, 1):
                    user, bot = _pair_values(item)
                    lines.extend([f"## Turn {i}\n", f"**You:** {user}\n", f"**AI:** {bot}\n"])
            else:
                lines.append(f"Chat Export — {now}\n")
                for i, item in enumerate(history, 1):
                    user, bot = _pair_values(item)
                    lines.extend([f"[{i}] You: {user}\n", f"[{i}] AI:  {bot}\n"])
            out_path.write_text("\n".join(lines), encoding="utf-8")
            return f"✅ Saved: {out_path}", f"<div class='su-link'><a href='file={out_path}'>📄 {full_name}</a></div>", True
        except Exception:
            continue
    return "❌ Could not save file — check Drive is mounted", "", False


def _uptime_text():
    total = int((datetime.now() - SESSION_START).total_seconds())
    return f"{total//3600:02d}:{(total%3600)//60:02d}:{total%60:02d}"
=======
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
>>>>>>> main


def build_status_card():
    vm = psutil.virtual_memory()
    ram_used_gb = vm.used / 1024**3
    ram_total_gb = vm.total / 1024**3
    ram_pct = vm.percent
<<<<<<< codex/add-model-download-hub-extension-he6kfh
    ram_bar = "█" * max(0, min(20, int(ram_pct / 5))) + "░" * (20 - max(0, min(20, int(ram_pct / 5))))
    ram_color = "#e74c3c" if ram_pct > 85 else "#f39c12" if ram_pct > 65 else "#2ecc71"
    cpu_pct = psutil.cpu_percent(interval=0.1)
=======
    ram_bar_fill = int(ram_pct / 5)
    ram_bar = "█" * ram_bar_fill + "░" * (20 - ram_bar_fill)
    ram_color = "#e74c3c" if ram_pct > 85 else "#f39c12" if ram_pct > 65 else "#2ecc71"

    cpu_pct = psutil.cpu_percent(interval=0.1)

>>>>>>> main
    model_name = "None loaded"
    try:
        import modules.shared as shared

        if getattr(shared, "model_name", None):
<<<<<<< codex/add-model-download-hub-extension-he6kfh
            model_name = str(shared.model_name)
    except Exception:
        pass
    drive_info = ""
    try:
        du = psutil.disk_usage("/content/drive/MyDrive")
        drive_info = f"<tr><td style='padding:4px 8px;color:#888'>📁 Drive</td><td style='padding:4px 8px'>{du.used/1024**3:.1f} / {du.total/1024**3:.1f} GB</td></tr>"
    except Exception:
        pass
    return f"<div class='su-card' style='font-family:monospace'><div class='su-muted' style='margin-bottom:10px'>Updated: {datetime.now().strftime('%H:%M:%S')}</div><table style='width:100%;border-collapse:collapse;color:#e0e0f0'><tr><td style='padding:4px 8px;color:#888'>🧠 RAM</td><td style='padding:4px 8px'><span style='color:{ram_color}'>{ram_bar}</span><span style='margin-left:8px'>{ram_used_gb:.1f} / {ram_total_gb:.1f} GB ({ram_pct:.0f}%)</span></td></tr><tr><td style='padding:4px 8px;color:#888'>⚙️ CPU</td><td style='padding:4px 8px'>{cpu_pct:.0f}%</td></tr><tr><td style='padding:4px 8px;color:#888'>🤖 Model</td><td style='padding:4px 8px'>{model_name}</td></tr><tr><td style='padding:4px 8px;color:#888'>⏱️ Uptime</td><td style='padding:4px 8px'>{_uptime_text()}</td></tr>{drive_info}</table></div>"
=======
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
>>>>>>> main


def switch_persona(persona_name, system_prompt):
    try:
        import modules.shared as shared

        if hasattr(shared, "settings") and isinstance(shared.settings, dict):
            shared.settings["instruction_template_str"] = system_prompt
            shared.settings["system_message"] = system_prompt
<<<<<<< codex/add-model-download-hub-extension-he6kfh
            return f"✅ Switched to: {persona_name}", persona_name, "", True
        return "⚠️ Could not switch automatically. Copy the prompt below.", persona_name, system_prompt, False
    except Exception as e:
        return f"⚠️ Could not switch automatically ({e}). Copy the prompt below.", persona_name, system_prompt, False
=======
        return f"✅ Switched to: {persona_name}", persona_name, ""
    except Exception as e:
        msg = (
            f"⚠️ Could not switch automatically ({e}). Copy and paste prompt manually."
        )
        return msg, persona_name, system_prompt
>>>>>>> main


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
<<<<<<< codex/add-model-download-hub-extension-he6kfh
            return f"✅ Saved at {datetime.now().strftime('%H:%M:%S')}", True
        except Exception:
            continue
    return "❌ Could not save — Drive may not be mounted", False


def clear_notes():
    status, ok = save_notes("")
    return "", status, ok
=======
            return f"✅ Saved at {datetime.now().strftime('%H:%M:%S')}"
        except Exception:
            continue
    return "❌ Could not save — Drive may not be mounted"


def clear_notes():
    status = save_notes("")
    return "", status
>>>>>>> main


def ui():
    gr.HTML(card_style())
<<<<<<< codex/add-model-download-hub-extension-he6kfh
    activity_state = gr.State([])

    with gr.Tabs():
        with gr.Tab("⚡ Quick Prompts"):
            try:
                gr.Markdown(STRINGS["quick_prompts"])
                with gr.Group(elem_classes=["su-card"]):
                    gr.Markdown("<ul class='su-list'><li>Explain this topic like I’m 12.</li><li>Quiz me on this chapter.</li><li>Turn these notes into flashcards.</li><li>Summarize this in 5 bullet points.</li></ul>")
=======
    with gr.Tabs():
        with gr.Tab("⚡ Quick Prompts"):
            try:
                gr.Markdown("### ⚡ Quick Prompts")
                with gr.Group(elem_classes=["su-card"]):
                    gr.Markdown("Use these starter prompts:")
                    gr.Markdown("- Explain this topic like I'm 12.\n- Quiz me on this chapter.\n- Turn these notes into flashcards.\n- Summarize this in 5 bullet points.")
>>>>>>> main
            except Exception as e:
                gr.Markdown(f"⚠️ Quick Prompts unavailable: {e}")

        with gr.Tab("💾 Export Chat"):
            try:
<<<<<<< codex/add-model-download-hub-extension-he6kfh
                gr.Markdown(STRINGS["export"])
=======
                gr.Markdown("### 💾 Export Chat")
>>>>>>> main
                with gr.Group(elem_classes=["su-card"]):
                    fmt = gr.Radio(["Markdown (.md)", "Plain Text (.txt)"], label="Format", value="Markdown (.md)")
                    filename = gr.Textbox(label="Filename", value="chat_export", placeholder="Enter filename without extension")
                    export_btn = gr.Button("⬇️ Export to Drive", variant="primary")
                    status = gr.Textbox(label="Status", interactive=False)
                    link = gr.HTML()
<<<<<<< codex/add-model-download-hub-extension-he6kfh
                    gr.Markdown("<div class='su-help'>If Drive is not mounted, export falls back to local /content.</div>")

                    def on_export(activity, f, n):
                        msg, file_link, ok = export_chat(get_history(), f, n)
                        activity, _, _ = add_activity(activity, msg, "success" if ok else "warning")
                        return msg, file_link, activity

                    export_btn.click(on_export, [activity_state, fmt, filename], [status, link, activity_state], show_progress=False)
=======

                    def on_export(sel_fmt, name):
                        return export_chat(get_history(), sel_fmt, name)

                    export_btn.click(on_export, [fmt, filename], [status, link], show_progress=False)
>>>>>>> main
            except Exception as e:
                gr.Markdown(f"⚠️ Export Chat unavailable: {e}")

        with gr.Tab("📊 System Status"):
            try:
<<<<<<< codex/add-model-download-hub-extension-he6kfh
                gr.Markdown(STRINGS["status"])
                with gr.Group(elem_classes=["su-card"]):
                    status_card = gr.HTML(build_status_card())
                    refresh = gr.Button("🔄 Refresh")
                    refresh.click(build_status_card, None, status_card, show_progress=False)
=======
                gr.Markdown("### 📊 Session Status")
                with gr.Group(elem_classes=["su-card"]):
                    status_card = gr.HTML(build_status_card())
                    refresh = gr.Button("🔄 Refresh")
                    refresh.click(lambda: build_status_card(), None, status_card, show_progress=False)
>>>>>>> main
            except Exception as e:
                gr.Markdown(f"⚠️ System Status unavailable: {e}")

        with gr.Tab("🎭 Personas"):
            try:
<<<<<<< codex/add-model-download-hub-extension-he6kfh
                gr.Markdown(STRINGS["persona"])
                with gr.Group(elem_classes=["su-card"]):
                    active = gr.Textbox(label="Active Persona", value="None", interactive=False)
                    persona_status = gr.Textbox(label="Status", value=STRINGS["ready"], interactive=False)
                    fallback_prompt = gr.Textbox(label="Fallback System Prompt (copy if needed)", lines=6, interactive=True)

                    def on_switch(activity, name, prompt):
                        msg, active_name, fallback, ok = switch_persona(name, prompt)
                        activity, _, _ = add_activity(activity, msg, "success" if ok else "warning")
                        return msg, active_name, fallback, activity

                    for row in (PERSONAS[:3], PERSONAS[3:]):
                        with gr.Row():
                            for label, prompt in row:
                                gr.Button(label).click(lambda a, n=label, p=prompt: on_switch(a, n, p), [activity_state], [persona_status, active, fallback_prompt, activity_state], show_progress=False)
=======
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
>>>>>>> main
            except Exception as e:
                gr.Markdown(f"⚠️ Personas unavailable: {e}")

        with gr.Tab("📝 Notes"):
            try:
<<<<<<< codex/add-model-download-hub-extension-he6kfh
                gr.Markdown(STRINGS["notes"])
                with gr.Group(elem_classes=["su-card"]):
                    notes = gr.Textbox(label="Notes (auto-saved to Drive)", lines=10, placeholder="Type notes here...", value=load_notes(), elem_id="su-notes-box")
=======
                gr.Markdown("### 📝 My Notes")
                with gr.Group(elem_classes=["su-card"]):
                    notes = gr.Textbox(label="Notes (auto-saved to Drive)", lines=10, placeholder="Type notes here...", value=load_notes())
>>>>>>> main
                    with gr.Row():
                        save_btn = gr.Button("💾 Save Notes", variant="primary")
                        clear_btn = gr.Button("🗑️ Clear", variant="stop")
                        copy_btn = gr.Button("📋 Copy to Clipboard")
<<<<<<< codex/add-model-download-hub-extension-he6kfh
                    notes_status = gr.Textbox(label="", interactive=False, value=STRINGS["ready"])

                    def on_save(activity, text):
                        msg, ok = save_notes(text)
                        activity, _, _ = add_activity(activity, msg, "success" if ok else "warning")
                        return msg, activity

                    def on_clear(activity):
                        new_text, msg, ok = clear_notes()
                        activity, _, _ = add_activity(activity, msg, "success" if ok else "warning")
                        return new_text, msg, activity

                    save_btn.click(on_save, [activity_state, notes], [notes_status, activity_state], show_progress=False)
                    clear_btn.click(on_clear, [activity_state], [notes, notes_status, activity_state], show_progress=False)
                    copy_btn.click(None, None, notes_status, js="() => { const t=document.querySelector('#su-notes-box textarea'); if(!t){return '⚠️ Could not copy';} navigator.clipboard.writeText(t.value || ''); return '✅ Copied to clipboard'; }")
            except Exception as e:
                gr.Markdown(f"⚠️ Notes unavailable: {e}")

        with gr.Tab("🔔 Activity"):
            try:
                gr.Markdown(STRINGS["activity"])
                with gr.Group(elem_classes=["su-card"]):
                    unread = gr.Textbox(label="Unread", value="0", interactive=False)
                    activity_html = gr.HTML("<div class='su-card su-muted'>No activity yet.</div>")
                    with gr.Row():
                        refresh_btn = gr.Button("Refresh")
                        mark_read_btn = gr.Button("Mark all read")
                        clear_btn = gr.Button("Clear")

                    refresh_btn.click(render_activity, [activity_state], [activity_html, unread], show_progress=False)
                    mark_read_btn.click(mark_all_read, [activity_state], [activity_state, activity_html, unread], show_progress=False)
                    clear_btn.click(clear_activity, None, [activity_state, activity_html, unread], show_progress=False)
            except Exception as e:
                gr.Markdown(f"⚠️ Activity unavailable: {e}")
=======
                    notes_status = gr.Textbox(label="", interactive=False)

                    save_btn.click(save_notes, notes, notes_status, show_progress=False)
                    clear_btn.click(clear_notes, None, [notes, notes_status], show_progress=False)
                    copy_btn.click(None, None, None, js="() => { const t=document.querySelector('textarea[aria-label=\"Notes (auto-saved to Drive)\"]'); if(t){navigator.clipboard.writeText(t.value);} }")
            except Exception as e:
                gr.Markdown(f"⚠️ Notes unavailable: {e}")
>>>>>>> main

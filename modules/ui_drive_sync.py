import gradio as gr

from modules import shared
from modules.google_drive_sync import (
    backup_settings,
    get_backup_stats,
    is_drive_mounted,
    restore_from_drive,
    setup_backup_dir,
)
from modules.utils import gradio


def _status_text() -> str:
    if is_drive_mounted():
        stats = get_backup_stats()
        count = stats.get("chat_count", 0)
        return f"☁️ Google Drive Connected — {count} chat(s) backed up"
    return "⚠️ Drive Not Mounted (run in Google Colab with Drive mounted)"


def _do_backup_now():
    if not is_drive_mounted():
        return "⚠️ Google Drive is not mounted."
    setup_backup_dir()
    backup_settings()
    stats = get_backup_stats()
    return f"✅ Backup complete — {stats.get('chat_count', 0)} chats on Drive at {stats.get('path', '')}"


def _do_restore():
    result = restore_from_drive()
    status = result.get("status", "")
    if status == "Drive not mounted":
        return "⚠️ Google Drive is not mounted."
    return f"✅ Restore complete from {result.get('path', '')}"


def create_ui():
    with gr.Accordion("☁️ Google Drive Auto-Save", open=False, elem_id="drive-sync-accordion"):
        shared.gradio['drive_status'] = gr.Markdown(_status_text())
        shared.gradio['auto_save_drive'] = gr.Checkbox(
            label="Auto-save conversations to Google Drive",
            value=is_drive_mounted() and shared.settings.get('auto_save_to_drive', True),
            interactive=is_drive_mounted(),
            info="Automatically backs up chats to /content/drive/MyDrive/Gizmo_AI_Backups/ after each save."
        )
        with gr.Row():
            shared.gradio['drive_backup_now_btn'] = gr.Button("☁️ Backup Now", elem_classes='refresh-button')
            shared.gradio['drive_restore_btn'] = gr.Button("⬇️ Restore from Drive", elem_classes='refresh-button')
        shared.gradio['drive_action_status'] = gr.Textbox(label="Drive action status", interactive=False)


def create_event_handlers():
    shared.gradio['drive_backup_now_btn'].click(
        _do_backup_now, [], gradio('drive_action_status')
    )
    shared.gradio['drive_restore_btn'].click(
        _do_restore, [], gradio('drive_action_status')
    )
    shared.gradio['auto_save_drive'].change(
        lambda v: shared.settings.update({'auto_save_to_drive': v}) or "",
        gradio('auto_save_drive'), []
    )

"""Gradio UI tab for Backup & Restore."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.backup_restore import (
    backup_to_drive,
    create_backup,
    export_chat_history,
    export_flashcard_deck,
    export_memory,
    export_quiz_results,
    get_backup_history_table,
    import_item,
    is_drive_mounted,
    list_local_backups,
    restore_backup,
)
from modules.utils import gradio


def _do_full_backup():
    """Trigger a full backup and return (status, file_path, history_table)."""
    msg, path = create_backup(include_all=True)
    table = get_backup_history_table()
    if path:
        return msg, gr.update(value=path, visible=True), table
    return msg, gr.update(visible=False), table


def _do_restore(file_obj, pre_backup: bool):
    if file_obj is None:
        return "⚠️ Please upload a backup .zip file first."
    path = file_obj if isinstance(file_obj, str) else file_obj.name
    return restore_backup(path, create_pre_restore_backup=pre_backup)


def _do_drive_backup():
    return backup_to_drive()


def _do_individual_export(item_type: str, deck_name: str):
    if item_type == "flashcards":
        msg, path = export_flashcard_deck(deck_name.strip())
    elif item_type == "quiz_results":
        msg, path = export_quiz_results()
    elif item_type == "memory":
        msg, path = export_memory()
    elif item_type == "chat_history":
        msg, path = export_chat_history()
    else:
        return f"❌ Unknown type: {item_type}", gr.update(visible=False)

    if path:
        return msg, gr.update(value=path, visible=True)
    return msg, gr.update(visible=False)


def _do_individual_import(file_obj, item_type: str):
    if file_obj is None:
        return "⚠️ Please upload a file first."
    path = file_obj if isinstance(file_obj, str) else file_obj.name
    return import_item(path, item_type)


def _refresh_history():
    return get_backup_history_table()


def create_ui() -> None:
    with gr.Tab("💾 Backup & Restore", elem_id="backup-tab"):
        gr.Markdown("## 💾 Data Backup & Restore")
        gr.Markdown(
            "Protect your notes, flashcards, quizzes, chat history, and settings "
            "from Colab session resets."
        )

        # ── Full Backup ──────────────────────────────────────────────────────
        with gr.Accordion("📦 Full Backup", open=True):
            gr.Markdown("Create a `.zip` containing all your data from `user_data/`.")
            shared.gradio['backup_btn'] = gr.Button("🗜️ Create Full Backup", variant="primary")
            shared.gradio['backup_status'] = gr.Markdown("")
            shared.gradio['backup_download'] = gr.File(
                label="⬇️ Download Backup", interactive=False, visible=False
            )

        # ── Restore ──────────────────────────────────────────────────────────
        with gr.Accordion("♻️ Restore from Backup", open=False):
            gr.Markdown("Upload a previously created `.zip` backup to restore your data.")
            shared.gradio['restore_upload'] = gr.File(
                label="Upload .zip backup", file_types=[".zip"], type="filepath"
            )
            shared.gradio['restore_pre_backup'] = gr.Checkbox(
                label="Create safety backup before restoring (recommended)", value=True
            )
            shared.gradio['restore_btn'] = gr.Button("♻️ Restore", variant="primary")
            shared.gradio['restore_status'] = gr.Markdown("")

        # ── Google Drive Auto-Backup ─────────────────────────────────────────
        with gr.Accordion("☁️ Google Drive Auto-Backup", open=False):
            drive_status = "✅ Google Drive is mounted" if is_drive_mounted() else "⚠️ Google Drive is not mounted"
            gr.Markdown(f"**Drive Status:** {drive_status}")
            gr.Markdown(
                "Backups are stored in `Google Drive/Gizmo_Backups/` "
                f"(keeps last 5 backups)."
            )
            shared.gradio['drive_backup_btn'] = gr.Button(
                "☁️ Backup to Google Drive Now", variant="secondary"
            )
            shared.gradio['drive_backup_status'] = gr.Markdown("")

        # ── Individual Export / Import ────────────────────────────────────────
        with gr.Accordion("📤 Individual Export / Import", open=False):
            gr.Markdown("### 📤 Export")
            with gr.Row():
                shared.gradio['export_type'] = gr.Dropdown(
                    label="Item Type",
                    choices=["flashcards", "quiz_results", "memory", "chat_history"],
                    value="flashcards",
                    scale=2,
                )
                shared.gradio['export_deck_name'] = gr.Textbox(
                    label="Deck name (flashcards only)",
                    placeholder="e.g. biology",
                    scale=2,
                )
                shared.gradio['export_btn'] = gr.Button("Export", scale=1)
            shared.gradio['export_status'] = gr.Markdown("")
            shared.gradio['export_file'] = gr.File(
                label="⬇️ Download", interactive=False, visible=False
            )

            gr.Markdown("### 📥 Import")
            with gr.Row():
                shared.gradio['import_type'] = gr.Dropdown(
                    label="Item Type",
                    choices=["flashcards", "quiz_results", "memory", "chat_history"],
                    value="flashcards",
                    scale=2,
                )
                shared.gradio['import_file'] = gr.File(
                    label="Upload .json file", file_types=[".json"], type="filepath", scale=3
                )
                shared.gradio['import_btn'] = gr.Button("Import", scale=1)
            shared.gradio['import_status'] = gr.Markdown("")

        # ── Backup History ────────────────────────────────────────────────────
        with gr.Accordion("🕑 Backup History", open=False):
            shared.gradio['backup_history_table'] = gr.Dataframe(
                headers=["Name", "Size", "Date", "Location"],
                datatype=["str", "str", "str", "str"],
                value=get_backup_history_table(),
                interactive=False,
                label="Recent Backups",
            )
            shared.gradio['backup_history_refresh'] = gr.Button("🔄 Refresh")


def create_event_handlers() -> None:
    shared.gradio['backup_btn'].click(
        _do_full_backup,
        inputs=[],
        outputs=[
            shared.gradio['backup_status'],
            shared.gradio['backup_download'],
            shared.gradio['backup_history_table'],
        ],
        show_progress=True,
    )

    shared.gradio['restore_btn'].click(
        _do_restore,
        inputs=[shared.gradio['restore_upload'], shared.gradio['restore_pre_backup']],
        outputs=[shared.gradio['restore_status']],
        show_progress=True,
    )

    shared.gradio['drive_backup_btn'].click(
        _do_drive_backup,
        inputs=[],
        outputs=[shared.gradio['drive_backup_status']],
        show_progress=True,
    )

    shared.gradio['export_btn'].click(
        _do_individual_export,
        inputs=[shared.gradio['export_type'], shared.gradio['export_deck_name']],
        outputs=[shared.gradio['export_status'], shared.gradio['export_file']],
        show_progress=True,
    )

    shared.gradio['import_btn'].click(
        _do_individual_import,
        inputs=[shared.gradio['import_file'], shared.gradio['import_type']],
        outputs=[shared.gradio['import_status']],
        show_progress=True,
    )

    shared.gradio['backup_history_refresh'].click(
        _refresh_history,
        inputs=[],
        outputs=[shared.gradio['backup_history_table']],
        show_progress=False,
    )

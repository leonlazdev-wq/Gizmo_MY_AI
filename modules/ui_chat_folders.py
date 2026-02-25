"""
ui_chat_folders.py — Gradio UI components for chat folder management.

Provides:
  create_ui()              — renders the folder management panel
  create_event_handlers()  — wires folder CRUD operations to Gradio events
"""

import gradio as gr

from modules import shared
from modules.chat_folders import (
    create_folder,
    delete_folder,
    get_folder_list,
    rename_folder,
)
from modules.utils import gradio as _gradio


def _folder_choices() -> list:
    return ["All Chats", "Unfiled"] + get_folder_list()


def create_ui():
    """Render the folder management accordion inside the chat tab."""
    with gr.Accordion("📁 Chat Folders", open=False, elem_id="chat-folders-accordion"):
        shared.gradio["folder_filter"] = gr.Dropdown(
            choices=_folder_choices(),
            value="All Chats",
            label="Filter by folder",
            elem_id="folder-filter-dropdown",
        )

        with gr.Row():
            shared.gradio["new_folder_name"] = gr.Textbox(
                label="New folder name",
                placeholder="e.g. Math, History…",
                elem_id="new-folder-name",
            )
            shared.gradio["new_folder_color"] = gr.ColorPicker(
                value="#4F46E5",
                label="Color",
                elem_id="new-folder-color",
            )

        shared.gradio["create_folder_btn"] = gr.Button(
            "📁 Create Folder", elem_id="create-folder-btn"
        )
        shared.gradio["folder_action_status"] = gr.Textbox(
            label="Status",
            interactive=False,
            elem_id="folder-action-status",
        )

        gr.Markdown("**Rename / Delete existing folder:**")
        with gr.Row():
            shared.gradio["manage_folder_name"] = gr.Dropdown(
                choices=get_folder_list(),
                label="Folder",
                elem_id="manage-folder-name",
            )
            shared.gradio["rename_folder_input"] = gr.Textbox(
                label="New name",
                placeholder="Leave blank to skip rename",
                elem_id="rename-folder-input",
            )

        with gr.Row():
            shared.gradio["rename_folder_btn"] = gr.Button(
                "✏️ Rename", elem_id="rename-folder-btn"
            )
            shared.gradio["delete_folder_btn"] = gr.Button(
                "🗑️ Delete folder (chats kept)", elem_id="delete-folder-btn"
            )


def create_event_handlers():
    """Wire folder CRUD buttons to their backend functions."""
    from modules.chat_folders import load_folders

    def _create(name, color):
        if not name or not name.strip():
            return "⚠️ Please enter a folder name.", gr.Dropdown.update(choices=_folder_choices()), gr.Dropdown.update(choices=get_folder_list())
        create_folder(name.strip(), color)
        return (
            f"✅ Folder '{name.strip()}' created.",
            gr.Dropdown.update(choices=_folder_choices(), value="All Chats"),
            gr.Dropdown.update(choices=get_folder_list()),
        )

    def _rename(folder_name, new_name):
        if not folder_name:
            return "⚠️ Select a folder first.", gr.Dropdown.update(choices=get_folder_list())
        if not new_name or not new_name.strip():
            return "⚠️ Enter a new name.", gr.Dropdown.update(choices=get_folder_list())
        data = load_folders()
        folder_id = next((f["id"] for f in data["folders"] if f["name"] == folder_name), None)
        if folder_id is None:
            return "⚠️ Folder not found.", gr.Dropdown.update(choices=get_folder_list())
        rename_folder(folder_id, new_name.strip())
        return (
            f"✅ Renamed to '{new_name.strip()}'.",
            gr.Dropdown.update(choices=get_folder_list()),
        )

    def _delete(folder_name):
        if not folder_name:
            return "⚠️ Select a folder first.", gr.Dropdown.update(choices=_folder_choices()), gr.Dropdown.update(choices=get_folder_list())
        data = load_folders()
        folder_id = next((f["id"] for f in data["folders"] if f["name"] == folder_name), None)
        if folder_id is None:
            return "⚠️ Folder not found.", gr.Dropdown.update(choices=_folder_choices()), gr.Dropdown.update(choices=get_folder_list())
        delete_folder(folder_id)
        return (
            f"✅ Folder '{folder_name}' deleted.",
            gr.Dropdown.update(choices=_folder_choices(), value="All Chats"),
            gr.Dropdown.update(choices=get_folder_list()),
        )

    shared.gradio["create_folder_btn"].click(
        _create,
        [shared.gradio["new_folder_name"], shared.gradio["new_folder_color"]],
        [
            shared.gradio["folder_action_status"],
            shared.gradio["folder_filter"],
            shared.gradio["manage_folder_name"],
        ],
    )

    shared.gradio["rename_folder_btn"].click(
        _rename,
        [shared.gradio["manage_folder_name"], shared.gradio["rename_folder_input"]],
        [
            shared.gradio["folder_action_status"],
            shared.gradio["manage_folder_name"],
        ],
    )

    shared.gradio["delete_folder_btn"].click(
        _delete,
        [shared.gradio["manage_folder_name"]],
        [
            shared.gradio["folder_action_status"],
            shared.gradio["folder_filter"],
            shared.gradio["manage_folder_name"],
        ],
    )

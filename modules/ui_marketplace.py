"""Marketplace tab for plugin browsing and install/enable/disable."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.plugin_manager import disable_plugin, enable_plugin, install_plugin, list_plugins
from modules.utils import gradio


def create_ui() -> None:
    """Render Marketplace tab."""
    with gr.Tab("Marketplace", elem_id="marketplace-tab"):
        gr.Markdown("## 🧩 Plugin Marketplace")
        # Visual mock: [card][card][card] with Install/Enable/Disable
        shared.gradio['mk_search'] = gr.Textbox(label='Search plugins', placeholder='Search plugins...')
        with gr.Row():
            shared.gradio['mk_path'] = gr.Textbox(label='Install from local path', value='dev_tools/sample_plugin')
            shared.gradio['mk_name'] = gr.Textbox(label='Plugin name', value='sample_plugin')
        with gr.Row():
            shared.gradio['mk_install'] = gr.Button('Install')
            shared.gradio['mk_enable'] = gr.Button('Enable')
            shared.gradio['mk_disable'] = gr.Button('Disable')
        shared.gradio['mk_status'] = gr.Textbox(label='Status', interactive=False)
        shared.gradio['mk_list'] = gr.JSON(label='Plugin cards')


def create_event_handlers() -> None:
    """Wire marketplace handlers."""
    shared.gradio['mk_search'].change(lambda _q: list_plugins(), gradio('mk_search'), gradio('mk_list'), show_progress=False)
    shared.gradio['mk_install'].click(lambda p: f"✅ Installed {install_plugin(p)}", gradio('mk_path'), gradio('mk_status'), show_progress=False).then(
        lambda: list_plugins(), None, gradio('mk_list'), show_progress=False
    )
    shared.gradio['mk_enable'].click(lambda n: (enable_plugin(n), f"✅ Enabled {n}")[1], gradio('mk_name'), gradio('mk_status'), show_progress=False).then(
        lambda: list_plugins(), None, gradio('mk_list'), show_progress=False
    )
    shared.gradio['mk_disable'].click(lambda n: (disable_plugin(n), f"✅ Disabled {n}")[1], gradio('mk_name'), gradio('mk_status'), show_progress=False).then(
        lambda: list_plugins(), None, gradio('mk_list'), show_progress=False
    )

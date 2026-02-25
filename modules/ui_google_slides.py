"""Gradio UI tab for the Google Slides integration."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.google_slides import (
    add_image_to_slide,
    add_text_to_slide,
    change_slide_background,
    connect_presentation,
    export_slide_as_image,
    get_current_state,
    get_slide_content,
    get_slides_info,
)

TUTORIAL_URL = "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#google-slides-connection"


def _slide_choices(slide_count: int) -> list:
    return [f"Slide {i + 1}" for i in range(slide_count)]


def _connect(pres_url, creds_path):
    msg, info = connect_presentation(pres_url, creds_path)
    slide_count = info.get("slide_count", 0)
    title = info.get("title", "")
    status_html = (
        f"<div style='color:#4CAF50;font-weight:600'>{msg}</div>"
        if "✅" in msg
        else f"<div style='color:#f44336'>{msg}</div>"
    )
    choices = _slide_choices(slide_count)
    header = f"**{title}** — {slide_count} slide(s)" if title else ""
    return status_html, gr.update(choices=choices, value=choices[0] if choices else None), header


def _get_slide_info():
    msg, slides = get_slides_info()
    if not slides:
        return msg, ""
    lines = [f"**Slide {s['slide_number']}** — {s['element_count']} element(s) (ID: `{s['object_id']}`)" for s in slides]
    return msg, "\n".join(lines)


def _get_slide_content(slide_choice):
    if not slide_choice:
        return "No slide selected.", ""
    idx = int(slide_choice.replace("Slide ", "")) - 1
    msg, elements = get_slide_content(idx)
    if not elements:
        return msg, ""
    lines = []
    for el in elements:
        text = el.get("text", "").replace("\n", " ")
        if text:
            lines.append(f"- `{el['object_id']}`: {text}")
    return msg, "\n".join(lines) if lines else "No text elements found on this slide."


def _add_text(slide_choice, text, x, y, width, height):
    if not slide_choice:
        return "No slide selected."
    idx = int(slide_choice.replace("Slide ", "")) - 1
    pos = {"x": float(x), "y": float(y), "width": float(width), "height": float(height)}
    return add_text_to_slide(idx, text, pos)


def _add_image(slide_choice, image_url, x, y, width, height):
    if not slide_choice:
        return "No slide selected."
    idx = int(slide_choice.replace("Slide ", "")) - 1
    pos = {"x": float(x), "y": float(y), "width": float(width), "height": float(height)}
    return add_image_to_slide(idx, image_url, pos)


def _change_bg(slide_choice, color_or_url):
    if not slide_choice:
        return "No slide selected."
    idx = int(slide_choice.replace("Slide ", "")) - 1
    return change_slide_background(idx, color_or_url)


def _screenshot(slide_choice):
    if not slide_choice:
        return "No slide selected.", None
    idx = int(slide_choice.replace("Slide ", "")) - 1
    msg, path = export_slide_as_image(idx)
    return msg, path


def create_ui():
    with gr.Tab("📊 Google Slides", elem_id="google-slides-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: How to set up Google Slides integration</a>"
            f"</div>"
        )

        with gr.Accordion("🔌 Connect to Presentation", open=True):
            gr.Markdown(
                "Enter your Google Slides URL or Presentation ID, and the path to your "
                "service account credentials JSON file."
            )
            with gr.Row():
                shared.gradio['gs_pres_url'] = gr.Textbox(
                    label="Presentation URL or ID",
                    placeholder="https://docs.google.com/presentation/d/... or just the ID",
                    scale=3,
                )
                shared.gradio['gs_creds_path'] = gr.Textbox(
                    label="Credentials JSON path",
                    placeholder="/path/to/service-account.json",
                    scale=2,
                )
            shared.gradio['gs_connect_btn'] = gr.Button("🔌 Connect", variant="primary")
            shared.gradio['gs_status_html'] = gr.HTML(
                value="<div style='color:#888'>Not connected</div>"
            )
            shared.gradio['gs_pres_header'] = gr.Markdown("")

        with gr.Row():
            shared.gradio['gs_slide_selector'] = gr.Dropdown(
                label="Active Slide",
                choices=[],
                value=None,
                interactive=True,
            )
            shared.gradio['gs_list_slides_btn'] = gr.Button("🔄 List Slides", size="sm")

        shared.gradio['gs_slides_info'] = gr.Markdown("")

        with gr.Accordion("📖 View Slide Content", open=False):
            shared.gradio['gs_view_btn'] = gr.Button("📖 View Slide Content")
            shared.gradio['gs_view_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['gs_view_content'] = gr.Markdown("")

        with gr.Accordion("✏️ Add Text", open=False):
            shared.gradio['gs_text_input'] = gr.Textbox(label="Text to add", lines=3)
            with gr.Row():
                shared.gradio['gs_text_x'] = gr.Number(label="X (PT)", value=100, precision=1)
                shared.gradio['gs_text_y'] = gr.Number(label="Y (PT)", value=100, precision=1)
                shared.gradio['gs_text_w'] = gr.Number(label="Width (PT)", value=400, precision=1)
                shared.gradio['gs_text_h'] = gr.Number(label="Height (PT)", value=80, precision=1)
            shared.gradio['gs_add_text_btn'] = gr.Button("➕ Add Text", variant="primary")
            shared.gradio['gs_text_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("🖼️ Add Image", open=False):
            shared.gradio['gs_image_url'] = gr.Textbox(
                label="Image URL",
                placeholder="https://example.com/image.png",
            )
            with gr.Row():
                shared.gradio['gs_img_x'] = gr.Number(label="X (PT)", value=100, precision=1)
                shared.gradio['gs_img_y'] = gr.Number(label="Y (PT)", value=100, precision=1)
                shared.gradio['gs_img_w'] = gr.Number(label="Width (PT)", value=300, precision=1)
                shared.gradio['gs_img_h'] = gr.Number(label="Height (PT)", value=200, precision=1)
            shared.gradio['gs_add_image_btn'] = gr.Button("🖼️ Add Image", variant="primary")
            shared.gradio['gs_image_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("🎨 Change Background", open=False):
            shared.gradio['gs_bg_value'] = gr.Textbox(
                label="Color (hex) or Image URL",
                placeholder="#4285f4  or  https://example.com/bg.jpg",
            )
            shared.gradio['gs_bg_btn'] = gr.Button("🎨 Change Background", variant="primary")
            shared.gradio['gs_bg_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("📸 Screenshot / Preview", open=False):
            shared.gradio['gs_screenshot_btn'] = gr.Button("📸 Take Screenshot", variant="primary")
            shared.gradio['gs_screenshot_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['gs_preview_image'] = gr.Image(label="Slide Preview", type="filepath")


def create_event_handlers():
    shared.gradio['gs_connect_btn'].click(
        _connect,
        inputs=[shared.gradio['gs_pres_url'], shared.gradio['gs_creds_path']],
        outputs=[
            shared.gradio['gs_status_html'],
            shared.gradio['gs_slide_selector'],
            shared.gradio['gs_pres_header'],
        ],
        show_progress=False,
    )

    shared.gradio['gs_list_slides_btn'].click(
        _get_slide_info,
        inputs=[],
        outputs=[shared.gradio['gs_view_status'], shared.gradio['gs_slides_info']],
        show_progress=False,
    )

    shared.gradio['gs_view_btn'].click(
        _get_slide_content,
        inputs=[shared.gradio['gs_slide_selector']],
        outputs=[shared.gradio['gs_view_status'], shared.gradio['gs_view_content']],
        show_progress=False,
    )

    shared.gradio['gs_add_text_btn'].click(
        _add_text,
        inputs=[
            shared.gradio['gs_slide_selector'],
            shared.gradio['gs_text_input'],
            shared.gradio['gs_text_x'],
            shared.gradio['gs_text_y'],
            shared.gradio['gs_text_w'],
            shared.gradio['gs_text_h'],
        ],
        outputs=[shared.gradio['gs_text_status']],
        show_progress=True,
    )

    shared.gradio['gs_add_image_btn'].click(
        _add_image,
        inputs=[
            shared.gradio['gs_slide_selector'],
            shared.gradio['gs_image_url'],
            shared.gradio['gs_img_x'],
            shared.gradio['gs_img_y'],
            shared.gradio['gs_img_w'],
            shared.gradio['gs_img_h'],
        ],
        outputs=[shared.gradio['gs_image_status']],
        show_progress=True,
    )

    shared.gradio['gs_bg_btn'].click(
        _change_bg,
        inputs=[shared.gradio['gs_slide_selector'], shared.gradio['gs_bg_value']],
        outputs=[shared.gradio['gs_bg_status']],
        show_progress=True,
    )

    shared.gradio['gs_screenshot_btn'].click(
        _screenshot,
        inputs=[shared.gradio['gs_slide_selector']],
        outputs=[shared.gradio['gs_screenshot_status'], shared.gradio['gs_preview_image']],
        show_progress=True,
    )

"""Gradio UI tab for the Google Sheets integration."""

from __future__ import annotations

import gradio as gr
import pandas as pd

from modules import shared
from modules.google_sheets import (
    analyze_data,
    connect_spreadsheet,
    get_current_state,
    get_sheet_metadata,
    get_sheet_names,
    read_all_data,
    read_range,
    suggest_formula,
    write_range,
)

TUTORIAL_URL = "https://github.com/leonlazdev-wq/Gizmo-my-ai-for-google-colab/blob/main/README.md#google-sheets-integration"


def _connect(url, creds):
    msg, info = connect_spreadsheet(url, creds)
    status_html = (
        f"<div style='color:#4CAF50;font-weight:600'>{msg}</div>"
        if "✅" in msg
        else f"<div style='color:#f44336'>{msg}</div>"
    )
    sheets = info.get("sheets", []) if isinstance(info, dict) else []
    title = info.get("title", "") if isinstance(info, dict) else ""
    header = f"**{title}**" if title else ""
    return status_html, gr.update(choices=sheets, value=sheets[0] if sheets else None), header


def _load_sheet_data(sheet_name):
    msg, data = read_all_data(sheet_name)
    if not data:
        return msg, pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame(data)
    return msg, df


def _read_range(range_str):
    msg, data = read_range(range_str)
    if not data:
        return msg, pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame(data)
    return msg, df


def _write_data(range_str, values_text):
    if not values_text:
        return "No values provided."
    rows = [line.split(",") for line in values_text.strip().splitlines()]
    return write_range(range_str, rows)


def _analyze(sheet_name):
    msg, analysis = analyze_data(sheet_name)
    return msg, analysis or ""


def _suggest_formula(description):
    msg, formula = suggest_formula(description)
    return msg, formula or ""


def _get_metadata():
    msg, meta = get_sheet_metadata()
    if not isinstance(meta, dict):
        return msg, ""
    lines = [f"**{k}:** {v}" for k, v in meta.items()]
    return msg, "\n\n".join(lines)


def create_ui():
    with gr.Tab("📊 Google Sheets", elem_id="google-sheets-tab"):
        gr.HTML(
            f"<div style='margin-bottom:8px'>"
            f"<a href='{TUTORIAL_URL}' target='_blank' rel='noopener noreferrer' "
            f"style='font-size:.88em;color:#8ec8ff'>📖 Tutorial: How to set up Google Sheets integration</a>"
            f"</div>"
        )

        with gr.Accordion("🔌 Connect", open=True):
            with gr.Row():
                shared.gradio['gsheets_url'] = gr.Textbox(
                    label="Spreadsheet URL or ID",
                    placeholder="https://docs.google.com/spreadsheets/d/... or just the ID",
                    scale=3,
                )
                shared.gradio['gsheets_creds'] = gr.Textbox(
                    label="Credentials JSON path",
                    placeholder="/path/to/service-account.json",
                    scale=2,
                )
            shared.gradio['gsheets_connect_btn'] = gr.Button("🔌 Connect", variant="primary")
            shared.gradio['gsheets_status_html'] = gr.HTML(
                value="<div style='color:#888'>Not connected</div>"
            )
            shared.gradio['gsheets_header'] = gr.Markdown("")

        with gr.Row():
            shared.gradio['gsheets_sheet_selector'] = gr.Dropdown(
                label="Active Sheet",
                choices=[],
                value=None,
                interactive=True,
            )
            shared.gradio['gsheets_refresh_btn'] = gr.Button("🔄 Refresh Data", size="sm")

        with gr.Accordion("📊 Data Viewer", open=False):
            shared.gradio['gsheets_data_df'] = gr.Dataframe(
                label="Sheet Data", interactive=False, wrap=True
            )
            with gr.Row():
                shared.gradio['gsheets_range_input'] = gr.Textbox(
                    label="Range",
                    placeholder="e.g. Sheet1!A1:D10",
                )
                shared.gradio['gsheets_read_range_btn'] = gr.Button("📖 Read Range")

        with gr.Accordion("✏️ Write Data", open=False):
            shared.gradio['gsheets_write_range'] = gr.Textbox(
                label="Target range", placeholder="e.g. Sheet1!A1"
            )
            shared.gradio['gsheets_write_values'] = gr.Textbox(
                label="Values (CSV format)",
                lines=3,
                placeholder="CSV format: val1,val2\nval3,val4",
            )
            shared.gradio['gsheets_write_btn'] = gr.Button("✏️ Write Data", variant="primary")
            shared.gradio['gsheets_write_status'] = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("🤖 AI Actions", open=False):
            with gr.Row():
                shared.gradio['gsheets_analyze_btn'] = gr.Button("📈 Analyze Data")
                shared.gradio['gsheets_formula_btn'] = gr.Button("🧮 Suggest Formula")
                shared.gradio['gsheets_metadata_btn'] = gr.Button("ℹ️ Info")
            shared.gradio['gsheets_formula_input'] = gr.Textbox(
                label="Formula description",
                placeholder="e.g. sum column B where column A is Math",
            )
            shared.gradio['gsheets_ai_status'] = gr.Textbox(label="Status", interactive=False)
            shared.gradio['gsheets_ai_output'] = gr.Textbox(
                label="Output", lines=6, interactive=False
            )


def create_event_handlers():
    shared.gradio['gsheets_connect_btn'].click(
        _connect,
        inputs=[shared.gradio['gsheets_url'], shared.gradio['gsheets_creds']],
        outputs=[
            shared.gradio['gsheets_status_html'],
            shared.gradio['gsheets_sheet_selector'],
            shared.gradio['gsheets_header'],
        ],
        show_progress=False,
    )

    shared.gradio['gsheets_refresh_btn'].click(
        _load_sheet_data,
        inputs=[shared.gradio['gsheets_sheet_selector']],
        outputs=[shared.gradio['gsheets_write_status'], shared.gradio['gsheets_data_df']],
        show_progress=True,
    )

    shared.gradio['gsheets_sheet_selector'].change(
        _load_sheet_data,
        inputs=[shared.gradio['gsheets_sheet_selector']],
        outputs=[shared.gradio['gsheets_write_status'], shared.gradio['gsheets_data_df']],
        show_progress=True,
    )

    shared.gradio['gsheets_read_range_btn'].click(
        _read_range,
        inputs=[shared.gradio['gsheets_range_input']],
        outputs=[shared.gradio['gsheets_write_status'], shared.gradio['gsheets_data_df']],
        show_progress=True,
    )

    shared.gradio['gsheets_write_btn'].click(
        _write_data,
        inputs=[shared.gradio['gsheets_write_range'], shared.gradio['gsheets_write_values']],
        outputs=[shared.gradio['gsheets_write_status']],
        show_progress=True,
    )

    shared.gradio['gsheets_analyze_btn'].click(
        _analyze,
        inputs=[shared.gradio['gsheets_sheet_selector']],
        outputs=[shared.gradio['gsheets_ai_status'], shared.gradio['gsheets_ai_output']],
        show_progress=True,
    )

    shared.gradio['gsheets_formula_btn'].click(
        _suggest_formula,
        inputs=[shared.gradio['gsheets_formula_input']],
        outputs=[shared.gradio['gsheets_ai_status'], shared.gradio['gsheets_ai_output']],
        show_progress=True,
    )

    shared.gradio['gsheets_metadata_btn'].click(
        _get_metadata,
        inputs=[],
        outputs=[shared.gradio['gsheets_ai_status'], shared.gradio['gsheets_ai_output']],
        show_progress=True,
    )

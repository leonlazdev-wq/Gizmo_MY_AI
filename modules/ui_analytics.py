"""Admin analytics dashboard tab."""

from __future__ import annotations

import matplotlib.pyplot as plt
import gradio as gr

from modules import shared
from modules.analytics import compute_kpis, synthetic_metrics
from modules.auth import enforce_permission
from modules.utils import gradio


def _render() -> tuple[str, str, str, object]:
    metrics = synthetic_metrics(50)
    kpi = compute_kpis(metrics["latencies"], failure_count=3, total_requests=sum(metrics["requests"]))
    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.plot(metrics["requests"], color="#4F46E5")
    ax.set_title("Requests over time")
    return (
        f"### {int(kpi['requests'])}\nRequests/day",
        f"### {kpi['avg_latency_ms']} ms\nAvg latency",
        f"### {kpi['failure_rate_pct']}%\nFailure rate",
        fig,
    )


def create_ui() -> None:
    """Render analytics UI, visible to admins."""
    with gr.Tab("Analytics", elem_id="analytics-tab"):
        gr.Markdown("## 📈 Advanced Analytics")
        # Visual mock: [KPI][KPI][KPI] / [Line chart]
        shared.gradio["analytics_user"] = gr.Textbox(label="Current user", value="admin", visible=False)
        shared.gradio["analytics_session"] = gr.Textbox(label="Session", value="default_session", visible=False)
        shared.gradio["analytics_reload_btn"] = gr.Button("Reload analytics")
        with gr.Row():
            shared.gradio["analytics_kpi_req"] = gr.Markdown("### -\nRequests/day")
            shared.gradio["analytics_kpi_lat"] = gr.Markdown("### -\nAvg latency")
            shared.gradio["analytics_kpi_fail"] = gr.Markdown("### -\nFailure rate")
        shared.gradio["analytics_plot"] = gr.Plot()


def create_event_handlers() -> None:
    """Wire analytics refresh with permission gate."""
    def _guarded(user_id: str, session_id: str):
        if not enforce_permission(user_id, session_id, "view_analytics"):
            return "### Access denied", "### -", "### -", None
        return _render()

    shared.gradio["analytics_reload_btn"].click(
        _guarded,
        gradio("analytics_user", "analytics_session"),
        gradio("analytics_kpi_req", "analytics_kpi_lat", "analytics_kpi_fail", "analytics_plot"),
        show_progress=False,
    )

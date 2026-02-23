"""Analytics dashboard UI."""

from __future__ import annotations

import matplotlib.pyplot as plt
import gradio as gr

from modules import shared
from modules.analytics import compute_kpis, top_integrations
from modules.auth import enforce_permission
from modules.utils import gradio


def _sample_events() -> list[dict]:
    return [
        {"latency": (i % 7) * 0.2 + 0.3, "status": "fail" if i % 9 == 0 else "ok", "integration": ["rag", "web", "none"][i % 3]}
        for i in range(50)
    ]


def _render() -> tuple[str, str, str, object, list[list[str]]]:
    if not enforce_permission("local-user", "default", "view_analytics"):
        return "N/A", "N/A", "N/A", None, [["Permission denied", "Assign admin role", "auth"]]
    events = _sample_events()
    k = compute_kpis(events)
    ints = top_integrations(events)

    fig, ax = plt.subplots(figsize=(6, 2.5))
    xs = list(range(len(events)))
    ys = [e["latency"] for e in events]
    ax.plot(xs, ys)
    ax.set_title("Latency over requests")
    ax.set_xlabel("Request #")
    ax.set_ylabel("Latency (s)")

    rows = [[name, str(cnt)] for name, cnt in ints.items()]
    return str(k["requests"]), str(k["avg_latency"]), f"{k['failure_rate']}%", fig, rows


def create_ui() -> None:
    with gr.Tab("Analytics", elem_id="analytics-tab"):
        gr.Markdown("### Advanced Analytics (Admin)")
        # Visual mock: [KPI] [KPI] [KPI] then charts row.
        with gr.Row():
            shared.gradio["analytics_requests"] = gr.Markdown("**Requests/day:** -")
            shared.gradio["analytics_latency"] = gr.Markdown("**Avg latency:** -")
            shared.gradio["analytics_failure"] = gr.Markdown("**Failure rate:** -")
        shared.gradio["analytics_plot"] = gr.Plot()
        shared.gradio["analytics_integrations"] = gr.Dataframe(headers=["Integration", "Count"], row_count=4)
        shared.gradio["analytics_refresh"] = gr.Button("Refresh analytics")


def create_event_handlers() -> None:
    def _refresh():
        req, lat, fail, fig, rows = _render()
        return f"**Requests/day:** {req}", f"**Avg latency:** {lat}s", f"**Failure rate:** {fail}", fig, rows

    shared.gradio["analytics_refresh"].click(
        _refresh,
        [],
        gradio("analytics_requests", "analytics_latency", "analytics_failure", "analytics_plot", "analytics_integrations"),
        show_progress=False,
    )

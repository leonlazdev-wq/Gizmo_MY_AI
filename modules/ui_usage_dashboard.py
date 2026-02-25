import gradio as gr

from modules import shared
from modules.usage_tracker import get_dashboard_data, get_usage_chart_data, load_stats, STATS_FILE
from modules.utils import gradio


def _fmt_tokens(n: int) -> str:
    return f"{n/1000:.1f}K" if n >= 1000 else str(n)


def _fmt_time(secs: float) -> str:
    if secs < 60:
        return f"{secs:.0f}s"
    elif secs < 3600:
        return f"{secs/60:.1f} min"
    return f"{secs/3600:.1f} hrs"


def _build_summary_html() -> str:
    data = get_dashboard_data()
    return f"""
    <div style='display:flex;flex-wrap:wrap;gap:12px;padding:8px 0'>
      <div style='flex:1;min-width:120px;background:#1e1e2e;border:1px solid #333;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:1.6em'>💬</div>
        <div style='font-size:1.3em;font-weight:bold'>{data['today_messages']} / {data['total_messages']}</div>
        <div style='color:#aaa;font-size:.82em'>Messages Today / Total</div>
      </div>
      <div style='flex:1;min-width:120px;background:#1e1e2e;border:1px solid #333;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:1.6em'>📊</div>
        <div style='font-size:1.3em;font-weight:bold'>{_fmt_tokens(data['today_tokens'])} / {_fmt_tokens(data['total_tokens'])}</div>
        <div style='color:#aaa;font-size:.82em'>Tokens Today / Total</div>
      </div>
      <div style='flex:1;min-width:120px;background:#1e1e2e;border:1px solid #333;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:1.6em'>⚡</div>
        <div style='font-size:1.3em;font-weight:bold'>{data['avg_response_time']:.1f}s</div>
        <div style='color:#aaa;font-size:.82em'>Avg Response Time</div>
      </div>
      <div style='flex:1;min-width:120px;background:#1e1e2e;border:1px solid #333;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:1.6em'>🔥</div>
        <div style='font-size:1.3em;font-weight:bold'>{data['streak_days']} days</div>
        <div style='color:#aaa;font-size:.82em'>Current Streak</div>
      </div>
    </div>
    <div style='margin-top:10px;padding:10px;background:#1a1a2e;border:1px solid #333;border-radius:8px'>
      <b>Most-used model:</b> {data['most_used_model']} &nbsp;|&nbsp;
      <b>Total chats:</b> {data['total_chats']} &nbsp;|&nbsp;
      <b>Time generating:</b> {_fmt_time(data['total_gen_time_s'])} &nbsp;|&nbsp;
      <b>First use:</b> {data['first_use']}
    </div>
    """


def _build_chart():
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        chart_data = get_usage_chart_data()
        fig, axes = plt.subplots(1, 2, figsize=(10, 3))
        fig.patch.set_facecolor('#111')

        dates = chart_data["dates"]
        messages = chart_data["messages"]
        tokens_out = chart_data["tokens_out"]
        tokens_in = chart_data["tokens_in"]

        ax1 = axes[0]
        ax1.set_facecolor('#1e1e2e')
        ax1.plot(range(len(dates)), messages, color='#6366F1', linewidth=2, marker='o', markersize=3)
        ax1.set_title("Messages per Day (last 30d)", color='white', fontsize=9)
        ax1.tick_params(colors='#aaa', labelsize=7)
        for spine in ax1.spines.values():
            spine.set_edgecolor('#333')
        if dates:
            step = max(1, len(dates) // 5)
            ax1.set_xticks(range(0, len(dates), step))
            ax1.set_xticklabels([dates[i][-5:] for i in range(0, len(dates), step)], rotation=30, ha='right', fontsize=6)

        ax2 = axes[1]
        ax2.set_facecolor('#1e1e2e')
        x = range(len(dates))
        ax2.bar(x, tokens_out, color='#10B981', alpha=0.8, label='Output')
        ax2.bar(x, tokens_in, bottom=tokens_out, color='#F59E0B', alpha=0.8, label='Input')
        ax2.set_title("Token Usage (last 30d)", color='white', fontsize=9)
        ax2.tick_params(colors='#aaa', labelsize=7)
        for spine in ax2.spines.values():
            spine.set_edgecolor('#333')
        ax2.legend(fontsize=7, labelcolor='white', facecolor='#1e1e2e', edgecolor='#333')

        plt.tight_layout()
        return fig
    except Exception:
        return None


def _export_stats():
    import tempfile, os
    data = load_stats()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w', encoding='utf-8')
    import json
    json.dump(data, tmp, indent=4, ensure_ascii=False)
    tmp.close()
    return tmp.name


def _reset_stats():
    if STATS_FILE.exists():
        STATS_FILE.unlink()
    return "✅ Stats reset."


def create_ui():
    with gr.Tab("Dashboard", elem_id="dashboard-tab"):
        gr.Markdown("## 📊 Your Usage Dashboard")
        shared.gradio['dashboard_summary'] = gr.HTML(_build_summary_html())
        shared.gradio['dashboard_chart'] = gr.Plot(value=_build_chart(), label="Usage Charts")
        with gr.Row():
            shared.gradio['dashboard_refresh_btn'] = gr.Button("🔄 Refresh", elem_classes='refresh-button')
            shared.gradio['dashboard_export_btn'] = gr.Button("⬇️ Export Stats (JSON)", elem_classes='refresh-button')
            shared.gradio['dashboard_reset_btn'] = gr.Button("🗑️ Reset Stats", elem_classes='refresh-button')
        shared.gradio['dashboard_export_file'] = gr.File(label="Download stats", visible=False)
        shared.gradio['dashboard_status'] = gr.Textbox(label="Status", interactive=False, visible=False)


def create_event_handlers():
    shared.gradio['dashboard_refresh_btn'].click(
        lambda: (_build_summary_html(), _build_chart()),
        [],
        gradio('dashboard_summary', 'dashboard_chart')
    )
    shared.gradio['dashboard_export_btn'].click(
        lambda: gr.update(value=_export_stats(), visible=True),
        [],
        gradio('dashboard_export_file')
    )
    shared.gradio['dashboard_reset_btn'].click(
        lambda: (_reset_stats(), gr.update(value=_reset_stats(), visible=True))[1],
        [],
        gradio('dashboard_status')
    )

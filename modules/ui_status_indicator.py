import modules.shared as shared


def get_model_status() -> str:
    """Get current model status as an HTML status bar string."""
    if shared.model is not None:
        model_name = shared.model_name or "Unknown"
        loader = getattr(shared.args, 'loader', None) or "unknown"
        return (
            f"<div id='status-indicator' class='ready'>"
            f"🟢 Ready — {model_name} ({loader})"
            f"</div>"
        )
    elif shared.model_name and shared.model_name != 'None':
        return (
            "<div id='status-indicator' class='loading'>"
            "🟡 Loading model... (this may take a minute)"
            "</div>"
        )
    else:
        return (
            "<div id='status-indicator' class='no-model'>"
            "🔴 No model loaded — go to Model tab to load one"
            "</div>"
        )

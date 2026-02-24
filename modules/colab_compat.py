"""Utilities for validating and rendering extension tabs in Google Colab."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from importlib import import_module
from typing import Dict, List


@dataclass
class ColabCheckResult:
    name: str
    ok: bool
    message: str


def check_frontend_dependencies() -> List[ColabCheckResult]:
    checks: List[ColabCheckResult] = []
    try:
        import_module("IPython.display")
        checks.append(ColabCheckResult("IPython.display", True, "available"))
    except Exception as exc:  # pragma: no cover
        checks.append(ColabCheckResult("IPython.display", False, str(exc)))

    try:
        import_module("google.colab")
        checks.append(ColabCheckResult("google.colab", True, "available"))
    except Exception:
        checks.append(ColabCheckResult("google.colab", False, "not running inside Colab"))

    for module_name in (
        "extensions.learning_center.script",
        "extensions.student_utils.script",
        "extensions.model_hub.script",
    ):
        try:
            import_module(module_name)
            checks.append(ColabCheckResult(module_name, True, "imported"))
        except Exception as exc:
            checks.append(ColabCheckResult(module_name, False, str(exc)))

    return checks


def build_lesson_tabs_html() -> str:
    """Build a Colab-friendly lesson tab UI using plain HTML/CSS/JS."""
    tabs: Dict[str, str] = {
        "📚 Tutorials": "Starter tutorials are available in the in-app Learning Center.",
        "💡 Prompt Library": "Use focused prompts for code, writing, and study sessions.",
        "💬 Community": "Community tips are stored in user_data/tutorials/community_tips.json.",
        "🛠️ Student Utils": "Export chat, monitor session status, switch persona, and keep notes.",
    }

    buttons = []
    panels = []
    for i, (title, body) in enumerate(tabs.items()):
        active = "true" if i == 0 else "false"
        hidden = "" if i == 0 else "hidden"
        buttons.append(
            f"<button class='lc-tab-btn' role='tab' aria-selected='{active}' data-tab='tab-{i}'>{escape(title)}</button>"
        )
        panels.append(
            f"<section id='tab-{i}' class='lc-tab-panel {hidden}' role='tabpanel'><p>{escape(body)}</p></section>"
        )

    return """
<div class="lc-wrap">
  <div class="lc-tab-list" role="tablist">%s</div>
  %s
</div>
<style>
.lc-wrap{background:#1e1e2e;border:1px solid #333355;border-radius:12px;padding:12px;color:#e0e0f0;font-family:Arial,sans-serif}
.lc-tab-list{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.lc-tab-btn{background:#2a2f4a;border:1px solid #3d4470;color:#e0e0f0;border-radius:8px;padding:8px 10px;cursor:pointer}
.lc-tab-btn[aria-selected='true']{background:#4a90d9;border-color:#4a90d9}
.lc-tab-panel{background:#171a2b;border:1px solid #303552;border-radius:8px;padding:10px}
.hidden{display:none}
</style>
<script>
(() => {
  const root = document.currentScript.previousElementSibling.previousElementSibling;
  if (!root) return;
  const buttons = root.querySelectorAll('.lc-tab-btn');
  const panels = root.querySelectorAll('.lc-tab-panel');
  buttons.forEach((btn, idx) => {
    btn.addEventListener('click', () => {
      buttons.forEach((b) => b.setAttribute('aria-selected', 'false'));
      panels.forEach((p) => p.classList.add('hidden'));
      btn.setAttribute('aria-selected', 'true');
      const panel = panels[idx];
      if (panel) panel.classList.remove('hidden');
    });
  });
})();
</script>
""" % ("".join(buttons), "".join(panels))


def display_lesson_tabs_in_colab() -> None:
    """Render lesson tabs in a notebook cell via IPython.display.display."""
    from IPython.display import HTML, display

    display(HTML(build_lesson_tabs_html()))


def run_colab_feature_smoke_test() -> Dict[str, str]:
    report = {c.name: ("ok" if c.ok else c.message) for c in check_frontend_dependencies()}
    report["lesson_tabs_html"] = "ok" if "lc-tab-btn" in build_lesson_tabs_html() else "missing"
    return report

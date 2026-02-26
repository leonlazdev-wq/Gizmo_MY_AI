"""
ui_theme_toggle.py — Dark/Light theme toggle component.

Renders a fixed-position button (top-right) that toggles the `dark` class on
`document.body`, keeps syntax highlight theme in sync, and persists user choice.
"""

THEME_TOGGLE_HTML = """
<style>
#theme-toggle-btn {
    position: fixed;
    top: 10px;
    right: 20px;
    z-index: 9999;
    font-size: 20px;
    background: transparent;
    border: 1px solid #5b6474;
    border-radius: 999px;
    width: 38px;
    height: 38px;
    cursor: pointer;
    transition: all 0.2s ease;
}
#theme-toggle-btn:hover {
    transform: scale(1.06);
    border-color: #10a37f;
}
.dark #theme-toggle-btn {
    border-color: #3a4455;
}
</style>
<button id="theme-toggle-btn" onclick="window.gizmoToggleTheme && window.gizmoToggleTheme()" title="Toggle dark/light theme">🌙</button>
<script>
(function () {
    function setHighlightByTheme(isDark) {
        const currentCSS = document.getElementById('highlight-css');
        if (currentCSS) {
            currentCSS.setAttribute('href', isDark
                ? 'file/css/highlightjs/github-dark.min.css'
                : 'file/css/highlightjs/github.min.css');
        }
    }

    function syncThemeStateInput(mode) {
        const input = document.querySelector('#theme_state textarea, #theme_state input');
        if (!input) return;
        input.value = mode;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function updateButtonIcon() {
        const btn = document.getElementById('theme-toggle-btn');
        if (!btn) return;
        btn.textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';
    }

    window.gizmoToggleTheme = function () {
        // Use existing global helper if available.
        if (typeof toggleDarkMode === 'function') {
            toggleDarkMode();
        } else {
            document.body.classList.toggle('dark');
        }

        const isDark = document.body.classList.contains('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        setHighlightByTheme(isDark);
        syncThemeStateInput(isDark ? 'dark' : 'light');
        updateButtonIcon();
    };

    // Initial sync on load.
    const saved = localStorage.getItem('theme');
    if (!saved) {
        localStorage.setItem('theme', 'dark');
        document.body.classList.add('dark');
    } else if (saved === 'dark') {
        document.body.classList.add('dark');
    } else if (saved === 'light') {
        document.body.classList.remove('dark');
    }

    setHighlightByTheme(document.body.classList.contains('dark'));
    updateButtonIcon();
})();
</script>
"""


def get_html() -> str:
    """Return the HTML snippet for the theme toggle button."""
    return THEME_TOGGLE_HTML

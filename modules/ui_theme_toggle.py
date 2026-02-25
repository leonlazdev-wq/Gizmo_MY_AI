"""
ui_theme_toggle.py — Dark/Light theme toggle component.

Renders a fixed-position button (top-right) that toggles the `dark` class on
`document.body` and persists the choice in `localStorage`.
"""

THEME_TOGGLE_HTML = """
<style>
#theme-toggle-btn {
    position: fixed;
    top: 10px;
    right: 20px;
    z-index: 9999;
    font-size: 24px;
    background: transparent;
    border: 1px solid #ccc;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    cursor: pointer;
    transition: all 0.3s ease;
}
#theme-toggle-btn:hover {
    transform: scale(1.1);
    border-color: #4F46E5;
}
</style>
<button id="theme-toggle-btn" onclick="toggleTheme()" title="Toggle dark/light theme">🌙</button>
<script>
function toggleTheme() {
    var body = document.body;
    var isDark = body.classList.contains('dark');
    if (isDark) {
        body.classList.remove('dark');
        localStorage.setItem('theme', 'light');
    } else {
        body.classList.add('dark');
        localStorage.setItem('theme', 'dark');
    }
    var btn = document.getElementById('theme-toggle-btn');
    if (btn) btn.textContent = isDark ? '🌙' : '☀️';
}

// Sync button icon with current theme on load
(function() {
    var btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        var isDark = document.body.classList.contains('dark') ||
                     localStorage.getItem('theme') === 'dark';
        btn.textContent = isDark ? '☀️' : '🌙';
    }
})();
</script>
"""


def get_html() -> str:
    """Return the HTML snippet for the theme toggle button."""
    return THEME_TOGGLE_HTML

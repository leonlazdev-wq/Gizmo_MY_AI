"""Version diff helpers based on git history."""

from __future__ import annotations

import subprocess


def get_recent_commits(limit: int = 2) -> list[str]:
    """Return recent commit hashes."""
    proc = subprocess.run(
        ["git", "log", "--oneline", f"-n{limit}"],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return [line.split()[0] for line in lines]


def render_diff(old_rev: str, new_rev: str) -> str:
    """Render a compact HTML summary for commit diff."""
    proc = subprocess.run(
        ["git", "diff", "--stat", old_rev, new_rev],
        capture_output=True,
        text=True,
        check=False,
    )
    content = proc.stdout or "No diff available"
    return f"<pre style='max-height:260px;overflow:auto'>{content}</pre>"

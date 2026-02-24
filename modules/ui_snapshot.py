"""UI state snapshot export utilities."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def capture_ui_state(session_id: str, state: dict[str, Any]) -> str:
    """Persist current UI state into snapshots directory."""
    folder = Path("snapshots")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = folder / f"ui_snapshot_{session_id}_{stamp}.json"
    out.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    return str(out)

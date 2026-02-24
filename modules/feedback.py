"""In-app feedback capture and optional webhook relay."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def submit_feedback(user_id: str, session_id: str, text: str, file_path: str = "") -> dict[str, Any]:
    """Save feedback payload under feedback directory."""
    folder = Path("feedback")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = folder / f"feedback_{session_id}_{stamp}.json"
    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "text": text,
        "file_path": file_path,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(out)}

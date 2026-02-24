"""Audit trace recording for provenance and analytics."""

from __future__ import annotations

import json
from datetime import datetime

from modules.feature_store import get_conn


def _init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                message_id TEXT,
                step_json TEXT,
                created_at TEXT
            )
            """
        )


def record_step(session_id: str, message_id: str, step_dict: dict) -> None:
    """Record a provenance step."""
    _init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_traces (session_id, message_id, step_json, created_at) VALUES (?, ?, ?, ?)",
            (session_id, message_id, json.dumps(step_dict), datetime.utcnow().isoformat() + "Z"),
        )


def list_steps(session_id: str, message_id: str) -> list[dict]:
    """List provenance steps for a message."""
    _init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT step_json, created_at FROM audit_traces WHERE session_id=? AND message_id=? ORDER BY id",
            (session_id, message_id),
        ).fetchall()
    return [{"step": json.loads(r["step_json"]), "created_at": r["created_at"]} for r in rows]

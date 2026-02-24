"""Session feature flags storage and retrieval."""

from __future__ import annotations

from modules.feature_store import get_conn


def _init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_flags (
                session_id TEXT,
                flag_name TEXT,
                enabled INTEGER,
                PRIMARY KEY (session_id, flag_name)
            )
            """
        )


def get_flags(session_id: str) -> dict[str, bool]:
    """Get all feature flags for a session."""
    _init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT flag_name, enabled FROM feature_flags WHERE session_id=?",
            (session_id,),
        ).fetchall()
    return {r["flag_name"]: bool(r["enabled"]) for r in rows}


def set_flag(session_id: str, name: str, enabled: bool) -> None:
    """Set a single feature flag for a session."""
    _init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO feature_flags (session_id, flag_name, enabled) VALUES (?, ?, ?)",
            (session_id, name, int(enabled)),
        )

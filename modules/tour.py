"""First-run guided tour state management."""

from __future__ import annotations

from modules.feature_store import get_conn


def _init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tour_state (
                session_id TEXT PRIMARY KEY,
                completed INTEGER DEFAULT 0
            )
            """
        )


def get_tour_state(session_id: str) -> bool:
    """Return whether the guided tour is completed for a session."""
    _init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT completed FROM tour_state WHERE session_id=?", (session_id,)).fetchone()
    return bool(row and row["completed"])


def mark_tour_completed(session_id: str) -> None:
    """Mark tour as completed for the session."""
    _init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO tour_state (session_id, completed) VALUES (?, 1)",
            (session_id,),
        )

"""Role-based access control helpers."""

from __future__ import annotations

from modules.feature_store import get_conn


ROLE_PRESETS = {
    "Owner": {"read": True, "write": True, "run": True, "manage": True},
    "Editor": {"read": True, "write": True, "run": True, "manage": False},
    "Viewer": {"read": True, "write": False, "run": False, "manage": False},
}


def _init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                session_id TEXT,
                user_id TEXT,
                can_read INTEGER,
                can_write INTEGER,
                can_run INTEGER,
                can_manage INTEGER,
                PRIMARY KEY (session_id, user_id)
            )
            """
        )


def set_permissions(session_id: str, user_id: str, role: str = "Viewer") -> None:
    """Set permissions for user using role preset."""
    _init_db()
    preset = ROLE_PRESETS.get(role, ROLE_PRESETS["Viewer"])
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO permissions
            (session_id, user_id, can_read, can_write, can_run, can_manage)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, int(preset["read"]), int(preset["write"]), int(preset["run"]), int(preset["manage"])),
        )


def enforce_permission(user_id: str, session_id: str, action: str) -> bool:
    """Return True if user has permission for action."""
    _init_db()
    column = {
        "read": "can_read",
        "write": "can_write",
        "run": "can_run",
        "manage": "can_manage",
        "view_analytics": "can_manage",
    }.get(action, "can_read")
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT {column} AS allowed FROM permissions WHERE session_id=? AND user_id=?",  # noqa: S608
            (session_id, user_id),
        ).fetchone()
    return bool(row and row["allowed"])

"""Role-based access control helpers.

# Visual mock:
# Name | Role ▼ | [✓Read] [✓Write] [ ]Run [ ]Manage
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict

DB_PATH = Path("audit/meta.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


ROLE_DEFAULTS = {
    "Owner": {"can_read": True, "can_write": True, "can_run": True, "can_manage": True, "view_analytics": True},
    "Editor": {"can_read": True, "can_write": True, "can_run": True, "can_manage": False, "view_analytics": False},
    "Viewer": {"can_read": True, "can_write": False, "can_run": False, "can_manage": False, "view_analytics": False},
}


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS permissions (
            session_id TEXT,
            user_id TEXT,
            can_read INTEGER,
            can_write INTEGER,
            can_run INTEGER,
            can_manage INTEGER,
            view_analytics INTEGER,
            UNIQUE(session_id, user_id)
        )"""
    )
    conn.commit()
    return conn


def set_permissions(session_id: str, user_id: str, perms: Dict[str, bool]) -> None:
    with _db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO permissions
            (session_id,user_id,can_read,can_write,can_run,can_manage,view_analytics)
            VALUES(?,?,?,?,?,?,?)""",
            (
                session_id,
                user_id,
                int(bool(perms.get("can_read"))),
                int(bool(perms.get("can_write"))),
                int(bool(perms.get("can_run"))),
                int(bool(perms.get("can_manage"))),
                int(bool(perms.get("view_analytics"))),
            ),
        )
        conn.commit()


def set_role_defaults(session_id: str, user_id: str, role: str) -> None:
    set_permissions(session_id, user_id, ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["Viewer"]))


def get_permissions(session_id: str, user_id: str) -> Dict[str, bool]:
    with _db() as conn:
        row = conn.execute(
            "SELECT can_read,can_write,can_run,can_manage,view_analytics FROM permissions WHERE session_id=? AND user_id=?",
            (session_id, user_id),
        ).fetchone()
    if not row:
        if user_id == "local-user":
            return ROLE_DEFAULTS["Owner"].copy()
        return ROLE_DEFAULTS["Viewer"].copy()
    keys = ["can_read", "can_write", "can_run", "can_manage", "view_analytics"]
    return {k: bool(v) for k, v in zip(keys, row)}


def enforce_permission(user_id: str, session_id: str, action: str) -> bool:
    perms = get_permissions(session_id, user_id)
    mapping = {
        "read": "can_read",
        "write": "can_write",
        "run": "can_run",
        "manage": "can_manage",
        "view_analytics": "view_analytics",
    }
    return bool(perms.get(mapping.get(action, action), False))

"""Collaboration session and invite token management."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from secrets import token_urlsafe

from modules.feature_store import get_conn


def _init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS collab_sessions (
                session_id TEXT,
                user_id TEXT,
                role TEXT,
                joined_at TEXT,
                last_seen TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS collab_invites (
                token TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                expires_at TEXT,
                password TEXT,
                used INTEGER DEFAULT 0
            )
            """
        )


def create_session_share(session_id: str, role: str = "Editor", password: str = "") -> str:
    """Create a time-limited invite token."""
    _init_db()
    token = token_urlsafe(18)
    expires = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO collab_invites (token, session_id, role, expires_at, password, used) VALUES (?, ?, ?, ?, ?, 0)",
            (token, session_id, role, expires, password),
        )
    return token


def join_session(token: str, user_id: str, password: str = "") -> dict[str, str]:
    """Join a session using token if valid and single-use."""
    _init_db()
    with get_conn() as conn:
        invite = conn.execute("SELECT * FROM collab_invites WHERE token=?", (token,)).fetchone()
        if not invite:
            return {"status": "error", "message": "Invalid invite token"}
        if invite["used"]:
            return {"status": "error", "message": "Invite token already used"}
        if invite["password"] and invite["password"] != password:
            return {"status": "error", "message": "Invite password mismatch"}
        if datetime.fromisoformat(invite["expires_at"].replace("Z", "")) < datetime.utcnow():
            return {"status": "error", "message": "Invite token expired"}

        now = datetime.utcnow().isoformat() + "Z"
        conn.execute(
            "INSERT INTO collab_sessions (session_id, user_id, role, joined_at, last_seen) VALUES (?, ?, ?, ?, ?)",
            (invite["session_id"], user_id, invite["role"], now, now),
        )
        conn.execute("UPDATE collab_invites SET used=1 WHERE token=?", (token,))
    _persist_membership(invite["session_id"])
    return {"status": "ok", "session_id": invite["session_id"], "role": invite["role"]}


def _persist_membership(session_id: str) -> None:
    members = list_collaborators(session_id)
    path = Path("audit") / f"collab_{session_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(members, indent=2), encoding="utf-8")


def list_collaborators(session_id: str) -> list[dict[str, str]]:
    """List collaborators for session."""
    _init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id, role, last_seen FROM collab_sessions WHERE session_id=?", (session_id,)).fetchall()
    return [{"user_id": r["user_id"], "role": r["role"], "last_seen": r["last_seen"]} for r in rows]


def update_presence(user_id: str, session_id: str) -> None:
    """Update presence heartbeat timestamp."""
    _init_db()
    now = datetime.utcnow().isoformat() + "Z"
    with get_conn() as conn:
        conn.execute(
            "UPDATE collab_sessions SET last_seen=? WHERE session_id=? AND user_id=?",
            (now, session_id, user_id),
        )

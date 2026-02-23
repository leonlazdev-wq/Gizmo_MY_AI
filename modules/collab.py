"""Simple collaboration session services.

# Visual mock:
# ●●● 3 online  [Invite]
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path("audit")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "meta.db"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS collab_invites (
            token TEXT PRIMARY KEY,
            session_id TEXT,
            owner_id TEXT,
            expires_at TEXT,
            password TEXT,
            used INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS collab_members (
            session_id TEXT,
            user_id TEXT,
            role TEXT,
            presence TEXT,
            UNIQUE(session_id, user_id)
        )"""
    )
    conn.commit()
    return conn


def create_session_share(session_id: str, owner_id: str = "owner", password: str = "") -> str:
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
    with _db() as conn:
        conn.execute(
            "INSERT INTO collab_invites(token,session_id,owner_id,expires_at,password,used) VALUES(?,?,?,?,?,0)",
            (token, session_id, owner_id, expires_at, password),
        )
        conn.execute(
            "INSERT OR IGNORE INTO collab_members(session_id,user_id,role,presence) VALUES(?,?,?,?)",
            (session_id, owner_id, "Owner", datetime.utcnow().isoformat() + "Z"),
        )
        conn.commit()
    return token


def join_session(token: str, user_id: str, password: str = "") -> Dict[str, str]:
    with _db() as conn:
        row = conn.execute("SELECT session_id, expires_at, password, used FROM collab_invites WHERE token=?", (token,)).fetchone()
        if not row:
            raise ValueError("Invalid token")
        session_id, expires_at, required_password, used = row
        if used:
            raise ValueError("Token already used")
        if required_password and required_password != password:
            raise ValueError("Invalid invite password")
        if datetime.utcnow() > datetime.fromisoformat(expires_at.rstrip("Z")):
            raise ValueError("Token expired")

        conn.execute(
            "INSERT OR REPLACE INTO collab_members(session_id,user_id,role,presence) VALUES(?,?,?,?)",
            (session_id, user_id, "Editor", datetime.utcnow().isoformat() + "Z"),
        )
        conn.execute("UPDATE collab_invites SET used=1 WHERE token=?", (token,))
        conn.commit()
    return {"session_id": session_id, "user_id": user_id, "role": "Editor"}


def list_collaborators(session_id: str) -> List[Dict[str, str]]:
    with _db() as conn:
        rows = conn.execute("SELECT user_id, role, presence FROM collab_members WHERE session_id=?", (session_id,)).fetchall()
    return [{"name": r[0], "role": r[1], "presence": r[2]} for r in rows]


def update_presence(user_id: str, session_id: str) -> None:
    with _db() as conn:
        conn.execute(
            "UPDATE collab_members SET presence=? WHERE session_id=? AND user_id=?",
            (datetime.utcnow().isoformat() + "Z", session_id, user_id),
        )
        conn.commit()


def collaborators_table(session_id: str) -> str:
    """Return markdown table for lightweight UI rendering."""
    rows = list_collaborators(session_id)
    if not rows:
        return "No collaborators yet."
    head = "| Name | Role | Presence |\n|---|---|---|"
    lines = [f"| {r['name']} | {r['role']} | {r['presence']} |" for r in rows]
    return "\n".join([head] + lines)

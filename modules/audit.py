"""Trace and provenance recording.

# Visual mock:
# User Prompt
#  ├─ Planner
#  ├─ WebSearch
#  └─ Final Answer
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = Path("audit/meta.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_traces (
            session_id TEXT,
            message_id TEXT,
            ts TEXT,
            payload TEXT
        )"""
    )
    conn.commit()
    return conn


def record_step(session_id: str, message_id: str, step_dict: Dict[str, Any]) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO audit_traces(session_id,message_id,ts,payload) VALUES(?,?,?,?)",
            (session_id, message_id, datetime.utcnow().isoformat() + "Z", json.dumps(step_dict, ensure_ascii=False)),
        )
        conn.commit()


def get_timeline(session_id: str, message_id: str) -> List[Dict[str, Any]]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT ts, payload FROM audit_traces WHERE session_id=? AND message_id=? ORDER BY ts",
            (session_id, message_id),
        ).fetchall()
    return [{"timestamp": ts, **json.loads(payload)} for ts, payload in rows]

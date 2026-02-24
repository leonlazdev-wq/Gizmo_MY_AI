"""Shared persistence helpers for feature modules."""

from __future__ import annotations

import sqlite3
from pathlib import Path

META_DB_PATH = Path("meta.db")


def ensure_dirs() -> None:
    """Create feature storage directories if they do not exist."""
    for folder in ("workflows", "plugins", "forms", "audit", "feedback", "snapshots", "demo"):
        Path(folder).mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    """Return a SQLite connection to the shared metadata database."""
    ensure_dirs()
    conn = sqlite3.connect(META_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

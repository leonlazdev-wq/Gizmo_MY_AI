"""Task manager for project tracking."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TASK_PATH = Path("user_data/tasks.json")


def _load() -> List[Dict]:
    if not TASK_PATH.exists():
        return []
    return json.loads(TASK_PATH.read_text(encoding="utf-8"))


def _save(tasks: List[Dict]) -> None:
    TASK_PATH.parent.mkdir(parents=True, exist_ok=True)
    TASK_PATH.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def create_task(title: str, progress: int = 0) -> Dict:
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "progress": int(progress),
        "status": "open",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    tasks = _load()
    tasks.append(task)
    _save(tasks)
    return task


def list_tasks() -> List[Dict]:
    return _load()


def update_task(task_id: str, progress: int | None = None, status: str | None = None) -> bool:
    tasks = _load()
    changed = False
    for t in tasks:
        if t["id"] == task_id:
            if progress is not None:
                t["progress"] = int(progress)
            if status is not None:
                t["status"] = status
            t["updated_at"] = datetime.utcnow().isoformat() + "Z"
            changed = True
            break
    if changed:
        _save(tasks)
    return changed

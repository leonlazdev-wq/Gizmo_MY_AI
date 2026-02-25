"""Data Backup & Restore module for Gizmo.

Handles full backups to .zip, restore from .zip, Google Drive auto-backup,
and individual item export/import.
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from modules.logging_colors import logger

# Paths
_USER_DATA = Path("user_data")
_BACKUP_DIR = Path("/tmp/gizmo_backups")

# Subdirectories/files to include in a selective backup (relative to _USER_DATA)
_BACKUP_SUBDIRS = [
    "flashcards",
    "quiz_results",
    "logs",
    "memory.json",
    "characters",
    "settings",
    "notes",
    "presets",
    "instruction-templates",
]

# Google Drive backup settings
_DRIVE_BACKUP_DIR = Path("/content/drive/MyDrive/Gizmo_Backups")
_MAX_DRIVE_BACKUPS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_backup_dir() -> Path:
    """Create and return the local temporary backup directory."""
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return _BACKUP_DIR


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _zip_name() -> str:
    return f"gizmo_backup_{_timestamp()}.zip"


# ---------------------------------------------------------------------------
# 1. Full Backup to .zip
# ---------------------------------------------------------------------------

def create_backup(include_all: bool = True) -> tuple[str, Optional[str]]:
    """Create a timestamped .zip backup of all user data.

    Args:
        include_all: If True, walk the entire user_data/ directory. If False,
                     only include the paths listed in _BACKUP_ITEMS.

    Returns:
        (status_message, path_to_zip_or_None)
    """
    _ensure_backup_dir()
    zip_path = _BACKUP_DIR / _zip_name()

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if include_all:
                # Walk all of user_data/, skip cache and model dirs (too large)
                _SKIP_DIRS = {"cache", "models", "loras", "mmproj", "image_models"}
                for root, dirs, files in os.walk(_USER_DATA):
                    dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                    for fname in files:
                        full_path = Path(root) / fname
                        arcname = full_path.relative_to(_USER_DATA.parent)
                        zf.write(full_path, arcname)
            else:
                for subdir in _BACKUP_SUBDIRS:
                    item = _USER_DATA / subdir
                    if not item.exists():
                        continue
                    if item.is_file():
                        arcname = item.relative_to(_USER_DATA.parent)
                        zf.write(item, arcname)
                    elif item.is_dir():
                        for sub in item.rglob("*"):
                            if sub.is_file():
                                arcname = sub.relative_to(_USER_DATA.parent)
                                zf.write(sub, arcname)

        size_kb = zip_path.stat().st_size // 1024
        msg = f"✅ Backup created: `{zip_path.name}` ({size_kb} KB)"
        logger.info(msg)
        return msg, str(zip_path)
    except Exception as exc:
        logger.error(f"Backup failed: {exc}")
        return f"❌ Backup failed: {exc}", None


# ---------------------------------------------------------------------------
# 2. Restore from Backup
# ---------------------------------------------------------------------------

def restore_backup(zip_path: str, create_pre_restore_backup: bool = True) -> str:
    """Restore user data from a .zip backup file.

    Args:
        zip_path: Path to the uploaded .zip file.
        create_pre_restore_backup: If True, take a safety backup before overwriting.

    Returns:
        Status message string.
    """
    zip_path_obj = Path(zip_path)
    if not zip_path_obj.exists():
        return "❌ Zip file not found."

    if not zipfile.is_zipfile(zip_path_obj):
        return "❌ The uploaded file is not a valid .zip archive."

    # Validate structure
    with zipfile.ZipFile(zip_path_obj, "r") as zf:
        names = zf.namelist()

    if not any(n.startswith("user_data/") for n in names):
        return "❌ Invalid backup: zip must contain a `user_data/` directory."

    # Safety pre-restore backup
    if create_pre_restore_backup:
        pre_msg, pre_path = create_backup(include_all=True)
        if pre_path:
            logger.info(f"Pre-restore safety backup: {pre_path}")

    # Extract
    try:
        counts: dict[str, int] = {}
        with zipfile.ZipFile(zip_path_obj, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                dest = Path(member.filename)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(member.filename))

                # Count per category
                parts = Path(member.filename).parts
                category = parts[1] if len(parts) > 1 else "root"
                counts[category] = counts.get(category, 0) + 1

        total = sum(counts.values())
        details = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        msg = f"✅ Restored {total} files ({details})"
        logger.info(msg)
        return msg
    except Exception as exc:
        logger.error(f"Restore failed: {exc}")
        return f"❌ Restore failed: {exc}"


# ---------------------------------------------------------------------------
# 3. Google Drive Auto-Backup
# ---------------------------------------------------------------------------

def is_drive_mounted() -> bool:
    """Check if Google Drive is mounted (Colab environment)."""
    from modules.google_drive_sync import is_drive_mounted as _check
    return _check()


def backup_to_drive() -> str:
    """Create a .zip backup and copy it to Google Drive.

    Keeps at most _MAX_DRIVE_BACKUPS files (deletes oldest if over limit).
    Returns a status message.
    """
    if not is_drive_mounted():
        return "⚠️ Google Drive is not mounted. Backup skipped."

    status, zip_path = create_backup(include_all=True)
    if not zip_path:
        return f"❌ Could not create local backup: {status}"

    try:
        _DRIVE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = _DRIVE_BACKUP_DIR / Path(zip_path).name
        shutil.copy2(zip_path, dest)

        # Rotation: keep last _MAX_DRIVE_BACKUPS backups
        backups = sorted(_DRIVE_BACKUP_DIR.glob("gizmo_backup_*.zip"))
        while len(backups) > _MAX_DRIVE_BACKUPS:
            oldest = backups.pop(0)
            oldest.unlink()
            logger.info(f"Rotated old backup: {oldest.name}")

        msg = f"✅ Backed up to Google Drive: `{dest.name}`"
        logger.info(msg)
        return msg
    except Exception as exc:
        logger.error(f"Drive backup failed: {exc}")
        return f"❌ Drive backup failed: {exc}"


def list_drive_backups() -> list[dict]:
    """Return metadata for all backups stored in Google Drive."""
    if not is_drive_mounted():
        return []
    if not _DRIVE_BACKUP_DIR.exists():
        return []
    result = []
    for f in sorted(_DRIVE_BACKUP_DIR.glob("gizmo_backup_*.zip"), reverse=True):
        stat = f.stat()
        result.append({
            "name": f.name,
            "size_kb": stat.st_size // 1024,
            "modified": datetime.utcfromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M UTC"),
        })
    return result


# ---------------------------------------------------------------------------
# 4. Individual Item Export / Import
# ---------------------------------------------------------------------------

def export_flashcard_deck(deck_name: str) -> tuple[str, Optional[str]]:
    """Export a single flashcard deck as a .json file.

    Returns (status_message, path_to_file_or_None).
    """
    deck_path = _USER_DATA / "flashcards" / f"{deck_name}.json"
    if not deck_path.exists():
        return f"❌ Deck `{deck_name}` not found.", None
    dest = Path(f"/tmp/{deck_name}_flashcards.json")
    shutil.copy2(deck_path, dest)
    return f"✅ Exported deck `{deck_name}`", str(dest)


def export_quiz_results() -> tuple[str, Optional[str]]:
    """Export all quiz results as a single .json file."""
    quiz_dir = _USER_DATA / "quiz_results"
    if not quiz_dir.exists():
        return "⚠️ No quiz results found.", None
    results = []
    for f in quiz_dir.glob("*.json"):
        try:
            results.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    dest = Path("/tmp/quiz_results_export.json")
    dest.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"✅ Exported {len(results)} quiz result(s)", str(dest)


def export_chat_history() -> tuple[str, Optional[str]]:
    """Export all chat logs as a .json file."""
    logs_dir = _USER_DATA / "logs"
    if not logs_dir.exists():
        return "⚠️ No chat history found.", None
    all_logs: dict = {}
    for f in logs_dir.rglob("*.json"):
        try:
            all_logs[str(f.relative_to(logs_dir))] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    dest = Path("/tmp/chat_history_export.json")
    dest.write_text(json.dumps(all_logs, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"✅ Exported {len(all_logs)} chat log(s)", str(dest)


def export_memory() -> tuple[str, Optional[str]]:
    """Re-export the memory.json file (delegates to chat_memory if possible)."""
    try:
        from modules.chat_memory import export_memories
        path = export_memories()
        return "✅ Memory exported", str(path)
    except Exception:
        pass
    mem_path = Path("user_data/memory.json")
    if not mem_path.exists():
        return "⚠️ No memory file found.", None
    dest = Path("/tmp/memory_export.json")
    shutil.copy2(mem_path, dest)
    return "✅ Memory exported", str(dest)


def import_item(file_path: str, item_type: str) -> str:
    """Import an individual item from a .json file.

    Args:
        file_path: Path to the uploaded .json file.
        item_type: One of "flashcards", "quiz_results", "memory", "chat_history".

    Returns:
        Status message.
    """
    src = Path(file_path)
    if not src.exists():
        return "❌ File not found."
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"❌ Could not parse JSON: {exc}"

    if item_type == "flashcards":
        dest_dir = _USER_DATA / "flashcards"
        dest_dir.mkdir(parents=True, exist_ok=True)
        deck_name = src.stem.replace("_flashcards", "")
        dest = dest_dir / f"{deck_name}.json"
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return f"✅ Imported flashcard deck `{deck_name}`"

    elif item_type == "quiz_results":
        dest_dir = _USER_DATA / "quiz_results"
        dest_dir.mkdir(parents=True, exist_ok=True)
        ts = _timestamp()
        dest = dest_dir / f"imported_{ts}.json"
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return f"✅ Imported quiz results ({len(data) if isinstance(data, list) else 1} entries)"

    elif item_type == "memory":
        try:
            from modules.chat_memory import import_memories
            return import_memories(file_path)[0]
        except Exception:
            dest = Path("user_data/memory.json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            return "✅ Memory imported"

    elif item_type == "chat_history":
        if isinstance(data, dict):
            logs_dir = _USER_DATA / "logs"
            for rel_path, content in data.items():
                dest = logs_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
            return f"✅ Imported {len(data)} chat log(s)"
        return "❌ Unexpected chat history format."

    return f"❌ Unknown item type: {item_type}"


# ---------------------------------------------------------------------------
# 5. Backup History
# ---------------------------------------------------------------------------

def list_local_backups() -> list[dict]:
    """Return metadata for all local backups in /tmp/gizmo_backups."""
    if not _BACKUP_DIR.exists():
        return []
    result = []
    for f in sorted(_BACKUP_DIR.glob("gizmo_backup_*.zip"), reverse=True):
        stat = f.stat()
        result.append({
            "name": f.name,
            "size_kb": stat.st_size // 1024,
            "modified": datetime.utcfromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M UTC"),
            "path": str(f),
        })
    return result


def get_backup_history_table() -> list[list]:
    """Return backup history as a table for Gradio Dataframe."""
    local = list_local_backups()
    drive = list_drive_backups()
    rows = []
    for b in local:
        rows.append([b["name"], f"{b['size_kb']} KB", b["modified"], "Local"])
    for b in drive:
        rows.append([b["name"], f"{b['size_kb']} KB", b["modified"], "Google Drive"])
    return rows

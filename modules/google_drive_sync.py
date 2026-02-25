import json
import os
import shutil
from pathlib import Path

DRIVE_MOUNT = Path("/content/drive/MyDrive")
BACKUP_DIR = DRIVE_MOUNT / "Gizmo_AI_Backups"


def is_drive_mounted() -> bool:
    """Check if Google Drive is mounted (Colab environment)"""
    return DRIVE_MOUNT.exists() and DRIVE_MOUNT.is_dir()


def is_colab() -> bool:
    """Check if running in Google Colab"""
    return 'COLAB_GPU' in os.environ or 'COLAB_RELEASE_TAG' in os.environ


def setup_backup_dir():
    """Create backup directory structure on Drive"""
    if not is_drive_mounted():
        return False
    (BACKUP_DIR / "chats").mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "settings").mkdir(parents=True, exist_ok=True)
    return True


def backup_chat(history: dict, unique_id: str, character: str, mode: str):
    """Save a chat history file to Google Drive"""
    if not is_drive_mounted():
        return
    if mode == 'instruct':
        dest = BACKUP_DIR / "chats" / "instruct" / f"{unique_id}.json"
    else:
        dest = BACKUP_DIR / "chats" / character / f"{unique_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(history, indent=4, ensure_ascii=False), encoding='utf-8')


def backup_settings():
    """Backup key settings files to Drive"""
    if not is_drive_mounted():
        return
    setup_backup_dir()
    settings_files = [
        "user_data/settings.yaml",
        "user_data/chat_folders.json",
        "user_data/memory.json",
        "user_data/pinned_messages.json",
    ]
    for f in settings_files:
        src = Path(f)
        if src.exists():
            dest = BACKUP_DIR / "settings" / src.name
            shutil.copy2(src, dest)


def restore_from_drive() -> dict:
    """Restore chats and settings from Drive backup. Returns summary."""
    if not is_drive_mounted():
        return {"status": "Drive not mounted"}
    drive_chats = BACKUP_DIR / "chats"
    if drive_chats.exists():
        for chat_file in drive_chats.rglob("*.json"):
            relative = chat_file.relative_to(drive_chats)
            local_dest = Path("user_data/logs/chat") / relative
            local_dest.parent.mkdir(parents=True, exist_ok=True)
            if not local_dest.exists():
                shutil.copy2(chat_file, local_dest)
    drive_settings = BACKUP_DIR / "settings"
    if drive_settings.exists():
        for setting_file in drive_settings.glob("*"):
            local_dest = Path("user_data") / setting_file.name
            if not local_dest.exists():
                shutil.copy2(setting_file, local_dest)
    return {"status": "Restored", "path": str(BACKUP_DIR)}


def get_backup_stats() -> dict:
    """Get stats about what's backed up on Drive"""
    if not is_drive_mounted():
        return {"mounted": False}
    chats_dir = BACKUP_DIR / "chats"
    chat_count = len(list(chats_dir.rglob("*.json"))) if chats_dir.exists() else 0
    return {"mounted": True, "chat_count": chat_count, "path": str(BACKUP_DIR)}

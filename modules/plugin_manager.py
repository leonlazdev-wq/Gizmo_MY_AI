"""Plugin marketplace loader/installer."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def _plugins_dir() -> Path:
    path = Path("plugins")
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_plugins() -> list[dict]:
    """List plugins by manifest files."""
    items: list[dict] = []
    for manifest in _plugins_dir().glob("*/plugin.json"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["enabled"] = (manifest.parent / "enabled.flag").exists()
        items.append(data)
    return items


def install_plugin(url_or_path: str) -> str:
    """Install plugin from local directory path."""
    source = Path(url_or_path)
    if not source.exists():
        raise FileNotFoundError("Plugin path does not exist")
    target = _plugins_dir() / source.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target.name


def enable_plugin(name: str) -> None:
    """Enable plugin by creating flag file."""
    (_plugins_dir() / name / "enabled.flag").write_text("1", encoding="utf-8")


def disable_plugin(name: str) -> None:
    """Disable plugin by removing flag file."""
    flag = _plugins_dir() / name / "enabled.flag"
    if flag.exists():
        flag.unlink()


def uninstall_plugin(name: str) -> None:
    """Uninstall plugin directory."""
    target = _plugins_dir() / name
    if target.exists():
        shutil.rmtree(target)

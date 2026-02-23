"""Plugin marketplace backend.

# Visual mock:
# [icon] Plugin Name ★★★★☆  [Install] [Enable]
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List

PLUGIN_ROOT = Path("extensions/plugins")
PLUGIN_ROOT.mkdir(parents=True, exist_ok=True)
STATE_FILE = PLUGIN_ROOT / "state.json"


def _state() -> Dict[str, bool]:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _save_state(data: Dict[str, bool]) -> None:
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_plugins() -> List[Dict[str, object]]:
    state = _state()
    items: List[Dict[str, object]] = []
    for manifest in PLUGIN_ROOT.glob("*/plugin.json"):
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        name = meta.get("name", manifest.parent.name)
        items.append(
            {
                "name": name,
                "description": meta.get("description", ""),
                "rating": meta.get("rating", 0),
                "enabled": bool(state.get(name, False)),
                "scopes": meta.get("scopes", []),
                "path": str(manifest.parent),
            }
        )
    return sorted(items, key=lambda x: x["name"])


def install_plugin(url_or_path: str) -> str:
    """Install plugin from a local path (remote URLs intentionally unsupported here)."""
    src = Path(url_or_path)
    if not src.exists():
        raise FileNotFoundError(f"Plugin source not found: {url_or_path}")
    dst = PLUGIN_ROOT / src.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst.name


def enable_plugin(name: str) -> None:
    data = _state()
    data[name] = True
    _save_state(data)


def disable_plugin(name: str) -> None:
    data = _state()
    data[name] = False
    _save_state(data)


def uninstall_plugin(name: str) -> None:
    for plugin_dir in PLUGIN_ROOT.glob(f"{name}*"):
        if plugin_dir.is_dir():
            shutil.rmtree(plugin_dir)
    data = _state()
    data.pop(name, None)
    _save_state(data)

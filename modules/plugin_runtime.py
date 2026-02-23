"""Simple plugin loader for extensions/plugins."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Dict, List

PLUGIN_DIR = Path("extensions/plugins")


def discover_plugins() -> List[Dict]:
    result = []
    if not PLUGIN_DIR.exists():
        return result

    for folder in PLUGIN_DIR.iterdir():
        if not folder.is_dir():
            continue
        meta = folder / "plugin.json"
        if not meta.exists():
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            data["path"] = str(folder)
            result.append(data)
        except Exception:
            continue
    return result


def load_plugin(folder_path: str):
    plugin_py = Path(folder_path) / "plugin.py"
    if not plugin_py.exists():
        return None

    spec = importlib.util.spec_from_file_location(f"plugin_{plugin_py.stem}", plugin_py)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

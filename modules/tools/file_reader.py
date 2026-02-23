from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from modules.tools.base import Tool


class FileReaderTool(Tool):
    name = "file_reader"
    description = "Read file contents from workspace."

    def execute(self, **kwargs) -> Dict[str, Any]:
        path = Path(str(kwargs.get("path", "")))
        if not path.exists():
            return {"ok": False, "error": "File not found"}

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            return {"ok": True, "content": content}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

from __future__ import annotations

import contextlib
import io
import multiprocessing as mp
import traceback
from typing import Any, Dict

from modules.tools.base import Tool


def _worker(code: str, q):
    stdout = io.StringIO()
    stderr = io.StringIO()
    ns = {}
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, {"__builtins__": __builtins__}, ns)
        q.put({"ok": True, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()})
    except Exception:
        q.put({"ok": False, "stdout": stdout.getvalue(), "stderr": stderr.getvalue(), "traceback": traceback.format_exc()})


class PythonRunnerTool(Tool):
    name = "python_runner"
    description = "Execute Python code in a time-limited subprocess."

    def execute(self, **kwargs) -> Dict[str, Any]:
        code = str(kwargs.get("code", ""))
        timeout = float(kwargs.get("timeout", 5.0))
        q = mp.Queue()
        p = mp.Process(target=_worker, args=(code, q))
        p.start()
        p.join(timeout)
        if p.is_alive():
            p.terminate()
            return {"ok": False, "error": f"Execution timeout after {timeout}s"}

        if q.empty():
            return {"ok": False, "error": "No output returned"}
        return q.get()

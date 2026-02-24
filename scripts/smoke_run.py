#!/usr/bin/env python3
"""Lightweight import smoke test for server-adjacent modules."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("GRADIO_SERVER_NAME", "0.0.0.0")
os.environ.setdefault("GRADIO_SHARE", "1")

MODULES = [
    "modules.ui",
    "modules.chat",
    "modules.html_generator",
]


def main() -> int:
    for name in MODULES:
        __import__(name)
        print(f"ok: {name}")
    print("smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

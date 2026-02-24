"""Demo data seeding helpers."""

from __future__ import annotations

import json
from pathlib import Path

from modules.feature_workflows import ensure_demo_workflow


def seed_demo_data() -> dict[str, str]:
    """Seed sample docs/memory/workflow for demos."""
    ensure_demo_workflow()
    demo_dir = Path("demo")
    demo_dir.mkdir(parents=True, exist_ok=True)

    sample_doc = demo_dir / "sample.txt"
    sample_doc.write_text("Photosynthesis converts light into chemical energy.", encoding="utf-8")

    mem_file = demo_dir / "memory_demo.json"
    mem_file.write_text(json.dumps({"fact": "Chlorophyll absorbs light."}, indent=2), encoding="utf-8")

    return {"status": "ok", "doc": str(sample_doc), "memory": str(mem_file)}

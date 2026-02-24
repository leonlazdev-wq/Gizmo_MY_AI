"""Smart context builder to avoid dumping whole history."""

from __future__ import annotations

from typing import Dict, List


def build_smart_context(messages: List[Dict], max_items: int = 8) -> List[Dict]:
    scored = []
    for idx, m in enumerate(messages):
        text = (m.get("content") or "").strip()
        score = len(text) * 0.01 + (1.0 if "?" in text else 0.0) + idx * 0.001
        scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:max(1, max_items)]]

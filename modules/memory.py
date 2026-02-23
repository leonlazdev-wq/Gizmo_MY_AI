"""Long-term memory utilities for Gizmo.

This module provides a lightweight, dependency-free memory store with simple
vector-style retrieval based on hashed term frequencies.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

MEMORY_PATH = Path("user_data/memory_store.json")


@dataclass
class MemoryItem:
    """One long-term memory record."""

    id: str
    text: str
    metadata: Dict
    timestamp: str
    source: str
    importance: float
    memory_type: str
    embedding: Dict[str, float]


_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 1]


def _embed(text: str) -> Dict[str, float]:
    counts: Dict[str, float] = {}
    for token in _tokenize(text):
        counts[token] = counts.get(token, 0.0) + 1.0

    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0

    if len(a) > len(b):
        a, b = b, a

    return sum(v * b.get(k, 0.0) for k, v in a.items())


def _load_all() -> List[MemoryItem]:
    if not MEMORY_PATH.exists():
        return []

    raw = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    result: List[MemoryItem] = []
    for item in raw:
        result.append(MemoryItem(**item))

    return result


def _save_all(items: List[MemoryItem]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable = [item.__dict__ for item in items]
    MEMORY_PATH.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_memory_importance(message: str) -> float:
    """Heuristic long-term importance score in [0,10]."""
    text = (message or "").strip().lower()
    if not text:
        return 0.0

    score = 1.0
    boosted_keywords = [
        "prefer", "always", "never", "my name", "remember", "project", "deadline",
        "goal", "i like", "i dislike", "important", "requirement", "use python",
    ]

    for kw in boosted_keywords:
        if kw in text:
            score += 1.4

    score += min(len(text) / 220.0, 2.0)
    return max(0.0, min(10.0, score))


def store_memory(text: str, metadata: Optional[Dict] = None) -> MemoryItem:
    """Store a memory record with metadata and importance."""
    metadata = metadata or {}
    importance = float(metadata.get("importance", detect_memory_importance(text)))

    item = MemoryItem(
        id=str(uuid.uuid4()),
        text=text.strip(),
        metadata=metadata,
        timestamp=datetime.utcnow().isoformat() + "Z",
        source=str(metadata.get("source", "chat")),
        importance=importance,
        memory_type=str(metadata.get("memory_type", "conversations")),
        embedding=_embed(text),
    )

    items = _load_all()
    items.append(item)
    _save_all(items)
    return item


def retrieve_memory(query: str, top_k: int = 5) -> List[Dict]:
    """Retrieve relevant memories using vector similarity + importance."""
    query_vec = _embed(query)
    scored = []
    for item in _load_all():
        sim = _cosine(query_vec, item.embedding)
        score = sim * 0.75 + (item.importance / 10.0) * 0.25
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, item in scored[:max(1, int(top_k))]:
        results.append({
            "id": item.id,
            "text": item.text,
            "score": round(score, 4),
            "source": item.source,
            "importance": item.importance,
            "timestamp": item.timestamp,
            "memory_type": item.memory_type,
        })

    return results


def delete_memory(memory_id: str) -> bool:
    """Delete memory by id."""
    items = _load_all()
    new_items = [i for i in items if i.id != memory_id]
    if len(new_items) == len(items):
        return False

    _save_all(new_items)
    return True


def format_memory_context(query: str, top_k: int = 5) -> str:
    memories = retrieve_memory(query, top_k=top_k)
    if not memories:
        return ""

    lines = ["Relevant past information:"]
    for m in memories:
        lines.append(f"- {m['text']}")
    return "\n".join(lines)
